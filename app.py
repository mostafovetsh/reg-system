"""
مركز فجر — نظام تسجيل الطلاب
Fajr Center — Student Registration System
v4.5 — Optimized Hybrid Engine (3x Upscale)
"""

import os
import sys
import io
import json
import time
import socket
import base64
import logging
import ssl
import re
import xmlrpc.client
from datetime import datetime, date
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, Response, session, redirect
import qrcode
from flask_cors import CORS

# ─── إعداد الـ Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("fajr")

# ─── التطبيق ──────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'CHANGE_THIS_IN_PRODUCTION_fajr2024')
CORS(app)

# ─── الإعدادات ────────────────────────────────────────────────────────────────
ODOO_URL      = os.environ.get('ODOO_URL',      'https://sys.fajr.com')
ODOO_DB       = os.environ.get('ODOO_DB',       'Fajr')
ODOO_USER     = os.environ.get('ODOO_USER',     'develop_register@fajr.com')
ODOO_PASSWORD = os.environ.get('ODOO_PASSWORD', '123456')

ADMIN_USERNAME = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASS', '123')

MAINTENANCE_MODE = False

# ─── مسارات الملفات ───────────────────────────────────────────────────────────
UPLOAD_FOLDER     = 'uploads'
JSON_FILE         = 'students_data.json'
WAITING_LIST_FILE = 'waiting_list.json'
ALLOWED_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'webp', 'jfif', 'avif', 'bmp', 'tiff', 'pjpeg', 'pjp',
    'gif', 'heic', 'heif',
}
_EXT_CANONICAL = {
    'jpeg': 'jpg', 'jpe': 'jpg', 'jfif': 'jpg', 'pjpeg': 'jpg', 'pjp': 'jpg',
    'tif': 'tiff', 'heif': 'heic',
}
_MIME_TO_EXT = {
    'image/jpeg': 'jpg', 'image/jpg': 'jpg', 'image/pjpeg': 'jpg',
    'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif',
    'image/bmp': 'bmp', 'image/x-ms-bmp': 'bmp',
    'image/tiff': 'tiff', 'image/x-tiff': 'tiff',
    'image/avif': 'avif',
    'image/heic': 'heic', 'image/heif': 'heic',
}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─── Tesseract OCR ────────────────────────────────────────────────────────────
try:
    import pytesseract
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    OCR_AVAILABLE = True
    log.info("✅ Tesseract OCR ready")
except ImportError:
    OCR_AVAILABLE = False
    log.warning("⚠️ pytesseract / Pillow غير متاح — OCR معطّل")

# ─── MRZ Library ──────────────────────────────────────────────────────────────
try:
    from mrz.checker.td3 import TD3CodeChecker
    MRZ_AVAILABLE = True
    log.info("✅ MRZ Library ready")
except ImportError:
    MRZ_AVAILABLE = False
    log.warning("⚠️ MRZ Library غير متاحة")

# ─── Odoo Constants الافتراضية ──────────────────────────────────────────────
DEFAULT_CATEGORY_ID = 53  
ODOO_BRANCH_ID = 1      

