import os
import sqlite3
import pandas as pd
import re
import zipfile
import io
from datetime import datetime
from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for
from weasyprint import HTML
from jinja2 import Template
import cloudinary
import cloudinary.uploader
import logging
import gc
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

# ---------------- LOGGING CONFIG ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------- CLOUDINARY CONFIG ----------------
cloudinary_cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
cloudinary_api_key = os.getenv("CLOUDINARY_API_KEY")
cloudinary_api_secret = os.getenv("CLOUDINARY_API_SECRET")

if not all([cloudinary_cloud_name, cloudinary_api_key, cloudinary_api_secret]):
    logger.warning("Cloudinary environment variables are missing!")

if cloudinary_cloud_name == "Certificate":
    logger.error("CRITICAL: Your Cloudinary 'cloud_name' is still set to 'Certificate'. Please update your environment variables with your actual Cloudinary Cloud Name.")

cloudinary.config(
    cloud_name=cloudinary_cloud_name,
    api_key=cloudinary_api_key,
    api_secret=cloudinary_api_secret
)

# ---------------- PATHS ----------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "certificates.db")
PDF_DIR = os.path.join(BASE_DIR, "generated", "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)

# ---------------- BACKGROUND EXECUTOR ----------------
bg_executor = ThreadPoolExecutor(max_workers=4)

# ---------------- DATABASE CONFIG ----------------
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def get_db_connection():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def db_execute(query, params=()):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if DATABASE_URL:
            pg_query = query.replace("?", "%s")
            cursor.execute(pg_query, params)
        else:
            cursor.execute(query, params)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def db_fetchall(query, params=()):
    conn = get_db_connection()
    if DATABASE_URL:
        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            pg_query = query.replace("?", "%s")
            cursor.execute(pg_query, params)
            rows = cursor.fetchall()
            return rows
        finally:
            cursor.close()
            conn.close()
    else:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return rows
        finally:
            cursor.close()
            conn.close()


def db_fetchone(query, params=()):
    conn = get_db_connection()
    if DATABASE_URL:
        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            pg_query = query.replace("?", "%s")
            cursor.execute(pg_query, params)
            row = cursor.fetchone()
            return row
        finally:
            cursor.close()
            conn.close()
    else:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row
        finally:
            cursor.close()
            conn.close()


def auto_migrate_sqlite_to_postgres():
    if not DATABASE_URL or not os.path.exists(DB_PATH):
        return
    try:
        import psycopg2
        import psycopg2.extras
        sqlite_conn = sqlite3.connect(DB_PATH)
        sqlite_conn.row_factory = sqlite3.Row
        s_cursor = sqlite_conn.cursor()
        s_cursor.execute("SELECT certificate_number, student_name, pdf_path, cloudinary_url, created_at FROM certificates ORDER BY id ASC")
        rows = s_cursor.fetchall()
        sqlite_conn.close()

        if not rows:
            return

        pg_conn = psycopg2.connect(DATABASE_URL)
        pg_cursor = pg_conn.cursor()
        migrated = 0
        for r in rows:
            pg_cursor.execute("SELECT id FROM certificates WHERE certificate_number = %s", (r["certificate_number"],))
            if not pg_cursor.fetchone():
                pg_cursor.execute(
                    "INSERT INTO certificates (certificate_number, student_name, pdf_path, cloudinary_url, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (r["certificate_number"], r["student_name"], r["pdf_path"], r["cloudinary_url"], r["created_at"])
                )
                migrated += 1
        pg_conn.commit()
        pg_cursor.close()
        pg_conn.close()
        if migrated > 0:
            logger.info(f"Auto-migrated {migrated} records from local SQLite to Cloud PostgreSQL!")
    except Exception as e:
        logger.error(f"Auto migration error: {e}")


def init_db():
    logger.info("Initializing database...")
    if DATABASE_URL:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS certificates (
                    id SERIAL PRIMARY KEY,
                    certificate_number TEXT,
                    student_name TEXT,
                    pdf_path TEXT,
                    cloudinary_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            conn.close()
            logger.info("PostgreSQL Database initialized successfully.")
            auto_migrate_sqlite_to_postgres()
            return
        except Exception as e:
            logger.error(f"PostgreSQL DB init failed: {e}. Falling back to SQLite.", exc_info=True)

    # SQLite fallback
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            certificate_number TEXT,
            student_name TEXT,
            pdf_path TEXT,
            cloudinary_url TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("PRAGMA table_info(certificates)")
    columns = [info[1] for info in c.fetchall()]
    if "cloudinary_url" not in columns:
        c.execute("ALTER TABLE certificates ADD COLUMN cloudinary_url TEXT")
    if "created_at" not in columns:
        c.execute("ALTER TABLE certificates ADD COLUMN created_at DATETIME")

    conn.commit()
    conn.close()
    logger.info("SQLite Database initialization complete.")


# Initialize DB on startup
init_db()


# ---------------- SAFE VALUE (NaN FIX) ----------------
def safe_value(value):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


# ---------------- CERTIFICATE NUMBER LOGIC ----------------
def get_cert_info(cert_type_preference, template_context, rendered_body):
    if cert_type_preference in ["internship", "short_term"]:
        return "INTERNSHIP", "C"
    elif cert_type_preference == "project":
        return "COMPLETION", "PRJ"
    elif cert_type_preference == "workshop":
        return "PARTICIPATION", "WS"
    elif cert_type_preference == "industrial_visit":
        return "INDUSTRIAL VISIT", "C"
    elif cert_type_preference == "appreciation":
        return "COMPLETION", "INT"

    subject_val = str(template_context.get("subject", "")).lower()
    program_val = str(template_context.get("internship_program", "")).lower()
    content_lower = rendered_body.lower()

    if "project" in subject_val or "project" in program_val or "project" in content_lower:
        return "COMPLETION", "PRJ"
    elif "workshop" in subject_val or "workshop" in program_val or "workshop" in content_lower:
        return "PARTICIPATION", "WS"
    elif "industrial visit" in subject_val or "industrial visit" in program_val or "industrial visit" in content_lower:
        return "INDUSTRIAL VISIT", "C"
    elif "appreciation" in subject_val or "appreciation" in program_val or "appreciation" in content_lower:
        return "COMPLETION", "INT"
    else:
        return "INTERNSHIP", "C"


def get_financial_year_suffix(issue_date=None):
    if issue_date is None:
        ref = datetime.now()
    elif isinstance(issue_date, str):
        try:
            ref = datetime.strptime(issue_date, "%d-%m-%Y")
        except ValueError:
            ref = datetime.now()
    else:
        ref = issue_date

    fy_start_year = ref.year if ref.month >= 4 else ref.year - 1
    return str(fy_start_year)[-2:]


def get_last_certificate_number_int(fy=None, type_code="C"):
    START_NUMBER = 1
    if fy is None:
        fy = get_financial_year_suffix(datetime.now())

    prefix = f"ACDT-{fy}-{type_code}-%"
    rows = db_fetchall("SELECT certificate_number FROM certificates WHERE certificate_number LIKE ?", (prefix,))

    max_no = 0
    for row in rows:
        cert_num = row[0] if isinstance(row, (tuple, list)) else row['certificate_number']
        match = re.search(r"(\d+)$", str(cert_num))
        if match:
            num = int(match.group(1))
            if num > max_no:
                max_no = num

    if max_no == 0:
        return START_NUMBER - 1

    return max(max_no, START_NUMBER - 1)


def format_certificate_number(number, issue_date=None, type_code="C"):
    PAD_LENGTH = 3
    fy = get_financial_year_suffix(issue_date)
    padded = str(int(number)).zfill(PAD_LENGTH)
    return f"ACDT-{fy}-{type_code}-{padded}"


def get_next_certificate_number(issue_date=None, type_code="C"):
    fy = get_financial_year_suffix(issue_date)
    last_no = get_last_certificate_number_int(fy, type_code)
    return format_certificate_number(last_no + 1, issue_date, type_code)


# ---------------- FORMATTERS ----------------
def format_semester(semester):
    if semester is None or pd.isna(semester):
        return ""
    semester = str(semester).strip()
    if not semester:
        return ""
    match = re.match(r"^(\d+)(st|nd|rd|th)$", semester, re.IGNORECASE)
    if match:
        return f"{match.group(1)}<sup>{match.group(2)}</sup>"
    if semester.isdigit():
        sem = int(semester)
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(sem % 10, "th")
        return f"{sem}{suffix}"
    return semester


def get_font_size(name):
    length = len(str(name))
    if length > 70:
        return "20px"
    if length > 60:
        return "22px"
    if length > 50:
        return "24px"
    if length > 40:
        return "28px"
    if length > 30:
        return "32px"
    if length > 25:
        return "36px"
    if length > 20:
        return "42px"
    if length > 15:
        return "48px"
    return "64px"


def format_internship_duration(row):
    hours = row.get("internship_hours")
    if not pd.isna(hours) and str(hours).strip():
        match = re.search(r"(\d+)", str(hours))
        if match:
            return f"{match.group(1)} Hours"
        return str(hours).strip()

    start = row.get("start_date") or row.get("joining_date") or row.get("start")
    end = row.get("end_date") or row.get("ending_date") or row.get("end")

    if not pd.isna(start) and not pd.isna(end):
        try:
            start_fmt = pd.to_datetime(start).strftime("%d-%m-%Y")
            end_fmt = pd.to_datetime(end).strftime("%d-%m-%Y")
            return f"from {start_fmt} to {end_fmt}"
        except Exception:
            pass
    return ""


# ---------------- CLOUDINARY UPLOADER ----------------
def upload_to_cloudinary(file_path, public_id):
    try:
        logger.info(f"Uploading {file_path} to Cloudinary...")
        response = cloudinary.uploader.upload(file_path, public_id=public_id, resource_type="auto")
        url = response.get("secure_url")
        logger.info(f"Upload successful: {url}")
        return url
    except Exception as e:
        logger.error(f"Cloudinary upload failed: {e}")
        return None


def async_cloudinary_upload(file_path, cert_no):
    """Background task to upload to Cloudinary and update database URL."""
    try:
        if os.path.exists(file_path):
            url = upload_to_cloudinary(file_path, cert_no)
            if url:
                db_execute("UPDATE certificates SET cloudinary_url = ? WHERE certificate_number = ?", (url, cert_no))
                logger.info(f"Background upload updated DB record for {cert_no}")
    except Exception as e:
        logger.error(f"Background upload error for {cert_no}: {e}")


# ---------------- SMART HEADER DETECTION ----------------
def detect_header_row(excel_file):
    try:
        df_preview = pd.read_excel(excel_file, header=None, nrows=10)
        max_cols = 0
        best_row = 0
        for idx, row in df_preview.iterrows():
            valid_cols = row.dropna().astype(str).str.strip().ne("").sum()
            if valid_cols > max_cols:
                max_cols = valid_cols
                best_row = idx
        return best_row
    except Exception:
        return 0


# ---------------- PREVIEW EXCEL COLUMNS ----------------
@app.route("/preview_columns", methods=["POST"])
def preview_columns():
    try:
        excel_file = request.files.get("excel")
        if not excel_file or not excel_file.filename:
            return jsonify({"error": "No file uploaded"}), 400

        header_row_idx = detect_header_row(excel_file)
        excel_file.seek(0)
        df = pd.read_excel(excel_file, header=header_row_idx)

        original_columns = df.columns.tolist()
        normalized_columns = []
        for col in df.columns:
            col_str = str(col).strip().lower()
            norm_col = re.sub(r"\s+", "_", col_str)
            normalized_columns.append(norm_col)

        column_mapping = [
            {"original": orig, "normalized": norm}
            for orig, norm in zip(original_columns, normalized_columns)
        ]

        return jsonify({
            "success": True,
            "columns": column_mapping,
            "row_count": len(df)
        })
    except Exception as e:
        logger.error(f"Preview columns error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400


# ---------------- MAIN GENERATOR ROUTE ----------------
@app.route("/", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        excel_file = request.files.get("excel")
        custom_content = request.form.get("content", "").strip()
        single_name = request.form.get("student_name", "").strip()
        cert_type_preference = request.form.get("cert_type", "auto")

        # ===================== BULK MODE =====================
        if excel_file and excel_file.filename:
            try:
                header_row_idx = detect_header_row(excel_file)
                excel_file.seek(0)
                df = pd.read_excel(excel_file, header=header_row_idx)

                df = df.dropna(how='all')
                df.columns = [str(c).strip() for c in df.columns]
                df.columns = (
                    pd.Series(df.columns)
                    .str.lower()
                    .str.replace(r"\s+", "_", regex=True)
                )

                name_cols = ["student_name", "full_name", "name", "full_name_with_initial", "studentname"]
                actual_name_col = next((c for c in name_cols if c in df.columns), None)
                if actual_name_col:
                    df = df[df[actual_name_col].astype(str).str.strip().ne("nan") & df[actual_name_col].astype(str).str.strip().ne("")]

                df = df.reset_index(drop=True)
                logger.info(f"Bulk generation started for {len(df)} rows.")
                if len(df) == 0:
                    return "Error: No valid data rows found in Excel file. Please check column headings."

                date_cols = ["issue_date", "date", "start_date", "end_date", "joining_date", "ending_date"]
                for col in date_cols:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

                pdf_files = []
                batch_id = datetime.now().strftime("%Y%m%d%H%M%S")
                batch_dir = os.path.join(PDF_DIR, batch_id)
                os.makedirs(batch_dir, exist_ok=True)

                start_no_input = request.form.get("start_number", "").strip()
                user_start_no = int(start_no_input) if start_no_input and start_no_input.isdigit() else None
                fy_next_number = {}

                selected_template = request.form.get("template", "Certificate_Acadeno.html")

                for i, (_, row) in enumerate(df.iterrows()):
                    issue_date_val = row.get("issue_date") or row.get("date")
                    if not pd.isna(issue_date_val) and hasattr(issue_date_val, "strftime"):
                        issue_date = issue_date_val.strftime("%d-%m-%Y")
                    else:
                        issue_date_val = None
                        issue_date = datetime.now().strftime("%d-%m-%Y")

                    fy = get_financial_year_suffix(issue_date_val)

                    template_context = {}
                    for col in df.columns:
                        value = row.get(col)
                        if col == "semester":
                            template_context[col] = format_semester(value)
                        elif col == "internship_duration":
                            template_context[col] = format_internship_duration(row)
                        elif col in ["start_date", "end_date", "joining_date", "ending_date"] and not pd.isna(value):
                            template_context[col] = pd.to_datetime(value).strftime("%d-%m-%Y")
                        elif col == "issue_date":
                            template_context[col] = issue_date
                        else:
                            template_context[col] = safe_value(value)

                    if "course_name" not in template_context and "subject" in template_context:
                        template_context["course_name"] = template_context["subject"]
                    if "internship_program" not in template_context:
                        template_context["internship_program"] = template_context.get("subject") or template_context.get("department", "")

                    reg_val = None
                    for key in template_context.keys():
                        if "register" in key or "reg" in key:
                            reg_val = template_context[key]
                            break
                    if reg_val:
                        template_context["reg_id"] = reg_val
                        template_context["register_number"] = reg_val

                    if "internship_duration" not in template_context:
                        template_context["internship_duration"] = format_internship_duration(row)

                    template = Template(custom_content)
                    rendered_body = template.render(**template_context)

                    cert_title, type_code = get_cert_info(cert_type_preference, template_context, rendered_body)

                    seq_key = (fy, type_code)
                    if seq_key not in fy_next_number:
                        if user_start_no is not None and len(fy_next_number) == 0:
                            fy_next_number[seq_key] = user_start_no
                        else:
                            fy_next_number[seq_key] = get_last_certificate_number_int(fy, type_code) + 1

                    cert_no = format_certificate_number(fy_next_number[seq_key], issue_date_val, type_code)
                    fy_next_number[seq_key] += 1

                    student_name_val = (
                        row.get("student_name") or
                        row.get("full_name") or
                        row.get("name") or
                        row.get("full_name_with_initial")
                    )

                    student_name = safe_value(student_name_val)

                    context = {
                        "student_name": student_name,
                        "student_name_style": f"font-size: {get_font_size(student_name)};",
                        "certificate_body": rendered_body,
                        "certificate_title": cert_title,
                        "certificate_number": cert_no,
                        "place": safe_value(row.get("place")),
                        "issue_date": issue_date,
                        "base_url": f"file:///{BASE_DIR.replace(os.sep, '/')}"
                    }

                    html = render_template(selected_template, **context)

                    safe_name = re.sub(r'[^\w\s-]', '', str(student_name)).strip().replace(' ', '_')
                    pdf_filename = f"{cert_no}_{safe_name}.pdf"
                    pdf_path = os.path.join(batch_dir, pdf_filename)

                    # Generate PDF directly to disk
                    HTML(string=html, base_url=BASE_DIR).write_pdf(pdf_path)
                    pdf_files.append(pdf_path)

                    # Insert DB record immediately
                    db_execute(
                        "INSERT INTO certificates (certificate_number, student_name, pdf_path, cloudinary_url) VALUES (?, ?, ?, ?)",
                        (cert_no, student_name, pdf_path, None)
                    )

                    # Queue async Cloudinary upload
                    bg_executor.submit(async_cloudinary_upload, pdf_path, cert_no)

                    del html
                    if i % 10 == 0:
                        gc.collect()

                # Package all 60+ generated PDFs into ZIP file
                zip_name = f"certificates_{batch_id}.zip"
                zip_path = os.path.join(PDF_DIR, zip_name)

                with zipfile.ZipFile(zip_path, "w") as zipf:
                    for pdf in pdf_files:
                        zipf.write(pdf, os.path.basename(pdf))

                return send_file(zip_path, as_attachment=True, download_name="certificates.zip")

            except Exception as e:
                logger.error(f"Bulk generation error: {e}", exc_info=True)
                return jsonify({"error": f"An error occurred during bulk generation: {str(e)}"}), 500

        # ===================== SINGLE MODE =====================
        elif single_name and custom_content:
            try:
                raw_date = request.form.get("single_date", "")
                single_place = request.form.get("single_place", "")

                single_date = ""
                if raw_date:
                    single_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d-%m-%Y")

                start_no_input = request.form.get("start_number", "").strip()
                fy_date = datetime.strptime(raw_date, "%Y-%m-%d") if raw_date else None
                fy = get_financial_year_suffix(fy_date)

                template = Template(custom_content)
                rendered_body = template.render()

                cert_title, type_code = get_cert_info(cert_type_preference, {}, rendered_body)

                try:
                    user_start = int(start_no_input) if start_no_input else None
                except ValueError:
                    user_start = None

                if user_start is not None:
                    cert_no = format_certificate_number(user_start, fy_date, type_code)
                else:
                    cert_no = get_next_certificate_number(fy_date, type_code)

                context = {
                    "student_name": safe_value(single_name),
                    "student_name_style": f"font-size: {get_font_size(single_name)};",
                    "certificate_body": rendered_body,
                    "certificate_title": cert_title,
                    "certificate_number": cert_no,
                    "single_place": safe_value(single_place),
                    "single_issue_date": single_date,
                    "base_url": f"file:///{BASE_DIR.replace(os.sep, '/')}"
                }

                selected_template = request.form.get("template", "Certificate_Acadeno.html")
                html = render_template(selected_template, **context)

                single_id = datetime.now().strftime("%Y%m%d%H%M%S_%f")
                pdf_path = os.path.join(PDF_DIR, f"{cert_no}_{single_id}.pdf")

                HTML(string=html, base_url=BASE_DIR).write_pdf(pdf_path)

                cloudinary_url = upload_to_cloudinary(pdf_path, cert_no)

                db_execute(
                    "INSERT INTO certificates (certificate_number, student_name, pdf_path, cloudinary_url) VALUES (?, ?, ?, ?)",
                    (cert_no, context["student_name"], pdf_path, cloudinary_url)
                )

                safe_name = re.sub(r'[^\w\s-]', '', str(context["student_name"])).strip().replace(' ', '_')
                download_name = f"{cert_no}_{safe_name}.pdf"

                return send_file(pdf_path, as_attachment=True, download_name=download_name)
            except Exception as e:
                logger.error(f"Single generation error: {e}", exc_info=True)
                return jsonify({"error": f"An error occurred during certificate generation: {str(e)}"}), 500

        return "Error: Upload Excel or enter Student Name"

    return render_template("upload.html")


# ---------------- WEB DATABASE DASHBOARD ----------------
@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")


# ---------------- API: FETCH CERTIFICATE RECORDS ----------------
@app.route("/api/records", methods=["GET"])
def get_records():
    try:
        search_query = request.args.get("q", "").strip()
        if search_query:
            param = f"%{search_query}%"
            rows = db_fetchall(
                "SELECT id, certificate_number, student_name, pdf_path, cloudinary_url, created_at FROM certificates WHERE student_name LIKE ? OR certificate_number LIKE ? ORDER BY id DESC",
                (param, param)
            )
        else:
            rows = db_fetchall(
                "SELECT id, certificate_number, student_name, pdf_path, cloudinary_url, created_at FROM certificates ORDER BY id DESC"
            )

        records = []
        for r in rows:
            if isinstance(r, (tuple, list)):
                records.append({
                    "id": r[0],
                    "certificate_number": r[1],
                    "student_name": r[2],
                    "pdf_path": r[3],
                    "cloudinary_url": r[4],
                    "created_at": str(r[5]) if len(r) > 5 and r[5] else ""
                })
            else:
                records.append({
                    "id": r["id"],
                    "certificate_number": r["certificate_number"],
                    "student_name": r["student_name"],
                    "pdf_path": r["pdf_path"],
                    "cloudinary_url": r["cloudinary_url"],
                    "created_at": str(r["created_at"]) if "created_at" in r.keys() and r["created_at"] else ""
                })

        return jsonify({"success": True, "count": len(records), "data": records})
    except Exception as e:
        logger.error(f"Get records API error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------- EXPORT ALL CERTIFICATES TO EXCEL ----------------
@app.route("/export_excel", methods=["GET"])
def export_excel():
    try:
        rows = db_fetchall("SELECT certificate_number, student_name, pdf_path, cloudinary_url, created_at FROM certificates ORDER BY id DESC")

        data = []
        for r in rows:
            if isinstance(r, (tuple, list)):
                data.append({
                    "Certificate Number": r[0],
                    "Student Name": r[1],
                    "Local PDF Path": r[2],
                    "Cloudinary URL": r[3] or "",
                    "Created At": str(r[4]) if len(r) > 4 and r[4] else ""
                })
            else:
                data.append({
                    "Certificate Number": r["certificate_number"],
                    "Student Name": r["student_name"],
                    "Local PDF Path": r["pdf_path"],
                    "Cloudinary URL": r["cloudinary_url"] or "",
                    "Created At": str(r["created_at"]) if "created_at" in r.keys() and r["created_at"] else ""
                })

        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame(columns=["Certificate Number", "Student Name", "Local PDF Path", "Cloudinary URL", "Created At"])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Certificates')

        output.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_name = f"certificates_database_{timestamp}.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        logger.error(f"Export excel error: {e}", exc_info=True)
        return jsonify({"error": f"Failed to export Excel: {str(e)}"}), 500


# ---------------- VIEW / DOWNLOAD SINGLE PDF ----------------
@app.route("/view_pdf/<int:record_id>", methods=["GET"])
def view_pdf(record_id):
    try:
        row = db_fetchone("SELECT pdf_path, cloudinary_url, student_name, certificate_number FROM certificates WHERE id = ?", (record_id,))
        if not row:
            return "Certificate record not found", 404

        pdf_path = row[0] if isinstance(row, (tuple, list)) else row["pdf_path"]
        cloudinary_url = row[1] if isinstance(row, (tuple, list)) else row["cloudinary_url"]
        student_name = row[2] if isinstance(row, (tuple, list)) else row["student_name"]
        cert_no = row[3] if isinstance(row, (tuple, list)) else row["certificate_number"]

        if pdf_path and os.path.exists(pdf_path):
            safe_name = re.sub(r'[^\w\s-]', '', str(student_name)).strip().replace(' ', '_')
            return send_file(pdf_path, as_attachment=False, download_name=f"{cert_no}_{safe_name}.pdf")
        elif cloudinary_url:
            return redirect(cloudinary_url)
        else:
            return "PDF file is not available locally or on Cloudinary", 404
    except Exception as e:
        logger.error(f"View PDF error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------------- DELETE SINGLE RECORD ----------------
@app.route("/delete_record/<int:record_id>", methods=["POST", "DELETE"])
def delete_record(record_id):
    try:
        row = db_fetchone("SELECT pdf_path FROM certificates WHERE id = ?", (record_id,))
        if row:
            pdf_path = row[0] if isinstance(row, (tuple, list)) else row["pdf_path"]
            if pdf_path and os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass
        db_execute("DELETE FROM certificates WHERE id = ?", (record_id,))
        return jsonify({"success": True, "message": f"Record {record_id} deleted successfully."})
    except Exception as e:
        logger.error(f"Delete record error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------- CLEAR ALL DB RECORDS ----------------
@app.route("/clear_db", methods=["POST"])
def clear_db():
    try:
        db_execute("DELETE FROM certificates")
        if not DATABASE_URL:
            db_execute("DELETE FROM sqlite_sequence WHERE name='certificates'")

        if os.path.exists(PDF_DIR):
            for f in os.listdir(PDF_DIR):
                file_path = os.path.join(PDF_DIR, f)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {e}")

        return jsonify({"success": True, "message": "Database and generated files cleared successfully!"})
    except Exception as e:
        logger.error(f"Clear DB error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------- MAIN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)