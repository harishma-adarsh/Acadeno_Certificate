# 🌐 Database Access & Cloud Configuration Guide

This guide explains how to access your Acadeno Certificate database from anywhere on any machine, phone, or deployment platform (such as Render, Railway, or Heroku), and how to export all records into Excel at any time.

---

## 🚀 1. Database Access from Anywhere (Remote PostgreSQL)

By default, the application runs locally using **SQLite** (`certificates.db`). 

To access your database remotely from anywhere and preserve database records across deployments, set up a **free cloud PostgreSQL database** using **Supabase** or **Neon**:

### Step 1: Create a Free PostgreSQL Database
1. Go to [Supabase.com](https://supabase.com) or [Neon.tech](https://neon.tech) and sign up for a free account.
2. Click **Create New Project** (e.g. `acadeno-certificates`).
3. Set your database password and region.
4. Copy your database connection string URL. It looks like:
   ```text
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres
   ```

### Step 2: Configure Environment Variable
Add the `DATABASE_URL` key to your `.env` file (locally) or in your deployment environment variables (e.g. on Render):

```env
DATABASE_URL=postgresql://postgres:yourpassword@db.xxxx.supabase.co:5432/postgres
```

The application automatically connects to PostgreSQL when `DATABASE_URL` is set, and falls back to SQLite if `DATABASE_URL` is empty.

---

## 📊 2. Web Database Dashboard

You can view, search, and manage all certificate records from any browser worldwide by navigating to:

```text
http://your-app-url/dashboard
```

### Features:
- 🔍 **Live Search**: Search certificates instantly by Student Name or Certificate Number.
- 📁 **Download PDF**: Directly download or open any certificate PDF file or Cloudinary link.
- 🗑️ **Delete / Clear**: Delete individual records or reset records safely.

---

## 📥 3. Download All Records in Excel

Whether you have 60, 100, or 1000 certificates in the database:
1. Open the Web Dashboard (`/dashboard`).
2. Click the green **"📊 Download All in Excel"** button at the top.
3. The server generates an `.xlsx` Excel spreadsheet containing all stored records:
   - Certificate Number
   - Student Name
   - Local PDF Path
   - Cloudinary URL
   - Creation Date

---

## ⚡ 4. Bulk Generation (60+ Certificates at a Time)

When uploading an Excel file with 60 or more rows:
- The system renders all PDFs locally in seconds.
- All 60 PDFs are packaged into `certificates.zip` and sent to your browser immediately.
- Cloudinary uploads run seamlessly in background threads without causing timeouts or limit caps.