# ─── جدول تحويل ISO 3→2 ───────────────────────────────────────────────────────
ISO_MAPPING = {
    'AFG':'AF','ALB':'AL','DZA':'DZ','ASM':'AS','AND':'AD','AGO':'AO','AIA':'AI',
    'ATA':'AQ','ATG':'AG','ARG':'AR','ARM':'AM','ABW':'AW','AUS':'AU','AUT':'AT',
    'AZE':'AZ','BHS':'BS','BHR':'BH','BGD':'BD','BRB':'BB','BLR':'BY','BEL':'BE',
    'BLZ':'BZ','BEN':'BJ','BMU':'BM','BTN':'BT','BOL':'BO','BIH':'BA','BWA':'BW',
    'BVT':'BV','BRA':'BR','IOT':'IO','BRN':'BN','BGR':'BG','BFA':'BF','BDI':'BI',
    'KHM':'KH','CMR':'CM','CAN':'CA','CPV':'CV','CYM':'KY','CAF':'CF','TCD':'TD',
    'CHL':'CL','CHN':'CN','CXR':'CX','CCK':'CC','COL':'CO','COM':'KM','COG':'CG',
    'COD':'CD','COK':'CK','CRI':'CR','CIV':'CI','HRV':'HR','CUB':'CU','CYP':'CY',
    'CZE':'CZ','DNK':'DK','DJI':'DJ','DMA':'DM','DOM':'DO','ECU':'EC','EGY':'EG',
    'SLV':'SV','GNQ':'GQ','ERI':'ER','EST':'EE','ETH':'ET','FLK':'FK','FRO':'FO',
    'FJI':'FJ','FIN':'FI','FRA':'FR','GUF':'GF','PYF':'PF','ATF':'TF','GAB':'GA',
    'GMB':'GM','GEO':'GE','DEU':'DE','GHA':'GH','GIB':'GI','GRC':'GR','GRL':'GL',
    'GRD':'GD','GLP':'GP','GUM':'GU','GTM':'GT','GIN':'GN','GNB':'GW','GUY':'GY',
    'HTI':'HT','HMD':'HM','VAT':'VA','HND':'HN','HKG':'HK','HUN':'HU','ISL':'IS',
    'IND':'IN','IDN':'ID','IRN':'IR','IRQ':'IQ','IRL':'IE','ISR':'IL','ITA':'IT',
    'JAM':'JM','JPN':'JP','JOR':'JO','KAZ':'KZ','KEN':'KE','KIR':'KI','PRK':'KP',
    'KOR':'KR','KWT':'KW','KGZ':'KG','LAO':'LA','LVA':'LV','LBN':'LB','LSO':'LS',
    'LBR':'LR','LBY':'LY','LIE':'LI','LTU':'LT','LUX':'LU','MAC':'MO','MKD':'MK',
    'MDG':'MG','MWI':'MW','MYS':'MY','MDV':'MV','MLI':'ML','MLT':'MT','MHL':'MH',
    'MTQ':'MQ','MRT':'MR','MUS':'MU','MYT':'YT','MEX':'MX','FSM':'FM','MDA':'MD',
    'MCO':'MC','MNG':'MN','MSR':'MS','MAR':'MA','MOZ':'MZ','MMR':'MM','NAM':'NA',
    'NRU':'NR','NPL':'NP','NLD':'NL','ANT':'AN','NCL':'NC','NZL':'NZ','NIC':'NI',
    'NER':'NE','NGA':'NG','NIU':'NU','NFK':'NF','MNP':'MP','NOR':'NO','OMN':'OM',
    'PAK':'PK','PLW':'PW','PSE':'PS','PAN':'PA','PNG':'PG','PRY':'PY','PER':'PE',
    'PHL':'PH','PCN':'PN','POL':'PL','PRT':'PT','PRI':'PR','QAT':'QA','REU':'RE',
    'ROM':'RO','RUS':'RU','RWA':'RW','SHN':'SH','KNA':'KN','LCA':'LC','SPM':'PM',
    'VCT':'VC','WSM':'WS','SMR':'SM','STP':'ST','SAU':'SA','SEN':'SN','SCG':'CS',
    'SYC':'SC','SLE':'SL','SGP':'SG','SVK':'SK','SVN':'SI','SLB':'SB','SOM':'SO',
    'ZAF':'ZA','SGS':'GS','ESP':'ES','LKA':'LK','SDN':'SD','SUR':'SR','SJM':'SJ',
    'SWZ':'SZ','SWE':'SE','CHE':'CH','SYR':'SY','TWN':'TW','TJK':'TJ','TZA':'TZ',
    'THA':'TH','TLS':'TL','TGO':'TG','TKL':'TK','TON':'TO','TTO':'TT','TUN':'TN',
    'TUR':'TR','TKM':'TM','TCA':'TC','TUV':'TV','UGA':'UG','UKR':'UA','ARE':'AE',
    'GBR':'GB','USA':'US','UMI':'UM','URY':'UY','UZB':'UZ','VUT':'VU','VEN':'VE',
    'VNM':'VN','VGB':'VG','VIR':'VI','WLF':'WF','ESH':'EH','YEM':'YE','ZMB':'ZM',
    'ZWE':'ZW',
}

# ══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_upload_ext(raw: str) -> str:
    if not raw:
        return ''
    e = raw.lower().strip()
    for ch in '\r\n\t\v\x00':
        e = e.replace(ch, '')
    e = e.split('?', 1)[0].split('#', 1)[0].strip('.')
    return e


def _normalize_mimetype(m: str) -> str:
    if not m:
        return ''
    return m.split(';')[0].strip().lower()


