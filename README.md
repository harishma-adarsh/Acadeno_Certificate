# Certificate Generator - Dynamic Excel Column Support

## 🎯 Overview

This Flask application generates certificates based on Excel data with **dynamic column detection**. The system automatically reads your Excel file headers and makes them available as placeholders in your certificate template.

## ✨ New Features

### 1. **Dynamic Column Detection**
- Upload any Excel file and the system will automatically detect all column headers
- Column names are normalized (spaces become underscores, converted to lowercase)
- All columns become available as placeholders in your certificate template

### 2. **Interactive Preview**
- Click "Preview Excel Columns" to see all available placeholders
- View the mapping between original column names and normalized placeholders
- See total row count before generating certificates

### 3. **Click-to-Copy Placeholders**
- Click any placeholder badge to copy it to your clipboard
- Instant visual feedback when copied
- Makes template creation faster and error-free

## 📋 How to Use

### Step 1: Prepare Your Excel File

Create an Excel file with any columns you need. For example:

| Student Name | College Name | College Location | Semester | Course Name | Reg ID | Internship Program | Internship Hours | Start Date | End Date | Place | Issue Date |
|--------------|--------------|------------------|----------|-------------|--------|-------------------|------------------|------------|----------|-------|------------|
| John Doe | ABC College | New York | 3rd | Computer Science | CS001 | Web Development | 120 | 01-01-2025 | 31-01-2025 | New York | 15-01-2025 |

**Note:** You can add ANY columns you want - the system will automatically detect them!

### Step 2: Upload and Preview

1. Go to `http://localhost:10000` (or your server URL)
2. Click "Upload Excel File" and select your file
3. Click "🔍 Preview Excel Columns" button
4. The system will show:
   - ✅ Success message
   - 📊 Total number of rows
   - List of detected columns with their placeholder names

Example output:
```
✅ Excel file loaded successfully!
📊 Total rows: 50

Detected Columns:
Student Name → {{ student_name }}
College Name → {{ college_name }}
College Location → {{ college_location }}
Semester → {{ semester }}
...
```

### Step 3: Create Your Certificate Template

In the "Certificate Content Template" field, use the placeholders shown in the preview:

```
This is to certify that {{ student_name }} from {{ college_name }}, {{ college_location }}, 
studying {{ course_name }} ({{ semester }} semester) with Registration ID: {{ reg_id }}, 
has successfully completed the {{ internship_program }} internship program 
for a duration of {{ internship_duration }}.

Date: {{ issue_date }}
Place: {{ place }}
```

**Tips:**
- Click on any placeholder badge to copy it
- Use any column from your Excel file
- The system handles date formatting automatically

### Step 4: Generate Certificates

Click "🎓 Generate Certificate(s)" and the system will:
- Generate a PDF certificate for each row in your Excel
- Create a ZIP file containing all certificates
- Automatically download the ZIP file

## 🔧 Special Features

### Automatic Formatting

The system provides special formatting for certain columns:

1. **Semester**: Automatically adds superscript (3rd, 2nd, 4th)
   - Input: `3` or `3rd` → Output: `3<sup>rd</sup>`

2. **Dates**: Automatically formats to DD-MM-YYYY
   - Columns: `issue_date`, `start_date`, `end_date`
   - Input: `2025-01-15` → Output: `15-01-2025`

3. **Internship Duration**: Computed field
   - Uses `internship_hours` if available → "120 Hours"
   - Otherwise uses `start_date` and `end_date` → "from 01-01-2025 to 31-01-2025"

### Computed Fields

Some placeholders are computed from other columns:

- `{{ internship_duration }}` - Calculated from hours or date range (shown in orange)

## 📝 Column Name Normalization

Excel column headers are normalized to create valid placeholder names:

| Original Column | Normalized Placeholder |
|----------------|----------------------|
| Student Name | `{{ student_name }}` |
| College Location | `{{ college_location }}` |
| Reg ID | `{{ reg_id }}` |
| Internship Program | `{{ internship_program }}` |

**Rules:**
- Spaces → Underscores
- Uppercase → Lowercase
- Special characters removed

## 🎨 Single Certificate Mode

You can also generate a single certificate without Excel:

1. Leave Excel field empty
2. Fill in:
   - Student Name
   - Issue Date
   - Place
3. Write your certificate content
4. Click "Generate Certificate(s)"

## 🚀 Example Workflow

1. **Upload Excel**: `students_data.xlsx`
2. **Preview Columns**: See all available placeholders
3. **Copy Placeholders**: Click badges to copy them
4. **Create Template**: 
   ```
   Certificate of Completion
   
   This certifies that {{ student_name }} has completed {{ course_name }}
   at {{ college_name }}, {{ college_location }}.
   
   Duration: {{ internship_duration }}
   Date: {{ issue_date }}
   ```
5. **Generate**: Click button and download ZIP with all certificates

## 🔍 Troubleshooting

### Excel file not loading?
- Ensure file is `.xlsx` or `.xls` format
- Check that file has headers in the first row
- Verify file is not corrupted

### Placeholders not working?
- Click "Preview Excel Columns" to see exact placeholder names
- Copy placeholders by clicking the badges
- Ensure placeholders match exactly (case-sensitive in template)

### Dates not formatting?
- Ensure date columns are named: `issue_date`, `start_date`, or `end_date`
- Excel dates should be in date format, not text

## 📦 Requirements

```
Flask
pandas
openpyxl
weasyprint
jinja2
```

## 🎯 Benefits

✅ **Flexible**: Use any Excel columns you want
✅ **Easy**: Click-to-copy placeholders
✅ **Fast**: Preview before generating
✅ **Smart**: Automatic formatting for dates and semesters
✅ **Visual**: Beautiful, modern interface
✅ **Reliable**: Error handling and validation

## 💡 Pro Tips

1. **Test First**: Upload Excel and preview columns before creating template
2. **Copy Placeholders**: Use click-to-copy to avoid typos
3. **Check Preview**: Verify row count matches your expectations
4. **Use Computed Fields**: Take advantage of `internship_duration` for flexibility
5. **Consistent Naming**: Keep Excel column names simple and clear

---

**Need Help?** The interface shows all available placeholders based on your Excel file. Just upload, preview, and start creating!
