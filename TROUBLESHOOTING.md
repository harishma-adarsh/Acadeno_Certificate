# 🔧 Troubleshooting Guide

## Issue Fixed: Template Syntax Error

### Problem
```
jinja2.exceptions.TemplateSyntaxError: unexpected char '$' at 10980
```

### Cause
The issue was caused by mixing JavaScript template literals `${}` with Jinja2 template syntax `{{ }}` in the HTML file. Jinja2 was trying to parse the JavaScript code and encountered the `$` character inside the `{{ }}` braces.

### Solution
Changed JavaScript template literals from:
```javascript
// ❌ WRONG - Jinja2 tries to parse this
badge.textContent = `{{ ${col.normalized} }}`;
```

To string concatenation:
```javascript
// ✅ CORRECT - Jinja2 ignores this
badge.textContent = '{{ ' + col.normalized + ' }}';
```

### Files Fixed
- `templates/upload.html` - Lines 307, 339, 341, 349

---

## ✅ Application Status

The Flask application is now running successfully at:
- **Local**: http://127.0.0.1:10000
- **Network**: http://192.168.20.4:10000

---

## 🎯 How to Use

1. **Open Browser**: Navigate to `http://localhost:10000`

2. **Upload Excel File**: 
   - Click "Upload Excel File"
   - Select any `.xlsx` or `.xls` file
   - Click "🔍 Preview Excel Columns"

3. **View Placeholders**:
   - System shows all detected columns
   - Example: `Student Name → {{ student_name }}`

4. **Create Template**:
   - Click purple badges to copy placeholders
   - Paste into certificate content area

5. **Generate**:
   - Click "🎓 Generate Certificate(s)"
   - Download ZIP with all certificates

---

## 🐛 Common Issues & Solutions

### Issue: Internal Server Error
**Solution**: Restart the Flask server
```bash
# Stop current server (Ctrl+C)
# Start again
python app.py
```

### Issue: Excel file not loading
**Solution**: 
- Ensure file is `.xlsx` or `.xls` format
- Check file is not corrupted
- Verify file has headers in first row

### Issue: Placeholders not working
**Solution**:
- Always click "Preview Excel Columns" first
- Copy placeholders by clicking badges
- Ensure exact match (case-sensitive)

### Issue: Port already in use
**Solution**:
```bash
# Kill existing process on port 10000
# Windows:
netstat -ano | findstr :10000
taskkill /PID <PID> /F

# Then restart
python app.py
```

### Issue: Module not found
**Solution**:
```bash
# Activate virtual environment
venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

---

## 📝 Technical Notes

### Template Syntax Rules

When mixing Jinja2 and JavaScript:

**❌ DON'T use template literals with Jinja2 syntax:**
```javascript
let html = `<div>{{ ${variable} }}</div>`;  // ERROR!
```

**✅ DO use string concatenation:**
```javascript
let html = '<div>{{ ' + variable + ' }}</div>';  // CORRECT
```

**✅ OR use HTML entities:**
```javascript
let html = `<div>&#123;&#123; ${variable} &#125;&#125;</div>`;  // CORRECT
```

### Why This Happens

1. Jinja2 processes the template **before** JavaScript runs
2. Jinja2 sees `{{ }}` and tries to evaluate it
3. Finds `$` inside and throws syntax error
4. JavaScript never gets a chance to run

### The Fix

By using string concatenation or HTML entities, we prevent Jinja2 from seeing the `{{ }}` as template syntax during the initial parse.

---

## 🚀 Performance Tips

1. **Test with small files first**: Try 2-3 rows before bulk generation
2. **Close unused tabs**: Reduces memory usage
3. **Clear generated folder**: Delete old PDFs periodically
4. **Use consistent data**: Ensure all rows have required columns

---

## 📞 Need More Help?

Check these files:
- `README.md` - Full documentation
- `USAGE_GUIDE.md` - Detailed usage examples
- `QUICK_START.md` - Quick reference
- `EXAMPLE_WALKTHROUGH.md` - Step-by-step examples

---

**Last Updated**: 2026-01-29
**Status**: ✅ All issues resolved