def _sniff_image_extension(stream) -> str | None:
    pos = 0
    try:
        if hasattr(stream, 'tell'):
            pos = stream.tell()
        head = stream.read(32)
    except Exception:
        return None
    finally:
        try:
            stream.seek(pos)
        except Exception:
            pass
    if len(head) < 4:
        return None
    if head.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if head.startswith(b'GIF87a') or head.startswith(b'GIF89a'):
        return 'gif'
    if len(head) >= 12 and head.startswith(b'RIFF') and head[8:12] == b'WEBP':
        return 'webp'
    if head.startswith(b'BM'):
        return 'bmp'
    if head.startswith(b'II*\x00') or head.startswith(b'MM\x00*'):
        return 'tiff'
    if len(head) >= 12 and head[4:8] == b'ftyp':
        brand = head[8:12]
        if brand in (b'heic', b'heix', b'heim', b'heis', b'mif1', b'msf1'):
            return 'heic'
        if brand == b'avif':
            return 'avif'
    return None


def get_image_extension_for_upload(file) -> str | None:
    name = (getattr(file, 'filename', None) or '').strip()
    if name and '.' in name:
        ext = _normalize_upload_ext(name.rsplit('.', 1)[1])
        ext = _EXT_CANONICAL.get(ext, ext)
        if ext in ALLOWED_EXTENSIONS:
            return ext
    mime = _normalize_mimetype(
        getattr(file, 'mimetype', None) or getattr(file, 'content_type', None) or ''
    )
    ext = _MIME_TO_EXT.get(mime)
    if ext:
        ext = _EXT_CANONICAL.get(ext, ext)
        if ext in ALLOWED_EXTENSIONS:
            return ext
    try:
        stream = getattr(file, 'stream', None) or file
        sniff = _sniff_image_extension(stream)
        if sniff:
            sniff = _EXT_CANONICAL.get(sniff, sniff)
            if sniff in ALLOWED_EXTENSIONS:
                return sniff
    except Exception:
        pass
    return None


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def parse_date_safe(raw: str) -> str | None:
    if not raw:
        return None
    raw = str(raw).strip()
    parts = re.findall(r'\d+', raw)
    if not parts:
        return None
    try:
        if len(parts) == 1 and len(parts[0]) == 6:
            s = parts[0]
            yy, mm, dd = int(s[:2]), int(s[2:4]), int(s[4:6])
            yyyy = 2000 + yy if yy < 40 else 1900 + yy
        elif len(parts) >= 3:
            p0, p1, p2 = parts[0], parts[1], parts[2]
            if len(p0) == 4:
                yyyy, mm, dd = int(p0), int(p1), int(p2)
            else:
                dd, mm, yyyy = int(p0), int(p1), int(p2)
                if mm > 12 and dd <= 12:
                    dd, mm = mm, dd
                if yyyy < 100:
                    yyyy = 2000 + yyyy if yyyy < 40 else 1900 + yyyy
        else:
            return None
        valid = date(yyyy, mm, dd)
        return valid.strftime("%Y-%m-%d")
    except (ValueError, OverflowError) as e:
        log.warning(f"parse_date_safe failed for '{raw}': {e}")
        return None


