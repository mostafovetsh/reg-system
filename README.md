# 🎓 نظام تسجيل الطلاب — Student Registration System

## هيكل المشروع

```
passport_system/
├── app.py                 ← Flask Backend
├── requirements.txt       ← المكتبات المطلوبة
├── students_data.xlsx     ← (ينشأ تلقائياً عند أول تسجيل)
├── uploads/               ← (ينشأ تلقائياً — صور الجوازات المرفوعة)
└── static/
    └── index.html         ← صفحة الويب
```

## خطوات التشغيل

### 1. تثبيت المكتبات
```bash
pip install -r requirements.txt
```

### 2. التأكد من وجود Tesseract
- حمّل Tesseract من: https://github.com/tesseract-ocr/tesseract
- تأكد إن المسار في `app.py` صح:
  ```python
  pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
  ```

### 3. تشغيل السيرفر
```bash
python app.py
```

### 4. فتح الصفحة
افتح المتصفح وادخل:
```
http://localhost:5000
```

---

## كيفية عمل النظام

1. **الطالب يرفع صورة جواز السفر وصورة الإقامة** (كلاهما إجباري)
2. **الضغط على "استخراج البيانات"** — يستخرج OCR + MRZ بيانات تلقائياً:
   - الاسم، اللقب، رقم الجواز، الجنسية، تاريخ الميلاد، تاريخ الانتهاء
3. **الطالب يكمل البيانات يدوياً**: التليفون، الواتساب، الإيميل، العنوان
4. **الضغط على حفظ** — يستخدم رقم الجواز كمعرف تسجيل ويحفظ كل البيانات في JSON

---

## الـ API Endpoints

| Method | URL | الوظيفة |
|--------|-----|---------|
| GET | `/` | صفحة الويب |
| POST | `/api/extract-passport` | استخراج بيانات الجواز |
| POST | `/api/extract-id` | استخراج بيانات صورة الإقامة |
| POST | `/api/register` | حفظ الطالب + إنشاء الكود |