def read_json(path: str, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.error(f"Failed to read {path}: {e}")
        return default if default is not None else []


def write_json(path: str, data) -> bool:
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except OSError as e:
        log.error(f"Failed to write {path}: {e}")
        return False


STUDENT_FIELD_MAP = {
    'updated_passport': 'رقم الجواز',
    'updated_nat':      'الجنسية',
    'updated_dob':      'تاريخ الميلاد',
    'updated_exp':      'تاريخ انتهاء الجواز',
    'updated_phone':    'رقم التليفون',
    'updated_arabic':   'الإسم بالعربي',
    'updated_address':  'العنوان',
}


def apply_field_updates(student: dict, source) -> dict:
    for key, ar_key in STUDENT_FIELD_MAP.items():
        val = source.get(key)
        if val:
            student[ar_key] = val
    full_name = (source.get('updated_name') or '').strip()
    if full_name:
        parts = full_name.split()
        student['اللقب']  = parts[-1] if len(parts) > 1 else ''
        student['الأسماء'] = ' '.join(parts[:-1]) if len(parts) > 1 else full_name
    return student


def find_student_by_passport(passport_no: str) -> tuple:
    students = read_json(JSON_FILE, [])
    code = passport_no.strip().upper()
    idx = next(
        (i for i, s in enumerate(students)
         if str(s.get('رقم الجواز', '')).upper() == code),
        -1
    )
    return students, idx


def _resolve_date(student_data: dict, ar_key: str, vals_key: str, vals: dict) -> tuple:
    raw = student_data.get(ar_key, '')
    if not raw:
        return True, None
    parsed = parse_date_safe(raw)
    if parsed:
        vals[vals_key] = parsed
        return True, None
    log.warning(f"{ar_key} غير صحيح: {raw}")
    return False, f"⚠️ {ar_key} غير صحيح ({raw})"


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return jsonify({'success': False, 'error': 'غير مصرح'}), 401
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════════════════════
# Odoo Integration
# ══════════════════════════════════════════════════════════════════════════════

def _get_odoo_connection():
    ctx = ssl._create_unverified_context()
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common', context=ctx)
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    if not uid:
        raise ConnectionError("فشل التحقق من بيانات Odoo")
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object', context=ctx)
    return uid, models


def find_country_id(country_code: str):
    if not country_code:
        return False
    try:
        code = str(country_code).strip().upper()
        if len(code) == 3 and code in ISO_MAPPING:
            code = ISO_MAPPING[code]
        
        if os.path.exists('odoo_constants.json'):
            try:
                with open('odoo_constants.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    countries = data.get('countries', [])
                    for c in countries:
                        if c.get('code') == code:
                            return c['id']
                    for c in countries:
                        if code in str(c.get('name', '')).upper():
                            return c['id']
            except Exception as json_err:
                log.warning(f"Local country lookup error: {json_err}")
        return False
    except Exception as e:
        log.warning(f"find_country_id error: {e}")
        return False


def sync_to_odoo(student_data: dict, branch_id=None, category_id=None):
    try:
        uid, models = _get_odoo_connection()

        arabic_name     = student_data.get('الإسم بالعربي') or 'طالب جديد'
        passport_surname = student_data.get('اللقب') or ''
        passport_given  = student_data.get('الأسماء') or ''
        passport_no     = student_data.get('رقم الجواز') or ''

        vals: dict = {
            'name':         arabic_name,
            'arabic_name':  arabic_name,
            'first_name':   passport_given,
            'last_name':    passport_surname,
            'passport_no':  passport_no or False,
            'email':        student_data.get('الإيميل') or False,
            'phone':        student_data.get('رقم التليفون') or False,
            'mobile':       student_data.get('رقم الواتساب') or student_data.get('رقم التليفون') or False,
            'street':       student_data.get('العنوان') or False,
        }

        gender_raw = str(student_data.get('الجنس') or '').lower()
        if gender_raw in ('male', 'm'):
            vals['gender'] = 'm'
        elif gender_raw in ('female', 'f'):
            vals['gender'] = 'f'

        vals['category_id'] = int(category_id) if category_id else DEFAULT_CATEGORY_ID

        ok, err = _resolve_date(student_data, 'تاريخ الميلاد',        'birth_date',           vals)
        if not ok: return False, err

        ok, err = _resolve_date(student_data, 'تاريخ انتهاء الجواز', 'passport_expiry_date', vals)
        if not ok: return False, err

        nat_val = student_data.get('الجنسية')
        if nat_val:
            if str(nat_val).isdigit():
                vals['nationality'] = int(nat_val)
            else:
                c_id = find_country_id(str(nat_val))
                if c_id:
                    vals['nationality'] = c_id

        passport_img = student_data.get('صورة الجواز', '')
        if passport_img:
            img_path = os.path.join(UPLOAD_FOLDER, passport_img)
            if os.path.exists(img_path):
                with open(img_path, 'rb') as f:
                    vals['passport_attachment'] = base64.b64encode(f.read()).decode()

        b_id = int(branch_id) if branch_id else student_data.get('branch_id') or ODOO_BRANCH_ID
        vals['company_id'] = b_id

        vals = {k: (v if v is not None else False) for k, v in vals.items()}

        existing = []
        if passport_no:
            existing = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'op.student',
                                         'search', [[['passport_no', '=', passport_no]]])

        if existing:
            models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'op.student', 'write',
                               [existing, vals])
            new_id = existing[0]
            log.info(f"✏️ Updated student in Odoo: ID={new_id}")
        else:
            new_id = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'op.student', 'create',
                                        [vals])
            log.info(f"✅ Created student in Odoo: ID={new_id}")

        if not new_id:
            return False, "فشل إنشاء السجل في Odoo"

        return str(new_id), {}

    except Exception as e:
        import traceback
        log.error(f"❌ Odoo Sync Error: {e}")
        traceback.print_exc()
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# Passport Extraction — Optimized Hybrid Engine
# ══════════════════════════════════════════════════════════════════════════════




def process_passport_image(image_path):
    """استخراج بيانات MRZ من صورة الجواز (المحرك القديم الأصلي)"""
    try:
        import re
        time.sleep(0.5)
        img = Image.open(image_path)
        
        # ⭐ تعديل جديد: تكبير الصورة 3x لتحسين القراءة (من النسخة الجديدة)
        w, h = img.size
        if min(w, h) < 1200:
            img = img.resize((w * 3, h * 3), Image.Resampling.LANCZOS)
            log.info(f"📐 تم تكبير الصورة 3x: {w}x{h} → {w*3}x{h*3}")

        # تحسين الصورة - المحرك القديم
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        
        def find_mrz(image_to_scan):
            for psm in ['--psm 6', '--psm 3', '--psm 11']:
                try:
                    raw_text = pytesseract.image_to_string(image_to_scan, lang='eng', config=psm)
                    lines = [line.replace(" ", "").strip().upper() for line in raw_text.split('\n')]
                    potential_lines = []
                    for l in lines:
                        if len(l) >= 30 and (l.count('<') >= 2 or len(re.findall(r'[A-Z0-9]', l)) >= 25):
                            potential_lines.append(l)
                    if len(potential_lines) >= 2:
                        return potential_lines[-2:]
                except: continue
            return None

        mrz_pair = find_mrz(img)
        if not mrz_pair:
            width, height = img.size
            img_bottom = img.crop((0, int(height * 0.6), width, height))
            mrz_pair = find_mrz(img_bottom)

        if mrz_pair:
            line1, line2 = mrz_pair
            
            def clean_mrz_line(l):
                for char in '({[]})|\\/':
                    l = l.replace(char, '<')
                return re.sub(r'[^A-Z0-9<]', '', l.upper())

            line1 = clean_mrz_line(line1)[:44].ljust(44, '<')
            line2 = clean_mrz_line(line2)[:44].ljust(44, '<')
            
            def safe_get(obj, attr, default=""):
                val = getattr(obj, attr, default)
                if val is None: val = ""
                res = str(val).replace("<", " ").strip()
                return "" if res.lower() == "none" else res

            def fmt_date_to_iso(d):
                """تحويل YYMMDD إلى YYYY-MM-DD للفرونت إيند"""
                if d and len(str(d)) == 6:
                    s = str(d)
                    try:
                        yy, mm, dd = int(s[:2]), int(s[2:4]), int(s[4:6])
                        curr_yy = datetime.now().year % 100
                        yyyy = 2000 + yy if yy <= curr_yy + 15 else 1900 + yy
                        return f"{yyyy}-{mm:02d}-{dd:02d}"
                    except: return s
                return d or ""

            try:
                log.info(f"🔍 Processing MRZ:\n1: {line1}\n2: {line2}")
                if MRZ_AVAILABLE:
                    checker = TD3CodeChecker(f"{line1}\n{line2}")
                    fields = checker.fields()
                    raw_nat = getattr(fields, 'nationality', '') or getattr(fields, 'country', '') or ""
                    s = safe_get(fields, 'surname')
                    g = safe_get(fields, 'name') or safe_get(fields, 'given_names')
                    
                    if not s and not g: raise Exception("Empty names")

                    res = {
                        "success": True,
                        "surname": s,
                        "given_names": g,
                        "passport_number": safe_get(fields, 'document_number').replace(' ', ''),
                        "nationality": str(raw_nat).replace('<', '').strip(),
                        "birth_date": fmt_date_to_iso(getattr(fields, 'birth_date', '')),
                        "expiry_date": fmt_date_to_iso(getattr(fields, 'expiry_date', '')),
                        "gender": (getattr(fields, 'sex', '') or '').strip(),
                        "extract_quality": "ok"
                    }
                    res['nationality_code2'] = ISO_MAPPING.get(res['nationality'], res['nationality'])
                    return res
            except Exception as e:
                log.warning(f"Manual fallback active: {e}")
                try:
                    name_part = line1[5:]
                    parts = name_part.split('<<') if '<<' in name_part else name_part.split('<')
                    s = parts[0].replace('<', ' ').strip()
                    g = " ".join(parts[1:]).replace('<', ' ').strip() if len(parts) > 1 else ""
                    
                    nat = ""
                    m = re.search(r'[A-Z]{3}', line2[10:18])
                    if m: nat = m.group()
                    else:
                        m1 = re.search(r'[A-Z]{3}', line1[2:5])
                        nat = m1.group() if m1 else re.sub(r'[^A-Z]', '', line1[2:5])
                    
                    res = {
                        "success": True,
                        "surname": s if s and s.lower() != "none" else "",
                        "given_names": g if g and g.lower() != "none" else "",
                        "passport_number": line2[:9].replace('<', ''),
                        "nationality": nat,
                        "birth_date": fmt_date_to_iso(line2[13:19]),
                        "expiry_date": fmt_date_to_iso(line2[21:27]),
                        "gender": line2[20] if len(line2) > 20 else "",
                        "note": "⚠️ تم التحليل يدوياً"
                    }
                    res['nationality_code2'] = ISO_MAPPING.get(res['nationality'], res['nationality'])
                    return res
                except: pass
        
        return {"success": False, "error": "لم يتم العثور على منطقة MRZ بوضوح. حاول التصوير من قريب."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# Waiting List
# ══════════════════════════════════════════════════════════════════════════════

def add_to_waiting_list(name: str) -> str:
    data = read_json(WAITING_LIST_FILE, {"next_number": 1, "students": []})
    if not isinstance(data, dict):
        data = {"next_number": 1, "students": []}
    queue_num = f"{data.get('next_number', 1):03d}"
    data.setdefault('students', []).append({"name": name, "queue_number": queue_num})
    data['next_number'] = data.get('next_number', 1) + 1
    if write_json(WAITING_LIST_FILE, data):
        log.info(f"🔢 Waiting queue: {name} → #{queue_num}")
        return queue_num
    return "000"


# ══════════════════════════════════════════════════════════════════════════════
# Student JSON Storage
# ══════════════════════════════════════════════════════════════════════════════

def save_to_json(student_data: dict) -> dict:
    p_num = str(student_data.get('passport_number') or '').strip().upper()
    if not p_num:
        return {"success": False, "error": "رقم الجواز مطلوب"}
    for attempt in range(3):
        try:
            students = read_json(JSON_FILE, [])
            if any(str(s.get('رقم الجواز', '')).upper() == p_num for s in students):
                log.warning(f"Duplicate passport: {p_num}")
                return {"success": False, "error": "هذا الطالب مسجل سابقاً — الرجاء التوجه لقسم التسجيل"}
            q_data = read_json(WAITING_LIST_FILE, {"next_number": 1})
            if not isinstance(q_data, dict):
                q_data = {"next_number": 1}
            queue_num = f"{q_data.get('next_number', 1):03d}"
            entry = {
                "اللقب":              student_data.get('surname', ''),
                "الأسماء":            student_data.get('given_names', ''),
                "رقم الجواز":         p_num,
                "الجنسية":            student_data.get('nationality', ''),
                "تاريخ الميلاد":     student_data.get('birth_date', ''),
                "تاريخ انتهاء الجواز": student_data.get('expiry_date', ''),
                "رقم التليفون":       student_data.get('phone', ''),
                "رقم الواتساب":       student_data.get('whatsapp', ''),
                "الإيميل":            student_data.get('email', ''),
                "الإسم بالعربي":      student_data.get('name_arabic', ''),
                "العنوان":            student_data.get('address', ''),
                "الجنس":              student_data.get('gender', ''),
                "صورة الجواز":        student_data.get('photo_passport', ''),
                "صورة الإقامة":       student_data.get('photo_id', ''),
                "رقم_الانتظار":       queue_num,
                "تاريخ التسجيل":      datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            students.append(entry)
            if write_json(JSON_FILE, students):
                log.info(f"✅ Saved student: {p_num} — Total: {len(students)}")
                return {"success": True, "student_code": p_num, "queue_number": queue_num}
            else:
                raise OSError("فشل الكتابة للملف")
        except Exception as e:
            log.warning(f"Save attempt {attempt+1} failed: {e}")
            if attempt == 2:
                return {"success": False, "error": str(e)}
            time.sleep(0.1)
    return {"success": False, "error": "فشل الحفظ بعد 3 محاولات"}


# ══════════════════════════════════════════════════════════════════════════════
# Flask Routes — Static Pages
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    if MAINTENANCE_MODE:
        return redirect('/maintenance')
    return send_from_directory('static', 'index.html')

@app.route('/admin')
def admin():
    if 'admin_logged_in' not in session:
        return redirect('/admin-login')
    return send_from_directory('static', 'admin.html')

@app.route('/admin-login')
def admin_login_page():
    return send_from_directory('static', 'admin-login.html')

@app.route('/waiting')
def waiting_screen():
    return send_from_directory('static', 'waiting.html')

@app.route('/maintenance')
def maintenance():
    return send_from_directory('static', 'maintenance.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ══════════════════════════════════════════════════════════════════════════════
# Flask Routes — Auth
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin-auth', methods=['POST'])
def admin_auth():
    u = request.form.get('username', '')
    p = request.form.get('password', '')
    if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'بيانات الدخول غير صحيحة'})

@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin-login')


# ══════════════════════════════════════════════════════════════════════════════
# Flask Routes — API
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/extract-passport', methods=['POST'])
def extract_passport():
    filename    = None
    id_filename = None
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "لم يتم رفع ملف"}), 400
        file    = request.files['file']
        id_file = request.files.get('id_file')
        passport_ext = get_image_extension_for_upload(file)
        if not passport_ext:
            return jsonify({"success": False, "error": "عذراً، هذا الملف لا يبدو كصورة صالحة."}), 400
        ts = int(time.time() * 1000)
        filename = f"passport_{ts}.{passport_ext}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            file.seek(0)
        except Exception:
            pass
        file.save(path)
        if id_file:
            id_ext = get_image_extension_for_upload(id_file)
            if id_ext:
                try:
                    id_file.seek(0)
                except Exception:
                    pass
                id_filename = f"id_{ts}.{id_ext}"
                id_file.save(os.path.join(UPLOAD_FOLDER, id_filename))
        result = process_passport_image(path)
        result['file_name']    = filename
        result['id_file_name'] = id_filename
        return jsonify(result)
    except Exception as e:
        log.error(f"extract_passport error: {e}")
        return jsonify({"success": False, "error": str(e), "file_name": filename, "id_file_name": id_filename})


@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"success": False, "error": "لا توجد بيانات"}), 400
        passport_number = str(data.get('passport_number') or '').strip().upper()
        if not passport_number:
            return jsonify({"success": False, "error": "رقم الجواز مطلوب"}), 400
        result = save_to_json(data)
        if not result.get('success'):
            return jsonify(result), 400
        name_arabic = (data.get('name_arabic') or
                       f"{data.get('given_names', '')} {data.get('surname', '')}".strip())
        queue_number = add_to_waiting_list(name_arabic)
        students = read_json(JSON_FILE, [])
        for s in students:
            if str(s.get('رقم الجواز', '')).upper() == passport_number:
                s['رقم_الانتظار'] = queue_number
                break
        write_json(JSON_FILE, students)
        return jsonify({"success": True, "student_code": passport_number, "queue_number": queue_number})
    except Exception as e:
        log.error(f"register error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/waiting-list', methods=['GET'])
def get_waiting_list():
    data = read_json(WAITING_LIST_FILE, {"students": []})
    return jsonify({"success": True, "students": data.get('students', []) if isinstance(data, dict) else []})


@app.route('/api/call-student', methods=['POST'])
def call_student():
    try:
        data     = request.get_json()
        passport = str(data.get('passport') or '').strip().upper()
        if not passport:
            return jsonify({"success": False, "error": "رقم الجواز مطلوب"})
        students, idx = find_student_by_passport(passport)
        if idx == -1:
            return jsonify({"success": False, "error": "الطالب غير موجود"})
        student   = students[idx]
        name      = student.get('الإسم بالعربي') or student.get('الأسماء') or '---'
        queue_num = student.get('رقم_الانتظار') or '---'
        q_data = read_json(WAITING_LIST_FILE, {"next_number": 1, "students": []})
        if not isinstance(q_data, dict):
            q_data = {"next_number": 1, "students": []}
        q_data['students'] = [s for s in q_data.get('students', []) if s.get('name') != name]
        q_data['students'].insert(0, {"name": name, "queue_number": queue_num})
        write_json(WAITING_LIST_FILE, q_data)
        return jsonify({"success": True, "name": name, "queue_number": queue_num})
    except Exception as e:
        log.error(f"call_student error: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/reset-waiting-list', methods=['POST'])
@admin_required
def reset_waiting_list():
    write_json(WAITING_LIST_FILE, {"next_number": 1, "students": []})
    return jsonify({"success": True})


@app.route('/api/list-students', methods=['GET'])
@admin_required
def list_students():
    students = read_json(JSON_FILE, [])
    pending  = [s for s in students if not s.get('odoo_student_code') or
                str(s.get('odoo_student_code')).lower() in ('true', 'false', '')]
    pending.reverse()
    return jsonify({'success': True, 'students': pending})


@app.route('/api/search-student', methods=['GET'])
def search_student():
    code = str(request.args.get('code') or '').strip().upper()
    if not code:
        return jsonify({"success": False, "error": "كود الطالب مطلوب"}), 400
    students, idx = find_student_by_passport(code)
    if idx == -1:
        return jsonify({"success": False, "error": "لم يتم العثور على الطالب"}), 404
    return jsonify({"success": True, "data": students[idx]})


@app.route('/api/update-student', methods=['POST'])
def update_student():
    try:
        data    = request.get_json()
        p_code  = str(data.get('student_code') or '').strip().upper()
        if not p_code:
            return jsonify({"success": False, "error": "رقم الجواز مطلوب"})
        students, idx = find_student_by_passport(p_code)
        if idx == -1:
            return jsonify({"success": False, "error": "الطالب غير موجود"})
        students[idx] = apply_field_updates(students[idx], data)
        students[idx]['تاريخ التعديل'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        write_json(JSON_FILE, students)
        return jsonify({"success": True})
    except Exception as e:
        log.error(f"update_student error: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/print-application', methods=['POST'])
@admin_required
def print_application():
    student_code = str(request.form.get('student_code') or '').strip().upper()
    branch_id    = request.form.get('branch_id')
    category_id  = request.form.get('category_id')
    if not student_code:
        return jsonify({'success': False, 'error': 'رقم الجواز مطلوب'})
    try:
        students, idx = find_student_by_passport(student_code)
        if idx == -1:
            return jsonify({'success': False, 'error': 'الطالب غير موجود'})
        students[idx] = apply_field_updates(students[idx], request.form)
        odoo_name, sync_report = sync_to_odoo(students[idx], branch_id=branch_id, category_id=category_id)
        if odoo_name:
            students[idx]['odoo_student_code'] = odoo_name
        write_json(JSON_FILE, students)
        if odoo_name:
            return jsonify({'success': True, 'data': students[idx], 'odoo_student_code': odoo_name, 'sync_report': sync_report})
        else:
            return jsonify({'success': False, 'error': f'فشلت المزامنة: {sync_report}'})
    except Exception as e:
        log.error(f"print_application error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/odoo-data', methods=['GET'])
def get_odoo_data():
    try:
        if os.path.exists('odoo_constants.json'):
            with open('odoo_constants.json', 'r', encoding='utf-8') as f:
                constants = json.load(f)
            return jsonify({'success': True, 'branches': constants.get('branches', []),
                           'categories': constants.get('categories', []),
                           'countries': constants.get('countries', []), 'source': 'local'})
        return jsonify({'success': False, 'error': 'ملف البيانات المحلية غير موجود'})
    except Exception as e:
        log.error(f"get_odoo_data error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/toggle-maintenance', methods=['POST'])
@admin_required
def toggle_maintenance():
    global MAINTENANCE_MODE
    MAINTENANCE_MODE = not MAINTENANCE_MODE
    return jsonify({'success': True, 'maintenance_mode': MAINTENANCE_MODE})


@app.route('/api/qrcode')
def generate_qrcode():
    ip  = get_local_ip()
    url = f"http://{ip}:5000/"
    qr  = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#00c8ff", back_color="#0a0e1a")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return Response(buf.read(), mimetype='image/png')


@app.route('/api/server-url')
def server_url():
    ip = get_local_ip()
    return jsonify({"url": f"http://{ip}:5000/", "ip": ip})


@app.route('/api/print-qrcodes', methods=['POST'])
@admin_required
def print_qrcodes():
    students = read_json(JSON_FILE, [])
    return jsonify({'success': True, 'students': students})


# ══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ip = get_local_ip()
    print(f"\n{'='*55}")
    print(f"  Fajr Center - Registration System v4.5")
    print(f"  Optimized Hybrid Engine (3x Upscale)")
    print(f"  http://{ip}:5000")
    print(f"  Admin: http://{ip}:5000/admin-login")
    print(f"  Waiting: http://{ip}:5000/waiting")
    print(f"{'='*55}\n")
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)