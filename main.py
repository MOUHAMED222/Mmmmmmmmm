import json
import html
import os
import time
import uuid
import subprocess
import threading
import logging
import csv
import io
import zipfile
import re
import ast
import importlib.util
import sys
import shlex
import shutil
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List, Set
from logging.handlers import RotatingFileHandler

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

# ===================== إعدادات التسجيل (Logging) مع التدوير =====================
LOG_FILE = os.path.join("logs", "bot.log")
os.makedirs("logs", exist_ok=True)

handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        handler,
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===================== الإعدادات العامة =====================
USER_DATA_DIR = os.path.abspath("user_data")
BOT_TOKEN = "8663385334:AAEYioH6NxjOIw7O66Y4EuD_1CcK049XVpI"
ADMIN_ID = 8523524013
BOT_USERNAME = "@HOST_1_1_1bot"
CONTACT_USERNAME = "@mouhamed_ma"
BACKUP_CHANNEL = "@ToolsforHumanitydoubleyourwe"
VIP_CHANNEL_ID = "@ToolsforHumanitydoubleyourwe"

DB_FILE = "bot_database.json"
UPLOADS_DIR = "uploads"
LOGS_DIR = "logs"
BACKUP_DIR = "backups"

for d in (UPLOADS_DIR, LOGS_DIR, BACKUP_DIR):
    os.makedirs(d, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ===================== نصوص القوانين والمساعدة =====================
RULES_TEXT = """
📜 <b>القوانين</b>

1. يمنع رفع ملفات تحتوي على محتوى غير قانوني.
2. يمنع استخدام البوت لأغراض ضارة أو تخريبية.
3. يحق للإدارة حظر أي مستخدم يخالف القوانين.
4. يجب الالتزام بسياسة الاستخدام العادل.
5. أي انتهاك للقوانين يعرض حسابك للحظر الفوري.

شكرًا لالتزامك بالقوانين.
"""

HELP_TEXT = """
❓ <b>المساعدة</b>

🔹 <b>كيفية رفع ملف:</b>
- اضغط على زر "رفع ملف" وأرسل ملف .py / .js / .php / .zip.
- بعد الموافقة، سيتم تشغيل البوت تلقائياً.

🔹 <b>كيفية الحصول على نقاط:</b>
- يمكنك شراء نقاط من المتجر.
- ادعُ أصدقائك للحصول على مكافآت.
- خذ الهدية اليومية.

🔹 <b>مشكلة في البوت؟</b>
- تواصل مع الدعم عبر زر "الدعم" أو "استفسار".

🔹 <b>لماذا توقف بوتي؟</b>
- قد يكون بسبب نفاد الرصيد. اشحن نقاطك لإعادة التشغيل.

للمزيد من المساعدة، تواصل مع الإدارة.
"""

# ===================== نظام الحماية =====================
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("مكتبة cryptography غير مثبتة، نظام الحماية لن يعمل. يرجى تثبيتها: pip install cryptography")

SECURITY_KEY_FILE = "security.key"
INTEGRITY_FILE = "integrity.json"
DECRYPTED_TEMP_DIR = "temp_decrypted"
SECURITY_ACTIVATED = False

def get_or_create_security_key():
    if os.path.exists(SECURITY_KEY_FILE):
        with open(SECURITY_KEY_FILE, "rb") as f:
            key = f.read()
    else:
        if CRYPTO_AVAILABLE:
            key = Fernet.generate_key()
            with open(SECURITY_KEY_FILE, "wb") as f:
                f.write(key)
            os.chmod(SECURITY_KEY_FILE, 0o600)
            logger.info("تم توليد مفتاح أمان جديد.")
        else:
            key = None
    return key

def get_cipher():
    if not CRYPTO_AVAILABLE:
        return None
    key = get_or_create_security_key()
    if key:
        return Fernet(key)
    return None

def encrypt_data(data: bytes) -> bytes:
    cipher = get_cipher()
    if cipher:
        return cipher.encrypt(data)
    return data

def decrypt_data(data: bytes) -> bytes:
    cipher = get_cipher()
    if cipher:
        try:
            return cipher.decrypt(data)
        except Exception as e:
            logger.error(f"فشل فك التشفير: {e}")
            return data
    return data

def is_encrypted_file(filepath: str) -> bool:
    if not CRYPTO_AVAILABLE or not os.path.exists(filepath):
        return False
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        cipher = get_cipher()
        if cipher:
            cipher.decrypt(data)
            return True
        return False
    except:
        return False

def encrypt_file(filepath: str) -> bool:
    if not CRYPTO_AVAILABLE:
        return False
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        encrypted = encrypt_data(data)
        enc_path = filepath + ".enc"
        with open(enc_path, "wb") as f:
            f.write(encrypted)
        os.remove(filepath)
        logger.info(f"تم تشفير الملف: {filepath} -> {enc_path}")
        return True
    except Exception as e:
        logger.error(f"فشل تشفير الملف {filepath}: {e}")
        return False

def decrypt_file_to_temp(filepath: str) -> str:
    if not CRYPTO_AVAILABLE or not os.path.exists(filepath):
        return filepath
    if not filepath.endswith(".enc"):
        return filepath
    try:
        with open(filepath, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = decrypt_data(encrypted_data)
        os.makedirs(DECRYPTED_TEMP_DIR, exist_ok=True)
        original_name = os.path.basename(filepath).replace(".enc", "")
        temp_path = os.path.join(DECRYPTED_TEMP_DIR, original_name)
        with open(temp_path, "wb") as f:
            f.write(decrypted_data)
        logger.info(f"تم فك تشفير الملف إلى: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"فشل فك تشفير الملف {filepath}: {e}")
        return filepath

def calculate_file_hash(filepath: str) -> str:
    if not os.path.exists(filepath):
        return ""
    hash_sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"خطأ في حساب الهاش للملف {filepath}: {e}")
        return ""

def update_integrity():
    if not CRYPTO_AVAILABLE:
        return
    files_to_protect = [
        __file__,
        DB_FILE,
        SECURITY_KEY_FILE,
        "requirements.txt" if os.path.exists("requirements.txt") else None,
        ".env" if os.path.exists(".env") else None,
    ]
    integrity = {}
    for fpath in files_to_protect:
        if fpath and os.path.exists(fpath):
            integrity[fpath] = calculate_file_hash(fpath)
    if os.path.exists(UPLOADS_DIR):
        for root, _, files in os.walk(UPLOADS_DIR):
            for file in files:
                full_path = os.path.join(root, file)
                if full_path.endswith(".enc"):
                    integrity[full_path] = calculate_file_hash(full_path)
    try:
        with open(INTEGRITY_FILE, "w", encoding="utf-8") as f:
            json.dump(integrity, f, indent=2)
        logger.info("تم تحديث ملف السلامة.")
    except Exception as e:
        logger.error(f"فشل تحديث ملف السلامة: {e}")

def check_integrity():
    if not CRYPTO_AVAILABLE or not os.path.exists(INTEGRITY_FILE):
        return
    try:
        with open(INTEGRITY_FILE, "r", encoding="utf-8") as f:
            stored = json.load(f)
    except Exception as e:
        logger.error(f"فشل قراءة ملف السلامة: {e}")
        return

    issues = []
    for fpath, stored_hash in stored.items():
        if not os.path.exists(fpath):
            issues.append(f"⚠️ الملف مفقود: {fpath}")
            continue
        current_hash = calculate_file_hash(fpath)
        if current_hash != stored_hash:
            issues.append(f"⚠️ تغيير في الملف: {fpath}")
    if issues:
        alert_text = "🚨 <b>تحذير أمني!</b>\nتم اكتشاف تغييرات في الملفات:\n" + "\n".join(issues)
        logger.warning(alert_text)
        try:
            bot.send_message(ADMIN_ID, f"<blockquote>{alert_text}</blockquote>", parse_mode="HTML")
        except Exception as e:
            logger.error(f"فشل إرسال إشعار السلامة: {e}")
    else:
        logger.info("✅ جميع الملفات سليمة.")

def start_security_system():
    global SECURITY_ACTIVATED
    if SECURITY_ACTIVATED:
        return
    if not CRYPTO_AVAILABLE:
        logger.warning("نظام الحماية غير مفعل بسبب عدم توفر cryptography.")
        return

    logger.info("بدء نظام الحماية...")

    if os.path.exists(DB_FILE):
        if not is_encrypted_file(DB_FILE):
            logger.info("تشفير قاعدة البيانات...")
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = f.read()
            encrypted = encrypt_data(data.encode('utf-8'))
            with open(DB_FILE, "wb") as f:
                f.write(encrypted)
            logger.info("✅ تم تشفير قاعدة البيانات.")

    for f in [".env", "requirements.txt"]:
        if os.path.exists(f) and not is_encrypted_file(f):
            encrypt_file(f)

    update_integrity()
    check_integrity()

    SECURITY_ACTIVATED = True
    logger.info("✅ تم تفعيل نظام الحماية بنجاح.")

def clean_temp_decrypted_files():
    if os.path.exists(DECRYPTED_TEMP_DIR):
        shutil.rmtree(DECRYPTED_TEMP_DIR, ignore_errors=True)
        logger.info("تم تنظيف المجلد المؤقت.")

# ===================== قاعدة البيانات =====================
db_lock = threading.Lock()

STATUS_AR = {
    "pending": "⏳ قيد الانتظار",
    "approved": "✅ موافق عليه",
    "rejected": "❌ مرفوض",
    "running": "▶️ شغال",
    "stopped": "⏹️ متوقف"
}

# خريطة الامتدادات إلى الأيقونات
FILE_ICONS = {
    "py": "🐍",
    "js": "🟨",
    "php": "🐘",
    "zip": "📦",
    "default": "📄"
}

def load_db() -> Dict[str, Any]:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "rb") as f:
                raw_data = f.read()
            decrypted = decrypt_data(raw_data)
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            logger.warning(f"فشل فك تشفير قاعدة البيانات، محاولة قراءة كنص عادي: {e}")
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    return {
        "users": {},
        "files": {},
        "store": {
            "1": {"name": "100 نقطة", "points": 100, "price": "15نجمة"},
            "2": {"name": "300 نقطة", "points": 300, "price": "25نجمة"},
            "3": {"name": "600 نقطة", "points": 600, "price": "40نجمة"},
        },
        "orders": {},
        "settings": {
            "daily_cost": 10,
            "free_plan": True,
            "free_points": 50,
            "daily_gift": 5,
            "referral_bonus": 10,
            "channels": [],
            "welcome_photo": None,
            "welcome_message": "👋 مرحباً بك في بوت الاستضافة!",
            "support_account": "@mouhamed_ma",
            "trust_channel": None,
            "pinned_announcement": None,
            "vip_plans": [],
            "max_backups": 200
        },
        "admins": [ADMIN_ID]
    }

def save_db():
    with db_lock:
        json_str = json.dumps(db, ensure_ascii=False, indent=2)
        encrypted = encrypt_data(json_str.encode('utf-8'))
        with open(DB_FILE, "wb") as f:
            f.write(encrypted)

db = load_db()

def migrate_db():
    modified = False
    if "admins" not in db:
        db["admins"] = [ADMIN_ID]
        modified = True
    if "settings" not in db:
        db["settings"] = {}
        modified = True
    settings = db["settings"]
    defaults = {
        "daily_cost": 10,
        "free_plan": True,
        "free_points": 50,
        "daily_gift": 5,
        "referral_bonus": 10,
        "channels": [],
        "welcome_photo": None,
        "welcome_message": "👋 مرحباً بك في بوت الاستضافة!",
        "support_account": "@mouhamed_ma",
        "trust_channel": None,
        "pinned_announcement": None,
        "vip_plans": [],
        "max_backups": 200
    }
    for key, value in defaults.items():
        if key not in settings:
            settings[key] = value
            modified = True
    if modified:
        save_db()
        logger.info("تم ترقية قاعدة البيانات بالحقول الجديدة.")

migrate_db()

db["settings"]["free_points"] = 100
db["settings"]["referral_bonus"] = 15
db["settings"]["daily_cost"] = 10
db["settings"]["daily_gift"] = 10
save_db()
logger.info("تم تحديث الإعدادات: free_points=100, referral_bonus=15, daily_cost=10, daily_gift=10")

pending_action = {}
running_processes = {}
cooldown = {}
question_messages = {}
bot_enabled = True

# ===================== أدوات مساعدة =====================
def now_iso():
    return datetime.now().isoformat()

def short_id():
    return uuid.uuid4().hex[:8]

def is_admin(user_id):
    return int(user_id) in db.get("admins", [ADMIN_ID]) or int(user_id) == ADMIN_ID

def get_points(user_id):
    return db["users"].get(str(user_id), {}).get("points", 0)

def add_points(user_id, amount):
    uid = str(user_id)
    if uid in db["users"]:
        db["users"][uid]["points"] += amount
        save_db()

def get_user_name(user_id):
    uid = str(user_id)
    user_data = db["users"].get(uid)
    if user_data:
        return user_data.get("username") or f"مستخدم {uid}"
    return f"مستخدم {uid}"

def esc(value):
    return html.escape("" if value is None else str(value))

def q(text):
    return f"<blockquote>{text}</blockquote>"

def send_q(chat_id, text, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    return bot.send_message(chat_id, q(text), **kwargs)

def reply_q(message, text, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    return bot.reply_to(message, q(text), **kwargs)

def edit_q(text, chat_id, message_id, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    try:
        return bot.edit_message_text(q(text), chat_id, message_id, **kwargs)
    except Exception:
        try:
            return bot.edit_message_caption(caption=q(text), chat_id=chat_id, message_id=message_id, **kwargs)
        except Exception:
            raise

def get_user_photo_file_id(user_id):
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count and photos.photos:
            return photos.photos[0][-1].file_id
    except Exception as e:
        logger.warning(f"لم نتمكن من جلب صورة المستخدم {user_id}: {e}")
    return None

def send_user_card(chat_id, user_id, caption, reply_markup=None):
    photo_id = get_user_photo_file_id(user_id)
    if photo_id:
        try:
            return bot.send_photo(
                chat_id,
                photo_id,
                caption=q(caption),
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"فشل إرسال الصورة للمستخدم {user_id}: {e}")
    return bot.send_message(
        chat_id,
        q(caption),
        reply_markup=reply_markup,
        parse_mode="HTML",
    )

def send_admin_user_card(chat_id, user_id, caption, reply_markup=None):
    return send_user_card(chat_id, user_id, caption, reply_markup=reply_markup)

def update_last_activity(user_id):
    uid = str(user_id)
    if uid in db["users"]:
        db["users"][uid]["last_activity"] = now_iso()
        save_db()

def is_user_banned(user_id):
    uid = str(user_id)
    return db["users"].get(uid, {}).get("banned", False)

def ensure_user(user_id, username=None, ref_by=None):
    uid = str(user_id)
    is_new = uid not in db["users"]
    if is_new:
        db["users"][uid] = {
            "username": username or "",
            "points": db["settings"]["free_points"],
            "joined": now_iso(),
            "referred_by": ref_by,
            "referrals": 0,
            "last_daily": None,
            "banned": False,
            "last_activity": now_iso()
        }

        if ref_by and ref_by != uid and ref_by in db["users"]:
            bonus = db["settings"]["referral_bonus"]
            db["users"][ref_by]["points"] += bonus
            db["users"][ref_by]["referrals"] += 1
            try:
                bot.send_message(
                    int(ref_by),
                    q(
                        "🎉 انضم مستخدم جديد عبر رابط دعوتك.\n"
                        f"🎁 تمت إضافة {bonus} نقطة إلى رصيدك.\n"
                        "🚀 استمر في الدعوات لتحصل على مكافآت أكثر."
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"فشل إرسال إشعار الإحالة للمُحيل {ref_by}: {e}")

        try:
            reg_caption = (
                "🆕 مستخدم جديد سجّل في البوت.\n\n"
                f"🆔 الآيدي: {uid}\n"
                f"👤 الاسم: {esc(username or 'بدون اسم')}\n"
                f"🔗 تمت الإحالة: {esc(ref_by or 'لا يوجد')}\n"
                f"💎 الرصيد الافتتاحي: {db['settings']['free_points']} نقطة"
            )
            send_admin_user_card(ADMIN_ID, user_id, reg_caption)
        except Exception as e:
            logger.error(f"فشل إرسال إشعار التسجيل للأدمن: {e}")

        save_db()
    elif username:
        db["users"][uid]["username"] = username
    return db["users"][uid]

def check_force_sub(user_id):
    channels = db["settings"]["channels"]
    if not channels:
        return True, []
    not_joined = []
    for ch in channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked"):
                not_joined.append(ch)
        except Exception as e:
            logger.warning(f"فشل التحقق من اشتراك {user_id} في القناة {ch}: {e}")
            not_joined.append(ch)
    return len(not_joined) == 0, not_joined

def clean_orphaned_files():
    if not os.path.exists(UPLOADS_DIR):
        return
    for filename in os.listdir(UPLOADS_DIR):
        filepath = os.path.join(UPLOADS_DIR, filename)
        found = False
        for fid, f in db["files"].items():
            if f.get("path") == filepath:
                found = True
                break
        if not found:
            try:
                os.remove(filepath)
                logger.info(f"تم حذف الملف اليتيم: {filepath}")
            except Exception as e:
                logger.error(f"فشل حذف الملف اليتيم {filepath}: {e}")

def cleanup_missing_files_from_db():
    to_remove = []
    for fid, f in db["files"].items():
        filepath = f.get("path")
        if filepath and not os.path.exists(filepath):
            logger.warning(f"الملف غير موجود: {filepath}، سيتم إزالة الإدخال {fid}")
            to_remove.append(fid)
    for fid in to_remove:
        db["files"].pop(fid, None)
    if to_remove:
        save_db()
        logger.info(f"تم إزالة {len(to_remove)} إدخالاً للملفات غير الموجودة.")

# ===================== دوال قناة الثقة =====================
def _parse_chat_identifier(raw):
    s = raw.strip()
    if s.startswith('@'):
        try:
            chat = bot.get_chat(s)
            return chat.id
        except Exception as e:
            logger.warning(f"فشل الحصول على معرف القناة من {s}: {e}")
            return s
    try:
        return int(s)
    except ValueError:
        return s

def verify_and_set_trust_channel(channel_input):
    if not channel_input:
        return False, "❌ لم يتم إدخال معرف القناة."

    chat_id = _parse_chat_identifier(channel_input)

    try:
        chat = bot.get_chat(chat_id)
        if not chat:
            return False, "❌ القناة غير موجودة (تأكد من المعرف)."

        bot_member = bot.get_chat_member(chat_id, bot.get_me().id)
        if bot_member.status in ("left", "kicked"):
            return False, "❌ البوت ليس عضواً في القناة. يرجى إضافة البوت كعضو (مع صلاحية إرسال الرسائل) ثم المحاولة مرة أخرى."

        try:
            bot.send_message(chat_id, "📡 تم تفعيل قناة الثقة بنجاح.", parse_mode="HTML")
        except ApiTelegramException as e:
            if e.error_code == 403:
                return False, "❌ البوت ليس لديه صلاحية إرسال الرسائل في القناة. يرجى منحه صلاحية 'إرسال الرسائل'."
            else:
                return False, f"❌ فشل إرسال رسالة الاختبار: {e.description}"

        return True, f"✅ تم تفعيل قناة الثقة بنجاح (المعرف: {chat_id})."

    except ApiTelegramException as e:
        error_code = e.error_code
        description = e.description
        if error_code == 400:
            if "chat not found" in description:
                return False, "❌ القناة غير موجودة (تأكد من المعرف)."
            else:
                return False, f"❌ طلب غير صحيح: {description}"
        elif error_code == 403:
            return False, "❌ البوت ليس لديه صلاحية الوصول إلى القناة (Forbidden). تأكد من أنه عضو ولديه الصلاحيات."
        else:
            return False, f"❌ خطأ في Telegram API (كود {error_code}): {description}"
    except Exception as e:
        logger.error(f"خطأ غير متوقع في verify_and_set_trust_channel: {e}")
        return False, f"❌ خطأ غير متوقع: {str(e)}"

def send_to_trust_channel(text):
    channel_setting = db["settings"].get("trust_channel")
    if not channel_setting:
        return

    chat_id = _parse_chat_identifier(channel_setting)

    try:
        bot.send_message(chat_id, q(text), parse_mode="HTML")
        logger.info(f"تم النشر في قناة الثقة: {channel_setting}")
    except ApiTelegramException as e:
        error_code = e.error_code
        description = e.description
        logger.error(f"فشل النشر في قناة الثقة {channel_setting}: كود {error_code} - {description}")
        try:
            if error_code == 400 and "chat not found" in description:
                admin_msg = f"⚠️ فشل النشر في قناة الثقة ({channel_setting}).\nالسبب: القناة غير موجودة (تأكد من المعرف).\nالرسالة: {text[:200]}..."
            elif error_code == 403:
                admin_msg = f"⚠️ فشل النشر في قناة الثقة ({channel_setting}).\nالسبب: البوت ليس لديه صلاحية الإرسال (Forbidden).\nالرسالة: {text[:200]}..."
            elif error_code == 400 and "bot is not a member" in description:
                admin_msg = f"⚠️ فشل النشر في قناة الثقة ({channel_setting}).\nالسبب: البوت ليس عضواً في القناة.\nالرسالة: {text[:200]}..."
            else:
                admin_msg = f"⚠️ فشل النشر في قناة الثقة ({channel_setting}).\nالسبب: كود {error_code} - {description}\nالرسالة: {text[:200]}..."
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
        except:
            pass
    except Exception as e:
        logger.error(f"فشل النشر في قناة الثقة {channel_setting}: {e}")
        try:
            bot.send_message(ADMIN_ID, f"⚠️ فشل النشر في قناة الثقة ({channel_setting}).\nالسبب: {str(e)}\nالرسالة: {text[:200]}...", parse_mode="HTML")
        except:
            pass

def send_to_vip_channel(text):
    if VIP_CHANNEL_ID is None:
        return
    try:
        bot.send_message(VIP_CHANNEL_ID, q(text), parse_mode="HTML")
        logger.info(f"تم الإرسال إلى قناة VIP: {VIP_CHANNEL_ID}")
    except Exception as e:
        logger.error(f"فشل الإرسال إلى قناة VIP: {e}")

def export_orders_to_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["رقم الطلب", "المستخدم", "اسم المنتج", "السعر", "النقاط", "الحالة", "التاريخ"])
    for oid, order in db["orders"].items():
        item = db["store"].get(order["item_id"], {})
        user_info = db["users"].get(order["user"], {})
        writer.writerow([
            oid,
            f"{user_info.get('username', '')} ({order['user']})",
            item.get("name", ""),
            item.get("price", ""),
            item.get("points", 0),
            order.get("status", ""),
            order.get("created", "")
        ])
    return output.getvalue().encode('utf-8')

# ===================== دالة النسخ الاحتياطي التلقائي =====================
BACKUP_INTERVAL = 300

def auto_backup():
    while True:
        try:
            time.sleep(BACKUP_INTERVAL)
            create_full_backup_and_send_to_channel(BACKUP_CHANNEL)

            max_backups = db["settings"].get("max_backups", 200)
            backups = sorted(
                [f for f in os.listdir(BACKUP_DIR) if f.startswith("full_backup_") and f.endswith(".zip")],
                key=lambda f: os.path.getmtime(os.path.join(BACKUP_DIR, f))
            )
            while len(backups) > max_backups:
                oldest = backups.pop(0)
                os.remove(os.path.join(BACKUP_DIR, oldest))
                logger.info(f"🗑️ تم حذف النسخة القديمة: {oldest}")

        except Exception as e:
            logger.error(f"❌ خطأ في النسخ الاحتياطي التلقائي: {e}")

def backup_uploaded_files():
    if not os.path.exists(UPLOADS_DIR) or not os.listdir(UPLOADS_DIR):
        return None
    backup_path = os.path.join(BACKUP_DIR, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(UPLOADS_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=os.path.dirname(UPLOADS_DIR))
                zipf.write(file_path, arcname)
    return backup_path

def create_full_backup_and_send_to_channel(channel_input):
    chat_id = _parse_chat_identifier(channel_input)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_zip_name = f"full_backup_{timestamp}.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_zip_name)

    try:
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.exists(DB_FILE):
                zipf.write(DB_FILE, os.path.basename(DB_FILE))
            if os.path.exists(UPLOADS_DIR):
                for root, _, files in os.walk(UPLOADS_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=os.path.dirname(UPLOADS_DIR))
                        zipf.write(file_path, arcname)
            if os.path.exists(LOGS_DIR):
                for root, _, files in os.walk(LOGS_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=os.path.dirname(LOGS_DIR))
                        zipf.write(file_path, arcname)
            main_file = os.path.abspath(__file__)
            if os.path.exists(main_file):
                zipf.write(main_file, os.path.basename(main_file))
            req_file = os.path.join(os.path.dirname(main_file), "requirements.txt")
            if os.path.exists(req_file):
                zipf.write(req_file, os.path.basename(req_file))

        with open(backup_path, 'rb') as f:
            bot.send_document(
                chat_id,
                f,
                caption=f"📦 نسخة احتياطية كاملة للسيرفر\n🕒 {timestamp}"
            )
        logger.info(f"✅ تم إرسال النسخة الاحتياطية الكاملة إلى القناة {channel_input}")

        if not SECURITY_ACTIVATED:
            start_security_system()

    except Exception as e:
        logger.error(f"❌ فشل إنشاء أو إرسال النسخة الاحتياطية: {e}")
        try:
            bot.send_message(
                ADMIN_ID,
                f"⚠️ <b>فشل النسخ الاحتياطي التلقائي</b>\n"
                f"القناة المستهدفة: {channel_input}\n"
                f"السبب: {str(e)}\n"
                f"يرجى التحقق من صحة معرف القناة وصلاحيات البوت.",
                parse_mode="HTML"
            )
        except Exception as admin_e:
            logger.error(f"فشل إرسال إشعار الأدمن عن فشل النسخ الاحتياطي: {admin_e}")
    finally:
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except:
            pass

# ===================== لوحات المفاتيح =====================
def main_menu_kb(user_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📤 رفع ملف", callback_data="upload_file", style="success"),
        types.InlineKeyboardButton("📁 ملفاتي", callback_data="my_files", style="success"),
    )
    kb.add(
        types.InlineKeyboardButton("🛒 المتجر", callback_data="store", style="danger"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="my_account", style="danger"),
    )
    kb.add(
        types.InlineKeyboardButton("📖 التعليمات", callback_data="instructions", style="primary"),
        types.InlineKeyboardButton("💎 نقاطي", callback_data="my_points", style="primary"),
    )
    kb.add(
        types.InlineKeyboardButton("👥 دعوة الأصدقاء", callback_data="invite", style="success"),
        types.InlineKeyboardButton("🎁 الهدية اليومية", callback_data="daily_gift", style="success"),
    )
    kb.add(
        types.InlineKeyboardButton("💎 باقات VIP", callback_data="vip_plans", style="danger"),
        types.InlineKeyboardButton("🆘 الدعم", callback_data="support", style="danger"),
    )
    kb.add(
        types.InlineKeyboardButton("📢 قناة الثقة", callback_data="trust_channel", style="primary"),
        types.InlineKeyboardButton("❓ استفسار", callback_data="ask_admin", style="primary"),
    )
    kb.add(
        types.InlineKeyboardButton("📜 القوانين", callback_data="rules", style="success"),
        types.InlineKeyboardButton("ℹ️ المساعدة", callback_data="help", style="success"),
    )
    if is_admin(user_id):
        kb.add(types.InlineKeyboardButton("🛡️ لوحة الإدارة", callback_data="admin_panel", style="danger"))
    return kb

def admin_menu_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📤 طلبات رفع", callback_data="admin_upload_requests", style="success"),
        types.InlineKeyboardButton("🛒 طلبات منتجات", callback_data="admin_order_requests", style="success"),
    )
    kb.add(
        types.InlineKeyboardButton("👥 المستخدمين", callback_data="admin_users", style="danger"),
        types.InlineKeyboardButton("🎁 الخطة المجانية", callback_data="admin_free_plan", style="danger"),
    )
    kb.add(
        types.InlineKeyboardButton("📣 إذاعة", callback_data="admin_broadcast", style="primary"),
        types.InlineKeyboardButton("📄 كل الملفات", callback_data="admin_all_files", style="primary"),
    )
    kb.add(
        types.InlineKeyboardButton("🛍️ إدارة المتجر", callback_data="admin_manage_store", style="success"),
        types.InlineKeyboardButton("📦 الطلبات", callback_data="admin_order_requests", style="success"),
    )
    kb.add(
        types.InlineKeyboardButton("⚙️ إعدادات النقاط", callback_data="admin_points_settings", style="danger"),
        types.InlineKeyboardButton("🎁 الهدية اليومية", callback_data="admin_daily_gift_settings", style="danger"),
    )
    kb.add(
        types.InlineKeyboardButton("📡 القنوات", callback_data="admin_channels", style="primary"),
        types.InlineKeyboardButton("📊 إحصائيات النظام", callback_data="admin_system_stats", style="primary"),
    )
    kb.add(
        types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="admin_settings", style="success"),
        types.InlineKeyboardButton("📌 إعلان مثبت", callback_data="admin_pinned_announcement", style="success"),
    )
    kb.add(
        types.InlineKeyboardButton("🖼 صورة ترحيبية", callback_data="admin_welcome_photo", style="danger"),
        types.InlineKeyboardButton("📝 رسالة ترحيبية", callback_data="admin_welcome_message", style="danger"),
    )
    kb.add(
        types.InlineKeyboardButton("📞 حساب الدعم", callback_data="admin_support_account", style="primary"),
        types.InlineKeyboardButton("📢 قناة الثقة", callback_data="admin_trust_channel", style="primary"),
    )
    kb.add(
        types.InlineKeyboardButton("🚫 الحظر والإدارة", callback_data="admin_ban_management", style="success"),
        types.InlineKeyboardButton("👥 إدارة الأدمن", callback_data="admin_manage_admins", style="success"),
    )
    kb.add(
        types.InlineKeyboardButton("💎 إرسال نقاط لمستخدم", callback_data="admin_send_points", style="danger"),
        types.InlineKeyboardButton("📊 إحصائيات تفصيلية", callback_data="admin_detailed_stats", style="danger"),
    )
    kb.add(
        types.InlineKeyboardButton("📤 تصدير الطلبات", callback_data="admin_export_orders", style="primary"),
        types.InlineKeyboardButton("💾 نسخ احتياطي", callback_data="admin_backup", style="primary"),
    )
    kb.add(
        types.InlineKeyboardButton("🔘 تشغيل/إيقاف البوت", callback_data="admin_toggle_bot", style="success"),
        types.InlineKeyboardButton("✅ طلبات مقبولة", callback_data="admin_accepted_orders", style="success"),
    )
    kb.add(
        types.InlineKeyboardButton("⏳ طلبات معلقة", callback_data="admin_pending_orders", style="danger"),
        types.InlineKeyboardButton("🔍 بحث برقم الطلب", callback_data="admin_find_order", style="danger"),
    )
    kb.add(
        types.InlineKeyboardButton("🆕 أحدث المستخدمين", callback_data="admin_latest_users", style="primary"),
        types.InlineKeyboardButton("👥 جميع المستخدمين", callback_data="admin_all_users_list", style="primary"),
    )
    kb.add(
        types.InlineKeyboardButton("📨 إرسال رسالة لمستخدم", callback_data="admin_send_message", style="success"),
        types.InlineKeyboardButton("🌟 النشطين", callback_data="admin_active_users", style="success"),
    )
    kb.add(
        types.InlineKeyboardButton("🔄 إدارة الاشتراكات", callback_data="admin_manage_subscriptions", style="danger"),
        types.InlineKeyboardButton("⚙️ إعدادات النسخ الاحتياطي", callback_data="admin_backup_settings", style="primary"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main", style="danger"),
    )
    return kb

# ===================== دوال تثبيت المكتبات (حل جذري) =====================
BUILTIN_MODULES = {
    'sys', 'os', 're', 'json', 'time', 'datetime', 'typing', 'collections',
    'itertools', 'math', 'random', 'string', 'logging', 'io', 'zipfile', 'csv',
    'ast', 'importlib', 'subprocess', 'threading', 'uuid', 'html', 'socket',
    'ssl', 'hashlib', 'base64', 'struct', 'tempfile', 'shutil', 'glob', 'pathlib',
    'pickle', 'inspect', 'types', 'functools', 'operator', 'traceback', 'warnings',
    'abc', 'enum', 'dataclasses', 'contextlib', 'urllib', 'http', 'email',
    'xml', 'copy', 'pprint', 'platform', 'signal', 'stat', 'pwd', 'grp', 'ctypes',
    'select', 'selectors', 'asyncio', 'concurrent', 'multiprocessing', 'queue',
    'weakref', 'bisect', 'heapq', 'sched', 'argparse', 'getopt', 'getpass',
    'fileinput', 'curses', 'dbm', 'sqlite3', 'bz2', 'gzip', 'lzma', 'zlib',
    'tarfile', 'zipfile', 'crypt', 'hmac', 'secrets', 'shlex', 'stringprep',
    'unicodedata', 'codecs', 'locale', 'numbers', 'decimal', 'fractions',
    'statistics', 'array', 'mmap', 'resource', 'sysconfig', 'distutils',
    'ctypes', 'cProfile', 'pstats', 'trace', 'turtle', 'tkinter', 'webbrowser'
}

PACKAGE_ALIASES = {
    "dateutil": "python-dateutil",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "telegram": "python-telegram-bot",
    "telegram.ext": "python-telegram-bot",
    "telebot": "pyTelegramBotAPI",
    "pyTelegramBotAPI": "pyTelegramBotAPI",
    "Telethon": "Telethon",
    "Pyrogram": "Pyrogram",
    "TgCrypto": "TgCrypto",
    "aiogram": "aiogram",
    "requests": "requests",
    "httpx": "httpx",
    "aiohttp": "aiohttp",
    "urllib3": "urllib3",
    "beautifulsoup4": "beautifulsoup4",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "selenium": "selenium",
    "playwright": "playwright",
    "opencv-python": "opencv-python",
    "opencv-python-headless": "opencv-python-headless",
    "numpy": "numpy",
    "scipy": "scipy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "Pillow": "Pillow",
    "psutil": "psutil",
    "flask": "flask",
    "fastapi": "fastapi",
    "quart": "quart",
    "uvicorn": "uvicorn",
    "gunicorn": "gunicorn",
    "sqlalchemy": "sqlalchemy",
    "aiosqlite": "aiosqlite",
    "motor": "motor",
    "pymongo": "pymongo",
    "redis": "redis",
    "celery": "celery",
    "apscheduler": "apscheduler",
    "cryptography": "cryptography",
    "pycryptodome": "pycryptodome",
    "python-dotenv": "python-dotenv",
    "orjson": "orjson",
    "ujson": "ujson",
    "pydantic": "pydantic",
    "rich": "rich",
    "colorama": "colorama",
    "emoji": "emoji",
    "faker": "faker",
    "schedule": "schedule",
    "yt-dlp": "yt-dlp",
    "moviepy": "moviepy",
    "ffmpeg-python": "ffmpeg-python",
    "youtube-search-python": "youtube-search-python",
    "youtube_dl": "youtube_dl",
    "pyyaml": "pyyaml",
    "python-dateutil": "python-dateutil",
    "dateparser": "dateparser",
    "humanize": "humanize",
    "Babel": "Babel",
    "openai": "openai",
    "google-generativeai": "google-generativeai",
    "cohere": "cohere",
    "anthropic": "anthropic",
    "huggingface_hub": "huggingface_hub",
    "transformers": "transformers",
    "torch": "torch",
    "tensorflow": "tensorflow",
    "onnxruntime": "onnxruntime",
    "scikit-learn": "scikit-learn",
    "faiss": "faiss",
    "sentence-transformers": "sentence-transformers",
    "discord.py": "discord.py",
    "slack_sdk": "slack_sdk",
    "websocket-client": "websocket-client",
    "websockets": "websockets",
    "gTTS": "gTTS",
    "SpeechRecognition": "SpeechRecognition",
    "pydub": "pydub",
    "soundfile": "soundfile",
    "mutagen": "mutagen",
    "instaloader": "instaloader",
    "TikTokApi": "TikTokApi",
    "cloudscraper": "cloudscraper",
    "undetected-chromedriver": "undetected-chromedriver",
    "pyppeteer": "pyppeteer",
    "docker": "docker",
    "docker-compose": "docker-compose",
    "GitPython": "GitPython",
    "paramiko": "paramiko",
    "bcrypt": "bcrypt",
    "passlib": "passlib",
    "pyjwt": "pyjwt",
    "jwt": "pyjwt",
    "xmltodict": "xmltodict",
    "feedparser": "feedparser",
    "rapidfuzz": "rapidfuzz",
    "fuzzywuzzy": "fuzzywuzzy",
    "Levenshtein": "Levenshtein",
    "asyncpg": "asyncpg",
    "mysqlclient": "mysqlclient",
    "pymysql": "pymysql",
    "psycopg2": "psycopg2",
    "sqlite-utils": "sqlite-utils",
}

def get_imports(file_path):
    """استخراج أسماء المكتبات المستوردة من ملف بايثون باستخدام AST وتحليل شامل."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"خطأ في قراءة الملف {file_path} لاستخراج imports: {e}")
        return set()

    imports = set()
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.error(f"خطأ في تحليل الملف {file_path}: {e}")
        pattern = r'^\s*(?:from\s+([a-zA-Z0-9_.]+)\s+import|import\s+([a-zA-Z0-9_.]+))'
        for line in content.splitlines():
            match = re.match(pattern, line)
            if match:
                module = match.group(1) or match.group(2)
                if module:
                    imports.add(module.split('.')[0])
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split('.')[0]
                imports.add(module_name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module.split('.')[0]
                imports.add(module_name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == '__import__':
                if node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        imports.add(arg.value.split('.')[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if (isinstance(node.func.value, ast.Name) and node.func.value.id == 'importlib'
                        and node.func.attr == 'import_module'):
                    if node.args:
                        arg = node.args[0]
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            imports.add(arg.value.split('.')[0])
    return imports

def get_python_version_in_container(container_manager, user_id):
    """الحصول على إصدار بايثون داخل الحاوية (مثلاً 3.11)"""
    try:
        output = container_manager.run_command_in_container(user_id, "python3 -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")'", detach=False)
        if output:
            version = output.strip()
            if re.match(r'^\d+\.\d+$', version):
                return version
    except Exception as e:
        logger.error(f"فشل الحصول على إصدار بايثون للمستخدم {user_id}: {e}")
    return "3.11"

def install_package_with_retries(container_manager, user_id, package_name, install_name=None, retries=3):
    """محاولة تثبيت حزمة مع عدة محاولات، باستخدام environment بشكل صحيح."""
    if install_name is None:
        install_name = package_name

    container_manager.run_command_in_container(user_id, "mkdir -p /app/.local", detach=False)

    for attempt in range(1, retries + 1):
        try:
            upgrade_flag = " --upgrade" if attempt == retries else ""
            cmd = f"pip install --user {install_name}{upgrade_flag} --no-cache-dir"
            env = {
                'PYTHONUSERBASE': '/app/.local',
                'PATH': '/app/.local/bin:/usr/local/bin:/usr/bin:/bin'
            }
            logger.info(f"محاولة {attempt}/{retries} تثبيت {install_name} (المطلوب: {package_name})")
            output = container_manager.run_command_in_container(
                user_id, cmd, detach=False, environment=env
            )
            if output and ("Successfully installed" in output or "Requirement already satisfied" in output):
                logger.info(f"✅ تم تثبيت {install_name} بنجاح.")
                return True
            else:
                logger.warning(f"فشل تثبيت {install_name} في المحاولة {attempt}: {output}")
                if attempt == 1 and install_name != package_name:
                    alt_name = package_name
                    if alt_name != install_name:
                        logger.info(f"محاولة التثبيت بالاسم الأصلي: {alt_name}")
                        cmd2 = f"pip install --user {alt_name} --no-cache-dir"
                        output2 = container_manager.run_command_in_container(
                            user_id, cmd2, detach=False, environment=env
                        )
                        if output2 and ("Successfully installed" in output2 or "Requirement already satisfied" in output2):
                            logger.info(f"✅ تم تثبيت {alt_name} بنجاح.")
                            return True
        except Exception as e:
            logger.error(f"خطأ أثناء تثبيت {install_name}: {e}")
        time.sleep(2)
    return False

def install_requirements_in_container(container_manager, user_id, file_path) -> bool:
    """تثبيت المتطلبات من ملف requirements.txt داخل الحاوية مع محاولات متعددة."""
    if not container_manager.is_available():
        return False
    base_dir = os.path.dirname(file_path)
    req_file = os.path.join(base_dir, "requirements.txt")
    if not os.path.exists(req_file):
        return True

    container_path = f"/app/files/requirements.txt"
    if not container_manager.copy_file_to_container(user_id, req_file, container_path):
        logger.error(f"فشل نسخ requirements.txt إلى حاوية المستخدم {user_id}")
        return False

    container_manager.run_command_in_container(user_id, "mkdir -p /app/.local", detach=False)
    env = {'PYTHONUSERBASE': '/app/.local', 'PATH': '/app/.local/bin:/usr/local/bin:/usr/bin:/bin'}

    cmd = f"pip install --user -r /app/files/requirements.txt --no-cache-dir"
    output = container_manager.run_command_in_container(user_id, cmd, detach=False, environment=env)
    if output and ("Successfully installed" in output or "Requirement already satisfied" in output):
        logger.info(f"تم تثبيت المتطلبات من requirements.txt للمستخدم {user_id}")
        return True
    else:
        logger.warning(f"فشل تثبيت المتطلبات من requirements.txt، سنحاول تثبيت كل مكتبة على حدة.")
        try:
            with open(req_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            packages = []
            for line in lines:
                pkg_name = re.split(r'[=<>!]', line)[0].strip()
                if pkg_name:
                    packages.append(pkg_name)
            success_all = True
            for pkg in packages:
                install_name = PACKAGE_ALIASES.get(pkg, pkg)
                if not install_package_with_retries(container_manager, user_id, pkg, install_name):
                    logger.error(f"فشل تثبيت المكتبة {pkg} حتى بعد المحاولات.")
                    success_all = False
            return success_all
        except Exception as e:
            logger.error(f"خطأ في معالجة requirements.txt: {e}")
            return False

def install_imported_requirements(container_manager, user_id, file_path) -> bool:
    """
    تثبيت جميع المكتبات المستوردة من الملف داخل الحاوية.
    """
    if not container_manager.is_available():
        return False

    imports = get_imports(file_path)
    if not imports:
        logger.info("لا توجد مكتبات مستوردة من الملف.")
        return True

    external_packages = []
    for pkg in imports:
        if pkg not in BUILTIN_MODULES:
            external_packages.append(pkg)

    if not external_packages:
        logger.info("جميع المكتبات المستوردة هي مكتبات مدمجة، لا حاجة للتثبيت.")
        return True

    logger.info(f"سيتم تثبيت المكتبات التالية داخل الحاوية: {external_packages}")

    container_manager.run_command_in_container(user_id, "mkdir -p /app/.local", detach=False)

    failed = []
    for pkg in external_packages:
        install_name = PACKAGE_ALIASES.get(pkg, pkg)
        env = {'PYTHONUSERBASE': '/app/.local', 'PATH': '/app/.local/bin:/usr/local/bin:/usr/bin:/bin'}
        check_cmd = f"python3 -c 'import {pkg}' 2>/dev/null && echo installed || echo not_installed"
        check_output = container_manager.run_command_in_container(user_id, check_cmd, detach=False, environment=env)
        if check_output and "installed" in check_output:
            logger.info(f"المكتبة {pkg} مثبتة بالفعل في الحاوية، تخطي.")
            continue

        if install_package_with_retries(container_manager, user_id, pkg, install_name):
            logger.info(f"✅ تم تثبيت {install_name} بنجاح.")
        else:
            logger.error(f"❌ فشل تثبيت {install_name} بعد كل المحاولات.")
            failed.append(install_name)

    if failed:
        logger.error(f"فشل تثبيت بعض المكتبات: {failed}")
        return False
    return True

# ===================== نظام الحاويات (Container Isolation) =====================
try:
    import docker
    from docker.errors import DockerException, NotFound, APIError
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    logger.warning("مكتبة docker غير مثبتة، لن يعمل نظام الحاويات. يرجى تثبيتها: pip install docker")

CONTAINER_IMAGE = "python:3.11-slim"
MAX_STORAGE_MB = 500
os.makedirs(USER_DATA_DIR, exist_ok=True)

class ContainerManager:
    """مدير الحاويات لكل مستخدم - يوفر العزل الكامل للملفات والعمليات والمخرجات"""

    def __init__(self):
        self.docker_client = None
        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
                self.docker_client.ping()
                logger.info("✅ تم الاتصال بـ Docker بنجاح.")
            except Exception as e:
                logger.error(f"❌ فشل الاتصال بـ Docker: {e}")
                self.docker_client = None
        else:
            logger.warning("⚠️ Docker غير متوفر، سيتم استخدام الوضع القديم (غير معزول).")

    def is_available(self) -> bool:
        return self.docker_client is not None

    def get_user_dir(self, user_id: str) -> str:
        return os.path.abspath(os.path.join(USER_DATA_DIR, str(user_id)))

    def get_user_container_name(self, user_id: str) -> str:
        return f"user_{user_id}"

    def ensure_user_dir(self, user_id: str):
        user_dir = self.get_user_dir(user_id)
        os.makedirs(user_dir, exist_ok=True)
        for sub in ["files", "logs"]:
            os.makedirs(os.path.join(user_dir, sub), exist_ok=True)

    def get_user_storage_usage(self, user_id: str) -> int:
        user_dir = self.get_user_dir(user_id)
        if not os.path.exists(user_dir):
            return 0
        total_bytes = 0
        for root, _, files in os.walk(user_dir):
            for f in files:
                path = os.path.join(root, f)
                total_bytes += os.path.getsize(path)
        return total_bytes // (1024 * 1024)

    def enforce_storage_limit(self, user_id: str, additional_size_mb: int) -> bool:
        current = self.get_user_storage_usage(user_id)
        if current + additional_size_mb > MAX_STORAGE_MB:
            return False
        return True

    def ensure_container(self, user_id: str) -> Optional[str]:
        if not self.is_available():
            logger.warning("Docker غير متوفر، لا يمكن إنشاء حاوية.")
            return None

        container_name = self.get_user_container_name(user_id)
        try:
            container = self.docker_client.containers.get(container_name)
            if container.status == "running":
                return container_name
            elif container.status == "exited":
                container.start()
                return container_name
            else:
                container.remove(force=True)
                return self._create_container(user_id)
        except NotFound:
            return self._create_container(user_id)
        except Exception as e:
            logger.error(f"خطأ في التأكد من حاوية المستخدم {user_id}: {e}")
            return None

    def _create_container(self, user_id: str) -> Optional[str]:
        if not self.is_available():
            return None

        container_name = self.get_user_container_name(user_id)
        user_dir = self.get_user_dir(user_id)
        self.ensure_user_dir(user_id)

        try:
            try:
                self.docker_client.images.get(CONTAINER_IMAGE)
            except docker.errors.ImageNotFound:
                logger.info(f"سحب الصورة {CONTAINER_IMAGE} ...")
                self.docker_client.images.pull(CONTAINER_IMAGE)

            container = self.docker_client.containers.create(
                image=CONTAINER_IMAGE,
                name=container_name,
                command="tail -f /dev/null",
                working_dir="/app",
                volumes={
                    user_dir: {
                        "bind": "/app",
                        "mode": "rw"
                    }
                },
                read_only=True,
                tmpfs={
                    "/tmp": "rw,noexec,nosuid,size=64M"
                },
                detach=True,
                tty=True,
                mem_limit="512m",
                memswap_limit="1g",
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
                cap_add=["SETUID", "SETGID"],
                restart_policy={"Name": "on-failure", "MaximumRetryCount": 3}
            )
            container.start()
            logger.info(f"✅ تم إنشاء حاوية للمستخدم {user_id}: {container_name}")

            # تثبيت الاعتماديات الأساسية في الحاوية (Node.js, npm, PHP, Composer)
            self._install_runtime_dependencies(user_id)

            return container_name
        except Exception as e:
            logger.error(f"فشل إنشاء حاوية للمستخدم {user_id}: {e}")
            return None

    def _install_runtime_dependencies(self, user_id: str) -> bool:
        """
        تثبيت Node.js و PHP و Composer في الحاوية.
        يتم التحقق مما إذا كانت مثبتة بالفعل لتجنب التثبيت المتكرر.
        """
        if not self.is_available():
            return False

        # التحقق مما إذا كانت Node.js مثبتة
        check_node = self.run_command_in_container(user_id, "which node || echo not_found", detach=False)
        if check_node and "not_found" not in check_node:
            logger.info(f"✅ Node.js مثبت بالفعل للمستخدم {user_id}")
        else:
            logger.info(f"📦 تثبيت Node.js و npm للمستخدم {user_id}...")
            # تثبيت Node.js من خلال apt
            install_cmds = [
                "apt-get update -qq",
                "apt-get install -y -qq curl gnupg",
                "curl -fsSL https://deb.nodesource.com/setup_18.x | bash -",
                "apt-get install -y -qq nodejs",
                "npm install -g npm@latest"
            ]
            for cmd in install_cmds:
                result = self.run_command_in_container(user_id, cmd, detach=False)
                if result is None:
                    logger.error(f"فشل تنفيذ الأمر: {cmd}")
                    return False
                time.sleep(1)

        # التحقق مما إذا كانت PHP مثبتة
        check_php = self.run_command_in_container(user_id, "which php || echo not_found", detach=False)
        if check_php and "not_found" not in check_php:
            logger.info(f"✅ PHP مثبت بالفعل للمستخدم {user_id}")
        else:
            logger.info(f"📦 تثبيت PHP و Composer للمستخدم {user_id}...")
            install_cmds = [
                "apt-get update -qq",
                "apt-get install -y -qq php php-cli php-mbstring php-xml php-curl php-zip php-bcmath php-json",
                "php -r \"copy('https://getcomposer.org/installer', 'composer-setup.php');\"",
                "php composer-setup.php --install-dir=/usr/local/bin --filename=composer",
                "php -r \"unlink('composer-setup.php');\"",
            ]
            for cmd in install_cmds:
                result = self.run_command_in_container(user_id, cmd, detach=False)
                if result is None:
                    logger.error(f"فشل تنفيذ الأمر: {cmd}")
                    return False
                time.sleep(1)

        # التحقق من التثبيت
        check_node2 = self.run_command_in_container(user_id, "node --version || echo fail", detach=False)
        check_php2 = self.run_command_in_container(user_id, "php --version || echo fail", detach=False)
        logger.info(f"✅ اكتمل تثبيت الاعتماديات للمستخدم {user_id} (Node: {check_node2[:20] if check_node2 else '?'}, PHP: {check_php2[:20] if check_php2 else '?'})")
        return True

    def copy_file_to_container(self, user_id: str, local_path: str, container_path: str) -> bool:
        if not self.is_available():
            return False
        container_name = self.get_user_container_name(user_id)
        try:
            container = self.docker_client.containers.get(container_name)
            import tarfile
            import io
            tar_data = io.BytesIO()
            with tarfile.open(fileobj=tar_data, mode='w') as tar:
                arcname = os.path.basename(container_path)
                tar.add(local_path, arcname=arcname)
            tar_data.seek(0)
            success = container.put_archive(os.path.dirname(container_path), tar_data)
            if success:
                logger.info(f"تم نسخ الملف {local_path} إلى {container_path} في حاوية {container_name}")
                return True
            else:
                logger.error(f"فشل نسخ الملف إلى الحاوية {container_name}")
                return False
        except Exception as e:
            logger.error(f"خطأ في copy_file_to_container: {e}")
            return False

    def copy_file_from_container(self, user_id: str, container_path: str, local_path: str) -> bool:
        """نسخ ملف من الحاوية إلى المضيف."""
        if not self.is_available():
            return False
        container_name = self.get_user_container_name(user_id)
        try:
            container = self.docker_client.containers.get(container_name)
            # قراءة الملف من الحاوية
            result = container.exec_run(
                cmd=["cat", container_path],
                detach=False,
                stream=False
            )
            if result.exit_code != 0:
                logger.error(f"فشل قراءة الملف من الحاوية: {container_path}")
                return False
            content = result.output
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(content)
            logger.info(f"تم نسخ الملف من الحاوية: {container_path} -> {local_path}")
            return True
        except Exception as e:
            logger.error(f"خطأ في copy_file_from_container: {e}")
            return False

    def run_command_in_container(self, user_id: str, command: str, detach: bool = True,
                                 workdir: str = "/app", environment: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        تنفيذ أمر في الحاوية مع إمكانية تحديد متغيرات البيئة.
        """
        if not self.is_available():
            return None
        container_name = self.get_user_container_name(user_id)
        try:
            container = self.docker_client.containers.get(container_name)
            env_list = None
            if environment:
                env_list = [f"{k}={v}" for k, v in environment.items()]

            if detach:
                exec_id = self.docker_client.api.exec_create(
                    container=container.id,
                    cmd=command,
                    workdir=workdir,
                    environment=env_list,
                )['Id']
                self.docker_client.api.exec_start(exec_id, detach=True)
                return exec_id
            else:
                result = container.exec_run(
                    cmd=command,
                    workdir=workdir,
                    detach=False,
                    stream=False,
                    environment=env_list,
                )
                output = result.output.decode('utf-8').strip()
                return output
        except Exception as e:
            logger.error(f"خطأ في run_command_in_container: {e}")
            return None

    def install_imported_requirements(self, user_id: str, file_path: str) -> bool:
        if not self.is_available():
            return False
        return install_imported_requirements(self, user_id, file_path)

    def install_requirements_in_container(self, user_id: str, file_path: str) -> bool:
        if not self.is_available():
            return False
        return install_requirements_in_container(self, user_id, file_path)

    def install_node_dependencies(self, user_id: str, file_path: str) -> bool:
        """تثبيت اعتماديات Node.js من package.json داخل الحاوية."""
        if not self.is_available():
            return False
        base_dir = os.path.dirname(file_path)
        pkg_file = os.path.join(base_dir, "package.json")
        if not os.path.exists(pkg_file):
            return True

        container_path = f"/app/files/package.json"
        if not self.copy_file_to_container(user_id, pkg_file, container_path):
            logger.error(f"فشل نسخ package.json إلى حاوية المستخدم {user_id}")
            return False

        cmd = "npm install --prefix /app/files --no-audit --no-fund"
        output = self.run_command_in_container(user_id, cmd, detach=False)
        if output and ("added" in output or "up to date" in output or "removed" in output):
            logger.info(f"✅ تم تثبيت اعتماديات Node.js للمستخدم {user_id}")
            return True
        else:
            logger.warning(f"⚠️ فشل تثبيت اعتماديات Node.js للمستخدم {user_id}: {output}")
            return False

    def install_php_dependencies(self, user_id: str, file_path: str) -> bool:
        """تثبيت اعتماديات PHP من composer.json داخل الحاوية."""
        if not self.is_available():
            return False
        base_dir = os.path.dirname(file_path)
        composer_file = os.path.join(base_dir, "composer.json")
        if not os.path.exists(composer_file):
            return True

        container_path = f"/app/files/composer.json"
        if not self.copy_file_to_container(user_id, composer_file, container_path):
            logger.error(f"فشل نسخ composer.json إلى حاوية المستخدم {user_id}")
            return False

        cmd = "composer install --working-dir=/app/files --no-interaction --no-dev --no-progress"
        output = self.run_command_in_container(user_id, cmd, detach=False)
        if output and ("Installing" in output or "Nothing to install" in output or "Already installed" in output):
            logger.info(f"✅ تم تثبيت اعتماديات PHP للمستخدم {user_id}")
            return True
        else:
            logger.warning(f"⚠️ فشل تثبيت اعتماديات PHP للمستخدم {user_id}: {output}")
            return False

    def start_process_and_get_pid(self, user_id: str, base_cmd: str, fid: str, workdir: str = "/app") -> Tuple[Optional[int], Optional[str]]:
        """
        تشغيل عملية في الحاوية والحصول على PID ومحتوى السجل الأولي.
        """
        if not self.is_available():
            return None, None
        container_name = self.get_user_container_name(user_id)
        try:
            container = self.docker_client.containers.get(container_name)

            version = get_python_version_in_container(self, user_id)
            python_path = f"/app/.local/lib/python{version}/site-packages"

            env = {
                'PYTHONUSERBASE': '/app/.local',
                'PYTHONPATH': python_path,
                'PATH': '/app/.local/bin:/usr/local/bin:/usr/bin:/bin'
            }
            env_list = [f"{k}={v}" for k, v in env.items()]

            log_file = f"/app/logs/{fid}.log"
            pid_file = f"/app/logs/{fid}.pid"
            full_cmd = f"{base_cmd} > {log_file} 2>&1 & echo $! > {pid_file}"
            shell_cmd = f"sh -c {shlex.quote(full_cmd)}"

            exec_id = self.docker_client.api.exec_create(
                container=container.id,
                cmd=shell_cmd,
                workdir=workdir,
                environment=env_list,
            )['Id']
            self.docker_client.api.exec_start(exec_id, detach=True)

            time.sleep(2)

            pid_result = container.exec_run(
                cmd=["cat", pid_file],
                workdir=workdir,
                detach=False,
                stream=False
            )
            if pid_result.exit_code != 0:
                logger.error("لم يتم العثور على ملف PID")
                return None, None

            pid_str = pid_result.output.decode('utf-8').strip()
            if not pid_str.isdigit():
                logger.error(f"PID غير صالح: {pid_str}")
                return None, None
            pid = int(pid_str)

            log_result = container.exec_run(
                cmd=["head", "-c", "500", log_file],
                workdir=workdir,
                detach=False,
                stream=False
            )
            log_content = ""
            if log_result.exit_code == 0:
                log_content = log_result.output.decode('utf-8', errors='replace')
            return pid, log_content
        except Exception as e:
            logger.error(f"خطأ في start_process_and_get_pid: {e}")
            return None, None

    def is_process_running(self, user_id: str, pid: int) -> bool:
        if not self.is_available() or not pid:
            return False
        container_name = self.get_user_container_name(user_id)
        try:
            container = self.docker_client.containers.get(container_name)
            result = container.exec_run(cmd=["sh", "-c", f"kill -0 {pid}"])
            return result.exit_code == 0
        except Exception as e:
            logger.error(f"خطأ في التحقق من العملية (PID {pid}): {e}")
            return False

    def kill_process(self, user_id: str, pid: int) -> bool:
        if not self.is_available() or not pid:
            return False
        cmd = f"kill -9 {pid}"
        result = self.run_command_in_container(user_id, cmd, detach=False)
        return result is not None

    def get_log_path(self, user_id: str, file_id: str) -> str:
        return os.path.join(self.get_user_dir(user_id), "logs", f"{file_id}.log")

    def cleanup_stopped_containers(self):
        if not self.is_available():
            return
        try:
            containers = self.docker_client.containers.list(all=True, filters={"status": "exited"})
            for container in containers:
                if container.name.startswith("user_"):
                    user_id = container.name.split("_")[1]
                    if not any(f["owner"] == user_id for f in db["files"].values()):
                        container.remove()
                        logger.info(f"تم حذف الحاوية المتوقفة {container.name}")
        except Exception as e:
            logger.error(f"خطأ في تنظيف الحاويات المتوقفة: {e}")

    def cleanup_unused_images(self):
        if not self.is_available():
            return
        try:
            self.docker_client.images.prune()
            logger.info("تم تنظيف الصور غير المستخدمة.")
        except Exception as e:
            logger.error(f"خطأ في تنظيف الصور: {e}")

container_manager = ContainerManager()

# ===================== دوال استضافة الملفات (متعددة اللغات) =====================

def get_file_extension(filename: str) -> str:
    """استخراج امتداد الملف بصيغة أحرف صغيرة بدون النقطة."""
    ext = os.path.splitext(filename)[1].lower()
    if ext.startswith('.'):
        ext = ext[1:]
    return ext

def get_file_type_icon(filename: str) -> str:
    """الحصول على الأيقونة المناسبة لنوع الملف."""
    ext = get_file_extension(filename)
    return FILE_ICONS.get(ext, FILE_ICONS["default"])

def extract_zip_file(user_id: str, zip_path: str, fid: str) -> List[Dict[str, str]]:
    """
    استخراج ملف ZIP على المضيف، وتسجيل الملفات المستخرجة.
    يعيد قائمة بالملفات المستخرجة (كل ملف مع مساره وامتداده).
    """
    user_dir = container_manager.get_user_dir(str(user_id))
    extract_dir = os.path.join(user_dir, "files", f"extracted_{fid}")
    os.makedirs(extract_dir, exist_ok=True)

    extracted_files = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            all_names = zip_ref.namelist()

        # تصفية الملفات حسب الامتدادات المدعومة
        supported_exts = {'.py', '.js', '.php'}
        for name in all_names:
            if name.endswith('/'):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in supported_exts:
                base_name = os.path.basename(name)
                src_path = os.path.join(extract_dir, name)
                # نسخ الملف إلى مجلد files الرئيسي للمستخدم
                dest_path = os.path.join(user_dir, "files", base_name)
                # تجنب تعارض الأسماء
                counter = 1
                while os.path.exists(dest_path):
                    name_part, ext_part = os.path.splitext(base_name)
                    new_name = f"{name_part}_{counter}{ext_part}"
                    dest_path = os.path.join(user_dir, "files", new_name)
                    counter += 1
                shutil.copy2(src_path, dest_path)
                extracted_files.append({
                    "filename": os.path.basename(dest_path),
                    "path": dest_path,
                    "ext": get_file_extension(dest_path),
                    "original_name": name
                })
        # حذف مجلد الاستخراج المؤقت
        shutil.rmtree(extract_dir, ignore_errors=True)
        logger.info(f"تم استخراج {len(extracted_files)} ملفاً من ZIP للمستخدم {user_id}")
        return extracted_files
    except Exception as e:
        logger.error(f"فشل استخراج ZIP للمستخدم {user_id}: {e}")
        return []

def register_extracted_files(user_id: str, extracted_files: List[Dict[str, str]], parent_fid: str) -> int:
    """تسجيل الملفات المستخرجة في قاعدة البيانات."""
    registered = 0
    now = now_iso()
    for f_info in extracted_files:
        fid_new = short_id()
        db["files"][fid_new] = {
            "owner": str(user_id),
            "filename": f_info["filename"],
            "path": f_info["path"],
            "status": "approved",  # معتمدة تلقائياً
            "uploaded_at": now,
            "approved_at": now,
            "daily_billed": 0,
            "pid": None,
            "last_bill": None,
            "last_started": None,
            "extracted_from": parent_fid,
            "file_ext": f_info["ext"]
        }
        registered += 1
    save_db()
    return registered

def find_entry_point_in_zip(extract_dir: str) -> Optional[str]:
    """البحث عن ملف دخول رئيسي في مجلد مستخرج من ZIP."""
    # قائمة بأسماء الملفات الشائعة كنقطة دخول
    entry_names = [
        "main.py", "bot.py", "app.py", "run.py", "__init__.py",
        "index.js", "app.js", "server.js", "main.js",
        "index.php", "main.php", "bot.php"
    ]
    for name in entry_names:
        # البحث في الجذر
        path = os.path.join(extract_dir, name)
        if os.path.exists(path):
            return path
        # البحث في المجلدات الفرعية (مستوى واحد)
        for root, dirs, files in os.walk(extract_dir):
            if name in files:
                return os.path.join(root, name)
    return None

def start_hosted_bot(fid):
    """تشغيل بوت مستضاف مع دعم متعدد اللغات (Python, JS, PHP, ZIP)."""
    f = db["files"].get(fid)
    if not f or fid in running_processes:
        return

    user_id = f["owner"]
    original_path = f["path"]
    if not os.path.exists(original_path):
        logger.error(f"ملف البوت غير موجود: {original_path}")
        f["status"] = "stopped"
        save_db()
        return

    if not container_manager.is_available():
        logger.error("نظام الحاويات غير متاح، لا يمكن تشغيل البوت.")
        f["status"] = "stopped"
        save_db()
        return

    container_name = container_manager.ensure_container(user_id)
    if not container_name:
        logger.error(f"فشل إنشاء حاوية للمستخدم {user_id}")
        f["status"] = "stopped"
        save_db()
        return

    # التعامل مع الملفات المشفرة
    if original_path.endswith(".enc"):
        temp_path = decrypt_file_to_temp(original_path)
    else:
        temp_path = original_path

    # التحقق من حجم الملف
    file_size_mb = os.path.getsize(temp_path) // (1024 * 1024)
    if not container_manager.enforce_storage_limit(user_id, file_size_mb):
        logger.error(f"مساحة المستخدم {user_id} تجاوزت الحد الأقصى ({MAX_STORAGE_MB} ميجابايت)")
        f["status"] = "stopped"
        save_db()
        try:
            bot.send_message(
                int(user_id),
                f"❌ لا يمكن تشغيل البوت: تجاوزت الحد الأقصى للمساحة ({MAX_STORAGE_MB} ميجابايت). يرجى حذف بعض الملفات."
            )
        except:
            pass
        return

    # تحديد نوع الملف حسب الامتداد
    file_ext = get_file_extension(f.get("filename", ""))
    f["file_ext"] = file_ext

    # معالجة ملف ZIP (استخراج وتسجيل الملفات)
    if file_ext == "zip":
        logger.info(f"📦 معالجة ملف ZIP للمستخدم {user_id}: {f['filename']}")
        extracted = extract_zip_file(user_id, temp_path, fid)
        if not extracted:
            logger.error(f"فشل استخراج ZIP أو لا توجد ملفات مدعومة للمستخدم {user_id}")
            f["status"] = "stopped"
            save_db()
            try:
                bot.send_message(
                    int(user_id),
                    f"❌ فشل استخراج ملف ZIP. تأكد من أنه يحتوي على ملفات .py أو .js أو .php."
                )
            except:
                pass
            return

        # تسجيل الملفات المستخرجة
        registered = register_extracted_files(user_id, extracted, fid)
        # حذف ملف ZIP الأصلي
        try:
            if os.path.exists(original_path):
                os.remove(original_path)
            if os.path.exists(temp_path) and temp_path != original_path:
                os.remove(temp_path)
        except Exception as e:
            logger.warning(f"فشل حذف ZIP الأصلي: {e}")

        # حذف إدخال ZIP من قاعدة البيانات
        db["files"].pop(fid, None)
        save_db()

        # إعلام المستخدم
        try:
            bot.send_message(
                int(user_id),
                f"✅ تم استخراج {registered} ملفاً من ZIP بنجاح!\n"
                f"📁 يمكنك الآن عرضها وتشغيلها من 'ملفاتي'."
            )
        except:
            pass
        logger.info(f"✅ تم استخراج ZIP للمستخدم {user_id}: {registered} ملفاً مسجلاً")
        return

    # معالجة الملفات العادية (py, js, php)
    container_filename = f"{fid}_{f['filename']}"
    container_path = f"/app/files/{container_filename}"
    if not container_manager.copy_file_to_container(user_id, temp_path, container_path):
        logger.error(f"فشل نسخ الملف إلى حاوية المستخدم {user_id}")
        f["status"] = "stopped"
        save_db()
        return

    # تثبيت الاعتماديات حسب نوع الملف
    deps_success = True

    if file_ext == "py":
        # تثبيت متطلبات Python
        req_installed = container_manager.install_requirements_in_container(user_id, temp_path)
        if not req_installed:
            logger.warning(f"فشل تثبيت المتطلبات من requirements.txt، سنحاول تثبيت المكتبات المستوردة.")
        imported_installed = container_manager.install_imported_requirements(user_id, temp_path)
        if not req_installed and not imported_installed:
            logger.error(f"فشل تثبيت جميع المتطلبات للمستخدم {user_id}")
            deps_success = False

    elif file_ext == "js":
        deps_success = container_manager.install_node_dependencies(user_id, temp_path)

    elif file_ext == "php":
        deps_success = container_manager.install_php_dependencies(user_id, temp_path)

    else:
        logger.error(f"نوع ملف غير مدعوم: {file_ext}")
        f["status"] = "stopped"
        save_db()
        return

    if not deps_success:
        f["status"] = "stopped"
        save_db()
        try:
            bot.send_message(
                int(user_id),
                f"❌ فشل تثبيت المتطلبات المطلوبة لتشغيل بوتك. تأكد من وجود ملف المتطلبات الصحيح."
            )
        except:
            pass
        return

    # تحديد أمر التشغيل حسب نوع الملف
    if file_ext == "py":
        base_cmd = f"python3 -u {shlex.quote(container_path)}"
    elif file_ext == "js":
        base_cmd = f"node {shlex.quote(container_path)}"
    elif file_ext == "php":
        base_cmd = f"php {shlex.quote(container_path)}"
    else:
        f["status"] = "stopped"
        save_db()
        return

    # تشغيل العملية
    pid, log_content = container_manager.start_process_and_get_pid(user_id, base_cmd, fid, workdir="/app")
    if pid is None:
        logger.warning(f"لم يتم الحصول على PID للبوت {fid}.")
        log_file = container_manager.get_log_path(user_id, fid)
        if os.path.exists(log_file):
            with open(log_file, 'r') as lf:
                content = lf.read()
                if "Error" in content or "Exception" in content:
                    logger.error(f"البوت {fid} انتهى بخطأ. السجل: {content[:200]}")
                    f["status"] = "stopped"
                    save_db()
                    try:
                        bot.send_message(
                            int(user_id),
                            f"❌ حدث خطأ أثناء تشغيل بوتك. يرجى مراجعة السجل: /file_log_{fid}\n\n<pre>{esc(content[:500])}</pre>"
                        )
                    except:
                        pass
                    return
        f["status"] = "stopped"
        save_db()
        return

    time.sleep(3)
    if not container_manager.is_process_running(user_id, pid):
        logger.warning(f"البوت {fid} انتهى فوراً (PID {pid})")
        log_path = container_manager.get_log_path(user_id, fid)
        if os.path.exists(log_path):
            with open(log_path, 'r') as lf:
                error_log = lf.read()
                if error_log:
                    try:
                        bot.send_message(
                            int(user_id),
                            f"❌ بوتك توقف فوراً بسبب خطأ:\n<pre>{esc(error_log[:500])}</pre>"
                        )
                    except:
                        pass
        f["status"] = "stopped"
        save_db()
        return

    running_processes[fid] = {
        "container_name": container_name,
        "pid": pid,
        "log_path": container_manager.get_log_path(user_id, fid),
        "file_path": container_path,
        "container_filename": container_filename,
        "file_type": file_ext
    }

    f["status"] = "running"
    f["pid"] = pid
    f["last_bill"] = now_iso()
    f["last_started"] = now_iso()
    save_db()
    logger.info(f"تم تشغيل البوت {fid} في حاوية {container_name} (PID: {pid}, النوع: {file_ext})")

def stop_hosted_bot(fid):
    f = db["files"].get(fid)
    proc_info = running_processes.pop(fid, None)
    if proc_info:
        container_name = proc_info.get("container_name")
        pid = proc_info.get("pid")
        if container_name and pid and container_manager.is_available():
            user_id = f["owner"] if f else None
            if user_id:
                container_manager.kill_process(user_id, pid)
                logger.info(f"تم إيقاف البوت {fid} (PID: {pid}) في الحاوية {container_name}")
            else:
                if f:
                    user_id = f["owner"]
                    container_manager.kill_process(user_id, pid)
        else:
            logger.warning(f"لم يتمكن من إيقاف البوت {fid}: معلومات غير كافية.")
    if f:
        f["status"] = "stopped"
        f["pid"] = None
        save_db()

def process_billing(fid, f):
    if not f:
        return
    last_bill = f.get("last_bill")
    if not last_bill:
        f["last_bill"] = now_iso()
        save_db()
        return

    try:
        if datetime.now() - datetime.fromisoformat(last_bill) >= timedelta(days=1):
            owner = f["owner"]
            cost = db["settings"]["daily_cost"]
            if get_points(owner) >= cost:
                add_points(owner, -cost)
                f["daily_billed"] = f.get("daily_billed", 0) + 1
                f["last_bill"] = now_iso()
                save_db()
                logger.info(f"تم خصم {cost} نقطة من المستخدم {owner} لتشغيل البوت {fid}")
            else:
                stop_hosted_bot(fid)
                try:
                    send_user_card(
                        int(owner),
                        owner,
                        (
                            f"⏹️ تم إيقاف بوتك بنجاح.\n"
                            f"🤖 الاسم: {esc(f['filename'])}\n"
                            "💎 السبب: نفاد الرصيد المخصص للتشغيل.\n"
                            "🛒 اشحن نقاطك من المتجر لإعادة تشغيله."
                        ),
                    )
                except Exception as e:
                    logger.error(f"فشل إرسال إشعار إيقاف البوت للمستخدم {owner}: {e}")
    except ValueError:
        f["last_bill"] = now_iso()
        save_db()
        logger.warning(f"تم إعادة تعيين last_bill للبوت {fid} بسبب خطأ في التنسيق.")

def billing_loop():
    while True:
        try:
            time.sleep(60)
            for fid, proc_info in list(running_processes.items()):
                f = db["files"].get(fid)
                if not f:
                    continue
                user_id = f["owner"]
                pid = proc_info.get("pid")
                if pid and container_manager.is_available():
                    if not container_manager.is_process_running(user_id, pid):
                        f["status"] = "stopped"
                        running_processes.pop(fid, None)
                        save_db()
                        logger.warning(f"توقف البوت {fid} بشكل غير متوقع (PID: {pid})")
                        continue
                else:
                    f["status"] = "stopped"
                    running_processes.pop(fid, None)
                    save_db()
                    continue

                process_billing(fid, f)
        except Exception as e:
            logger.error(f"خطأ في حلقة الفوترة: {e}")

STORAGE_MONITOR_INTERVAL = 300

def monitor_storage_loop():
    while True:
        try:
            time.sleep(STORAGE_MONITOR_INTERVAL)
            logger.info("بدء فحص المساحة للمستخدمين...")

            users_to_check = set()
            for fid, f in db["files"].items():
                if f.get("status") == "running" or f.get("status") == "approved":
                    users_to_check.add(f["owner"])

            for uid in users_to_check:
                usage = container_manager.get_user_storage_usage(uid)
                if usage > MAX_STORAGE_MB:
                    logger.warning(f"المستخدم {uid} تجاوز حد المساحة: {usage} ميجابايت / {MAX_STORAGE_MB} ميجابايت")
                    for fid, f in list(db["files"].items()):
                        if f["owner"] == uid and f.get("status") == "running":
                            stop_hosted_bot(fid)
                            logger.info(f"تم إيقاف البوت {fid} للمستخدم {uid} بسبب تجاوز المساحة")
                            try:
                                bot.send_message(
                                    int(uid),
                                    f"⛔ تم إيقاف بوتك `{f['filename']}` تلقائياً بسبب تجاوز حد المساحة {MAX_STORAGE_MB} ميجابايت.\n"
                                    f"المساحة المستخدمة حالياً: {usage} ميجابايت.\n"
                                    "يرجى حذف بعض الملفات غير الضرورية وإعادة تشغيل البوت يدوياً."
                                )
                            except Exception as e:
                                logger.error(f"فشل إرسال إشعار للمستخدم {uid}: {e}")

        except Exception as e:
            logger.error(f"خطأ في حلقة مراقبة المساحة: {e}")

def cleanup_loop():
    while True:
        try:
            time.sleep(3600)
            container_manager.cleanup_stopped_containers()
            container_manager.cleanup_unused_images()
            clean_temp_decrypted_files()
            clean_orphaned_files()
        except Exception as e:
            logger.error(f"خطأ في حلقة التنظيف: {e}")

# ===================== معالجات البوت =====================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    logger.info(f"Received /start from user {message.from_user.id}")

    global bot_enabled
    if not bot_enabled and not is_admin(message.from_user.id):
        reply_q(message, "⛔ البوت متوقف حالياً، يرجى المحاولة لاحقاً.")
        return

    user_id = message.from_user.id
    if is_user_banned(user_id):
        reply_q(message, "🚫 أنت محظور من استخدام هذا البوت.")
        return

    args = message.text.split()
    ref_by = args[1][4:] if len(args) > 1 and args[1].startswith("ref_") else None
    ensure_user(user_id, message.from_user.username, ref_by)
    update_last_activity(user_id)

    ok, missing = check_force_sub(user_id)
    if not ok:
        kb = types.InlineKeyboardMarkup()
        for ch in missing:
            kb.add(types.InlineKeyboardButton(f"📢 اشترك في {ch}", url=f"https://t.me/{ch.lstrip('@')}"))
        kb.add(types.InlineKeyboardButton("✅ تحققت من الاشتراك", callback_data="check_sub", style="danger"))
        send_q(message.chat.id, "⚠️ خاصك تشترك فالقنوات التالية قبل الاستعمال:", reply_markup=kb)
        return

    welcome_photo = db["settings"].get("welcome_photo")
    welcome_message = db["settings"].get("welcome_message", "👋 مرحباً بك في بوت الاستضافة!")

    if welcome_photo:
        try:
            bot.send_photo(
                message.chat.id,
                welcome_photo,
                caption=q(welcome_message),
                reply_markup=main_menu_kb(user_id),
                parse_mode="HTML"
            )
            return
        except Exception as e:
            logger.warning(f"فشل إرسال الصورة الترحيبية: {e}")

    send_user_card(
        message.chat.id,
        user_id,
        welcome_message,
        reply_markup=main_menu_kb(user_id),
    )

@bot.message_handler(commands=["cancel"])
def cmd_cancel(message):
    if is_user_banned(message.from_user.id):
        reply_q(message, "🚫 أنت محظور.")
        return
    pending_action.pop(message.from_user.id, None)
    reply_q(message, "❌ تم إلغاء العملية الحالية.")

@bot.message_handler(content_types=["document"])
def handle_document(message):
    if not bot_enabled and not is_admin(message.from_user.id):
        reply_q(message, "⛔ البوت متوقف حالياً.")
        return
    user_id = message.from_user.id
    if is_user_banned(user_id):
        reply_q(message, "🚫 أنت محظور.")
        return

    action_data = pending_action.get(user_id, {})
    if action_data.get("action") == "awaiting_file_update":
        fid = action_data.get("fid")
        if not fid or fid not in db["files"]:
            reply_q(message, "❌ الملف غير موجود.")
            pending_action.pop(user_id, None)
            return
        f = db["files"][fid]
        doc = message.document
        if not doc.file_name.endswith((".py", ".js", ".php", ".zip")):
            reply_q(message, "❌ خاص يكون الملف بصيغة .py أو .js أو .php أو .zip فقط.")
            return
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        old_path = f["path"]
        try:
            os.remove(old_path)
        except Exception as e:
            logger.warning(f"فشل حذف الملف القديم {old_path}: {e}")
        with open(old_path, "wb") as new_f:
            new_f.write(downloaded)
        f["filename"] = doc.file_name
        f["uploaded_at"] = now_iso()
        f["file_ext"] = get_file_extension(doc.file_name)
        save_db()
        reply_q(message, "✅ تم تحديث ملف البوت بنجاح مع الحفاظ على جميع البيانات.")
        pending_action.pop(user_id, None)
        return

    if pending_action.get(user_id, {}).get("action") != "awaiting_file":
        reply_q(message, "📎 خاصك تضغط أولاً على «رفع ملف 📤» من القائمة قبل إرسال الملف.")
        return

    doc = message.document
    file_ext = get_file_extension(doc.file_name)

    # التحقق من الامتداد المدعوم
    if file_ext not in ("py", "js", "php", "zip"):
        reply_q(message, "❌ خاص يكون الملف بصيغة .py أو .js أو .php أو .zip فقط.")
        return

    # التحقق من النقاط
    if get_points(user_id) < db["settings"]["daily_cost"]:
        reply_q(message, f"❌ لا تملك نقاطاً كافية لرفع الملف. تحتاج على الأقل {db['settings']['daily_cost']} نقطة لتشغيل البوت ليوم واحد.")
        pending_action.pop(user_id, None)
        return

    file_info = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)
    fid = short_id()
    save_path = os.path.join(UPLOADS_DIR, f"{fid}_{doc.file_name}")
    with open(save_path, "wb") as f:
        f.write(downloaded)

    # تشفير الملف إذا كان متاحاً
    if CRYPTO_AVAILABLE:
        if encrypt_file(save_path):
            save_path = save_path + ".enc"
        else:
            logger.warning("فشل تشفير الملف المرفوع، سيتم حفظه بدون تشفير.")

    # تخزين الملف في قاعدة البيانات مع نوعه
    db["files"][fid] = {
        "owner": str(user_id),
        "filename": doc.file_name,
        "path": save_path,
        "status": "pending",
        "uploaded_at": now_iso(),
        "daily_billed": 0,
        "pid": None,
        "last_bill": None,
        "approved_at": None,
        "last_started": None,
        "file_ext": file_ext
    }
    save_db()
    pending_action.pop(user_id, None)

    # عرض أيقونة حسب النوع
    icon = get_file_type_icon(doc.file_name)
    ext_display = {
        "py": "بايثون 🐍",
        "js": "جافا سكريبت 🟨",
        "php": "بي إتش بي 🐘",
        "zip": "مضغوط 📦"
    }.get(file_ext, file_ext)

    reply_q(message, f"✅ تم رفع الملف بنجاح ({icon} {ext_display})، وسننتظر موافقة الإدارة لبدء التشغيل.")
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_file_{fid}", style="success"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_file_{fid}", style="success"),
    )
    username = message.from_user.username or ""
    caption = (
        "📤 طلب رفع جديد وصل للإدارة\n\n"
        f"👤 المستخدم: @{esc(username)} ({user_id})\n"
        f"📄 الملف: {esc(doc.file_name)}\n"
        f"📦 النوع: {ext_display} {icon}"
    )
    photo_id = get_user_photo_file_id(user_id)
    try:
        if photo_id:
            bot.send_photo(ADMIN_ID, photo_id, caption=q(caption), reply_markup=kb, parse_mode="HTML")
        bot.send_document(
            ADMIN_ID,
            doc.file_id,
            caption=q(f"📄 الملف المرفوع: {esc(doc.file_name)} ({ext_display})"),
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"فشل إرسال طلب الرفع للأدمن: {e}")
        bot.send_document(
            ADMIN_ID,
            doc.file_id,
            caption=q(f"📄 الملف المرفوع: {esc(doc.file_name)} ({ext_display})"),
            reply_markup=kb,
            parse_mode="HTML",
        )

def show_my_files(chat_id, user_id):
    user_files = {fid: f for fid, f in db["files"].items() if f["owner"] == str(user_id)}
    if not user_files:
        send_q(chat_id, "📁 ماعندك حتى ملف مرفوع حالياً.")
        return
    for fid, f in user_files.items():
        status_text = STATUS_AR.get(f.get('status', ''), f.get('status', 'غير معروف'))
        icon = get_file_type_icon(f.get('filename', ''))
        ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(f"{icon} {esc(f['filename'])} - {status_text}", callback_data=f"file_detail_{fid}"))
        send_q(chat_id, f"{icon} {esc(f['filename'])} [{ext}]", reply_markup=kb)

def show_file_detail(chat_id, user_id, fid):
    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if str(user_id) != f["owner"] and not is_admin(user_id):
        send_q(chat_id, "🔒 ماعندكش الصلاحية لعرض تفاصيل هذا الملف.")
        return

    status_text = STATUS_AR.get(f.get('status', ''), f.get('status', 'غير معروف'))
    icon = get_file_type_icon(f.get('filename', ''))
    ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
    ext_display = {
        "py": "بايثون 🐍",
        "js": "جافا سكريبت 🟨",
        "php": "بي إتش بي 🐘",
        "zip": "مضغوط 📦"
    }.get(ext, ext)

    info = (
        f"{icon} <b>{esc(f['filename'])}</b>\n\n"
        f"📌 الحالة: {status_text}\n"
        f"📦 النوع: {ext_display}\n"
        f"📅 تاريخ الرفع: {esc(f.get('uploaded_at', 'غير معروف'))}\n"
        f"📅 تاريخ الموافقة: {esc(f.get('approved_at', 'لم تتم بعد'))}\n"
        f"🧾 أيام الفوترة: {f.get('daily_billed', 0)}\n"
        f"🆔 PID: {f.get('pid', 'لا يوجد')}"
    )

    kb = types.InlineKeyboardMarkup(row_width=2)
    if f["status"] == "running":
        kb.add(types.InlineKeyboardButton("⏹️ إيقاف", callback_data=f"stop_file_{fid}", style="success"))
    elif f["status"] in ("approved", "stopped") and ext != "zip":
        kb.add(types.InlineKeyboardButton("▶️ تشغيل", callback_data=f"start_file_{fid}", style="danger"))
    kb.add(types.InlineKeyboardButton("🗑️ حذف", callback_data=f"del_file_{fid}", style="primary"))
    kb.add(types.InlineKeyboardButton("📋 سجل التشغيل", callback_data=f"file_log_{fid}", style="success"))
    if ext == "py":
        kb.add(types.InlineKeyboardButton("🔑 تغيير التوكن", callback_data=f"file_change_token_{fid}", style="danger"))
        kb.add(types.InlineKeyboardButton("🆔 تغيير معرف الأدمن", callback_data=f"file_change_admin_{fid}", style="primary"))
    kb.add(types.InlineKeyboardButton("🔄 تحديث البوت", callback_data=f"file_update_{fid}", style="success"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="my_files", style="danger"))

    send_q(chat_id, info, reply_markup=kb)

def show_file_log(chat_id, user_id, fid):
    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if str(user_id) != f["owner"] and not is_admin(user_id):
        send_q(chat_id, "🔒 ماعندكش الصلاحية لعرض السجل.")
        return
    log_path = container_manager.get_log_path(f["owner"], fid)
    if not os.path.exists(log_path):
        send_q(chat_id, "📋 لا يوجد سجل تشغيل لهذا البوت بعد.")
        return
    try:
        with open(log_path, "r", encoding="utf-8") as log_file:
            lines = log_file.readlines()
        last_lines = lines[-50:] if len(lines) > 50 else lines
        log_text = "".join(last_lines)
        if len(log_text) > 4000:
            with open(log_path, "rb") as f_log:
                bot.send_document(chat_id, f_log, caption=f"📋 سجل تشغيل {esc(f['filename'])}")
        else:
            send_q(chat_id, f"<b>سجل التشغيل (آخر {len(last_lines)} سطر):</b>\n<pre>{esc(log_text)}</pre>")
    except Exception as e:
        logger.error(f"خطأ في قراءة السجل: {e}")
        send_q(chat_id, "❌ حدث خطأ أثناء قراءة السجل.")

def change_file_token(chat_id, user_id, fid):
    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if str(user_id) != f["owner"] and not is_admin(user_id):
        send_q(chat_id, "🔒 ماعندكش الصلاحية.")
        return
    # فقط ملفات بايثون تدعم تغيير التوكن
    ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
    if ext != "py":
        send_q(chat_id, "❌ تغيير التوكن متاح فقط لملفات بايثون.")
        return
    pending_action[user_id] = {"action": "awaiting_token_change", "fid": fid}
    send_q(chat_id, "🔑 أرسل التوكن الجديد (مثال: <code>123456:ABC-DEF</code>):")

def change_file_admin(chat_id, user_id, fid):
    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if str(user_id) != f["owner"] and not is_admin(user_id):
        send_q(chat_id, "🔒 ماعندكش الصلاحية.")
        return
    ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
    if ext != "py":
        send_q(chat_id, "❌ تغيير معرف الأدمن متاح فقط لملفات بايثون.")
        return
    pending_action[user_id] = {"action": "awaiting_admin_change", "fid": fid}
    send_q(chat_id, "🔑 أرسل معرف الأدمن الجديد (رقم فقط):")

def update_file_prompt(chat_id, user_id, fid):
    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if str(user_id) != f["owner"] and not is_admin(user_id):
        send_q(chat_id, "🔒 ماعندكش الصلاحية.")
        return
    pending_action[user_id] = {"action": "awaiting_file_update", "fid": fid}
    send_q(chat_id, "📤 أرسل ملف البوت الجديد (بصيغة .py أو .js أو .php أو .zip) ليتم استبداله مع الحفاظ على جميع البيانات.")

def show_store(chat_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    for item_id, item in db["store"].items():
        kb.add(types.InlineKeyboardButton(f"🛍️ {item['name']} - {item['price']}", callback_data=f"buy_{item_id}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main", style="danger"))
    send_q(chat_id, "🛍️ اختر الباقة التي تناسبك من المتجر:", reply_markup=kb)

def handle_buy(chat_id, user_id, item_id):
    item = db["store"].get(item_id)
    if not item:
        send_q(chat_id, "❌ المنتج غير موجود.")
        return
    order_id = short_id()
    db["orders"][order_id] = {"user": str(user_id), "item_id": item_id, "status": "pending", "created": now_iso()}
    save_db()

    send_q(
        chat_id,
        (
            f"✅ تم تسجيل طلبك بنجاح.\n"
            f"📦 المنتج: {esc(item['name'])} - {esc(item['price'])}\n"
            f"📩 للتأكيد والدفع تواصل مع: {db['settings'].get('support_account', CONTACT_USERNAME)}"
        ),
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_order_{order_id}", style="success"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_order_{order_id}", style="success"),
    )
    username = db["users"].get(str(user_id), {}).get("username", "")
    admin_caption = (
        "🛒 طلب شراء جديد وصل للإدارة\n\n"
        f"👤 المستخدم: @{esc(username)} ({user_id})\n"
        f"📦 المنتج: {esc(item['name'])} - {esc(item['price'])}"
    )
    send_admin_user_card(ADMIN_ID, user_id, admin_caption, reply_markup=kb)
    send_to_trust_channel(f"🛒 طلب شراء جديد من @{esc(username)}: {esc(item['name'])}")

def show_account(chat_id, user_id):
    u = db["users"].get(str(user_id), {})
    n_files = len([f for f in db["files"].values() if f["owner"] == str(user_id)])
    caption = (
        "👤 <b>ملف حسابك</b>\n\n"
        f"🆔 الآيدي: <code>{user_id}</code>\n"
        f"💎 النقاط: <b>{u.get('points', 0)}</b>\n"
        f"📁 عدد الملفات: {n_files}\n"
        f"👥 الإحالات: {u.get('referrals', 0)}\n"
        f"📅 تاريخ الانضمام: {esc(u.get('joined', '')[:10])}"
    )
    send_user_card(chat_id, user_id, caption)

def handle_daily_gift(chat_id, user_id):
    u = db["users"][str(user_id)]
    last = u.get("last_daily")
    if last:
        try:
            elapsed = datetime.now() - datetime.fromisoformat(last)
            if elapsed < timedelta(hours=24):
                remain = timedelta(hours=24) - elapsed
                h = int(remain.total_seconds() // 3600)
                send_q(chat_id, f"⏳ خاصك تستنى {h} ساعة قبل ما تاخذ الهدية من جديد.")
                return
        except ValueError:
            pass
    gift = db["settings"]["daily_gift"]
    u["points"] += gift
    u["last_daily"] = now_iso()
    save_db()
    send_q(chat_id, f"🎁 مبروك! تربحت {gift} نقطة. رصيدك الحالي ولى {u['points']} نقطة.")

def show_vip_plans(chat_id):
    vips = db["settings"].get("vip_plans", [])
    if not vips:
        send_q(chat_id, "💎 لا توجد خطط VIP حالياً.")
        return
    kb = types.InlineKeyboardMarkup(row_width=2)
    for idx, plan in enumerate(vips):
        kb.add(types.InlineKeyboardButton(
            f"💎 {plan.get('name', '')} - {plan.get('price', '')}",
            callback_data=f"vip_buy_{idx}"
        ))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main", style="danger"))
    send_q(chat_id, "💎 اختر باقة VIP المناسبة لك:", reply_markup=kb)

def handle_vip_buy(chat_id, user_id, plan_idx):
    vips = db["settings"].get("vip_plans", [])
    try:
        plan = vips[int(plan_idx)]
    except (IndexError, ValueError):
        send_q(chat_id, "❌ الخطة غير موجودة.")
        return

    order_id = short_id()
    db["orders"][order_id] = {
        "user": str(user_id),
        "item_id": f"vip_{plan_idx}",
        "status": "pending",
        "created": now_iso(),
        "vip_plan": plan
    }
    save_db()

    send_q(
        chat_id,
        (
            f"✅ تم تسجيل طلب VIP بنجاح.\n"
            f"💎 الباقة: {esc(plan.get('name', ''))} - {esc(plan.get('price', ''))}\n"
            f"📩 للتأكيد والدفع تواصل مع: {db['settings'].get('support_account', CONTACT_USERNAME)}"
        ),
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_vip_{order_id}", style="success"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_vip_{order_id}", style="success"),
    )
    username = db["users"].get(str(user_id), {}).get("username", "")
    admin_caption = (
        "💎 طلب VIP جديد وصل للإدارة\n\n"
        f"👤 المستخدم: @{esc(username)} ({user_id})\n"
        f"💎 الباقة: {esc(plan.get('name', ''))} - {esc(plan.get('price', ''))}\n"
        f"📦 التفاصيل: {plan}"
    )
    send_admin_user_card(ADMIN_ID, user_id, admin_caption, reply_markup=kb)
    send_to_vip_channel(
        f"💎 طلب VIP جديد من @{esc(username)} ({user_id})\n"
        f"الباقة: {esc(plan.get('name', ''))} - {esc(plan.get('price', ''))}"
    )

def handle_vip_decision(chat_id, data):
    approve = data.startswith("approve_vip_")
    order_id = data[len("approve_vip_"):] if approve else data[len("reject_vip_"):]
    order = db["orders"].get(order_id)
    if not order:
        send_q(chat_id, "❌ الطلب غير موجود.")
        return
    if approve:
        order["status"] = "approved"
        points_to_add = 999999999
        add_points(int(order["user"]), points_to_add)
        send_q(chat_id, "✅ تم قبول طلب VIP.")
        send_to_vip_channel(f"✅ تم قبول طلب VIP #{order_id} للمستخدم {get_user_name(order['user'])}")
        try:
            send_user_card(
                int(order["user"]),
                int(order["user"]),
                f"🎉 تم قبول طلب VIP الخاص بك وتم إضافة {points_to_add} نقطة إلى رصيدك.",
            )
        except Exception as e:
            logger.error(f"فشل إرسال إشعار قبول VIP للمستخدم {order['user']}: {e}")
    else:
        order["status"] = "rejected"
        send_q(chat_id, "❌ تم رفض طلب VIP.")
        try:
            send_user_card(
                int(order["user"]),
                int(order["user"]),
                "❌ تم رفض طلب VIP الخاص بك.",
            )
        except Exception as e:
            logger.error(f"فشل إرسال إشعار رفض VIP للمستخدم {order['user']}: {e}")
    save_db()

def handle_file_decision(chat_id, data):
    approve = data.startswith("approve_file_")
    fid = data[len("approve_file_"):] if approve else data[len("reject_file_"):]
    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if approve:
        f["status"] = "approved"
        f["approved_at"] = now_iso()
        save_db()
        threading.Thread(target=start_hosted_bot, args=(fid,), daemon=True).start()
        send_q(chat_id, "✅ تمت الموافقة على الملف وجاري تشغيله في الخلفية.")

        owner_id = int(f["owner"])
        owner_name = get_user_name(owner_id)
        points = get_points(owner_id)
        daily_cost = db["settings"]["daily_cost"]
        expected_days = points // daily_cost if daily_cost > 0 else 0
        icon = get_file_type_icon(f.get('filename', ''))
        ext = f.get('file_ext', get_file_extension(f.get('filename', '')))

        message_text = (
            f"🚀 <b>تم تشغيل ملف جديد</b>\n\n"
            f"{icon} اسم الملف: <code>{esc(f['filename'])}</code>\n"
            f"📦 النوع: {ext}\n"
            f"👤 المالك: {esc(owner_name)}\n"
            f"🤖 يوزر البوت: @{BOT_USERNAME}\n"
            f"🆔 رقم الطلب: <code>{fid}</code>\n"
            f"💎 رصيد النقاط: {points} نقطة\n"
            f"⏳ ساعات التشغيل المتوقعة: {expected_days} ساعة (التكلفة: {daily_cost} نقطة/يوم)"
        )
        send_to_trust_channel(message_text)

        try:
            send_user_card(
                owner_id,
                owner_id,
                f"🎉 تم قبول وتشغيل ملفك بنجاح.\n\n📄 الاسم: {esc(f['filename'])}\n📦 النوع: {ext}",
            )
        except Exception as e:
            logger.error(f"فشل إرسال إشعار الموافقة للمستخدم {f['owner']}: {e}")
    else:
        f["status"] = "rejected"
        save_db()
        send_q(chat_id, "❌ تم رفض الملف.")
        try:
            send_user_card(
                int(f["owner"]),
                int(f["owner"]),
                f"📄 تم رفض ملفك.\n\nاسم الملف: {esc(f['filename'])}",
            )
        except Exception as e:
            logger.error(f"فشل إرسال إشعار الرفض للمستخدم {f['owner']}: {e}")

def handle_file_action(chat_id, user_id, data):
    if data.startswith("stop_file_"):
        fid, act = data[len("stop_file_"):], "stop"
    elif data.startswith("start_file_"):
        fid, act = data[len("start_file_"):], "start"
    elif data.startswith("del_file_"):
        fid, act = data[len("del_file_"):], "del"
    else:
        return

    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if str(user_id) != f["owner"] and not is_admin(user_id):
        send_q(chat_id, "🔒 ماعندكش الصلاحية لتنفيذ هاد العملية.")
        return

    ext = f.get('file_ext', get_file_extension(f.get('filename', '')))

    if act == "stop":
        stop_hosted_bot(fid)
        send_q(chat_id, "⏹️ تم إيقاف البوت بنجاح.")
    elif act == "start":
        if ext == "zip":
            send_q(chat_id, "📦 هذا ملف ZIP، سيتم استخراجه تلقائياً عند الموافقة.")
            return
        if get_points(int(f["owner"])) < db["settings"]["daily_cost"]:
            send_q(chat_id, "❌ النقاط ماكافيين لتشغيله ليوم كامل.")
            return
        threading.Thread(target=start_hosted_bot, args=(fid,), daemon=True).start()
        send_q(chat_id, "▶️ جاري تشغيل البوت في الخلفية.")
    else:
        stop_hosted_bot(fid)
        try:
            if os.path.exists(f["path"]):
                os.remove(f["path"])
        except Exception as e:
            logger.error(f"فشل حذف الملف {f['path']}: {e}")
        db["files"].pop(fid, None)
        save_db()
        send_q(chat_id, "🗑️ تم حذف الملف نهائياً.")

def handle_order_decision(chat_id, data):
    approve = data.startswith("approve_order_")
    order_id = data[len("approve_order_"):] if approve else data[len("reject_order_"):]
    order = db["orders"].get(order_id)
    if not order:
        send_q(chat_id, "❌ الطلب غير موجود.")
        return
    item = db["store"].get(order["item_id"], {})
    if approve:
        order["status"] = "approved"
        add_points(int(order["user"]), item.get("points", 0))
        send_q(chat_id, "✅ تم قبول الطلب وإضافة النقاط.")
        send_to_trust_channel(f"✅ تم قبول طلب شراء: {esc(item.get('name', ''))} (المستخدم: {get_user_name(order['user'])})")
        try:
            send_user_card(
                int(order["user"]),
                int(order["user"]),
                f"🎁 تم تأكيد طلبك بنجاح.\n\n💎 تمت إضافة {item.get('points', 0)} نقطة إلى رصيدك.",
            )
        except Exception as e:
            logger.error(f"فشل إرسال إشعار قبول الطلب للمستخدم {order['user']}: {e}")
    else:
        order["status"] = "rejected"
        send_q(chat_id, "❌ تم رفض الطلب.")
        try:
            send_user_card(
                int(order["user"]),
                int(order["user"]),
                "📦 تم رفض طلب الشراء ديالك.",
            )
        except Exception as e:
            logger.error(f"فشل إرسال إشعار رفض الطلب للمستخدم {order['user']}: {e}")
    save_db()

def handle_admin_callback(chat_id, user_id, data):
    if data == "admin_upload_requests":
        pending = {fid: f for fid, f in db["files"].items() if f["status"] == "pending"}
        if not pending:
            send_q(chat_id, "📂 ماكاين حتى طلب رفع قيد الانتظار.")
            return
        for fid, f in pending.items():
            icon = get_file_type_icon(f.get('filename', ''))
            ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_file_{fid}", style="success"),
                types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_file_{fid}", style="success"),
            )
            send_q(chat_id, f"{icon} ملف جديد: {esc(f['filename'])} [{ext}]\n👤 المالك: {get_user_name(f['owner'])}", reply_markup=kb)

    elif data == "admin_order_requests":
        pending = {oid: o for oid, o in db["orders"].items() if o["status"] == "pending"}
        if not pending:
            send_q(chat_id, "🛍️ ماكاينين حتى طلبات شراء فالانتظار.")
            return
        for oid, o in pending.items():
            item = db["store"].get(o["item_id"], {})
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_order_{oid}", style="success"),
                types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_order_{oid}", style="success"),
            )
            send_q(chat_id, f"🛒 {esc(item.get('name', ''))} - {esc(item.get('price', ''))}\n👤 من: {get_user_name(o['user'])}", reply_markup=kb)

    elif data == "admin_users":
        total = len(db["users"])
        active = len([u for u in db["users"].values() if u.get("points", 0) > 0])
        send_q(chat_id, f"👥 <b>إحصائيات المستخدمين</b>\n\nإجمالي: {total}\nنشطاء (لديهم نقاط): {active}")

    elif data == "admin_free_plan":
        db["settings"]["free_plan"] = not db["settings"]["free_plan"]
        save_db()
        state = "مفعلة ✅" if db["settings"]["free_plan"] else "معطلة ❌"
        send_q(chat_id, f"🎁 حالة الخطة المجانية: {state}\n💎 نقاط البداية: {db['settings']['free_points']}")

    elif data == "admin_broadcast":
        pending_action[user_id] = {"action": "awaiting_broadcast"}
        send_q(chat_id, "📣 اكتب الرسالة التي تريد إرسالها إلى جميع المستخدمين:")

    elif data == "admin_all_files":
        try:
            if not db["files"]:
                send_q(chat_id, "📁 ماكاين حتى ملفات مسجلة.")
                return
            for fid, f in db["files"].items():
                status_text = STATUS_AR.get(f.get('status', ''), f.get('status', 'غير معروف'))
                icon = get_file_type_icon(f.get('filename', ''))
                ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
                kb = types.InlineKeyboardMarkup()
                kb.add(
                    types.InlineKeyboardButton("⏹️ إيقاف", callback_data=f"stop_file_{fid}", style="success"),
                    types.InlineKeyboardButton("🗑️ حذف", callback_data=f"del_file_{fid}", style="success"),
                )
                owner_name = get_user_name(f['owner'])
                send_q(
                    chat_id,
                    f"{icon} <b>{esc(f['filename'])}</b> [{ext}]\n"
                    f"الحالة: {status_text}\n"
                    f"المالك: {owner_name}",
                    reply_markup=kb
                )
        except Exception as e:
            logger.error(f"خطأ في عرض كل الملفات: {e}")
            send_q(chat_id, "حدث خطأ أثناء جلب الملفات، حاول مرة أخرى.")

    elif data == "admin_manage_store":
        kb = types.InlineKeyboardMarkup(row_width=2)
        for iid, item in db["store"].items():
            kb.add(types.InlineKeyboardButton(f"🗑️ حذف: {item['name']}", callback_data=f"delitem_{iid}"))
        kb.add(types.InlineKeyboardButton("➕ إضافة منتج", callback_data="additem", style="danger"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel", style="primary"))
        send_q(chat_id, "🛒 <b>إدارة المتجر</b>", reply_markup=kb)

    elif data == "additem":
        pending_action[user_id] = {"action": "awaiting_new_item"}
        send_q(chat_id, "➕ أرسل بيانات المنتج بهذا الشكل:\n<code>الاسم|عدد النقاط|السعر</code>\nمثال: 200 نقطة|200|15 درهم")

    elif data.startswith("delitem_"):
        item_id = data[len("delitem_"):]
        if item_id in db["store"]:
            del db["store"][item_id]
            save_db()
            send_q(chat_id, "🗑️ تم حذف المنتج بنجاح.")
        else:
            send_q(chat_id, "❌ المنتج غير موجود.")

    elif data == "admin_points_settings":
        pending_action[user_id] = {"action": "awaiting_daily_cost"}
        send_q(chat_id, f"💰 التكلفة اليومية الحالية: {db['settings']['daily_cost']} نقطة\nأرسل القيمة الجديدة (رقم فقط):")

    elif data == "admin_daily_gift_settings":
        pending_action[user_id] = {"action": "awaiting_daily_gift"}
        send_q(chat_id, f"🎁 الهدية اليومية الحالية: {db['settings']['daily_gift']} نقطة\nأرسل القيمة الجديدة (رقم فقط):")

    elif data == "admin_channels":
        channels = db["settings"]["channels"]
        text = "📡 <b>القنوات المطلوب الاشتراك فيها:</b>\n" + ("\n".join(channels) if channels else "لا توجد قنوات.")
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➕ إضافة قناة", callback_data="add_channel", style="success"))
        kb.add(types.InlineKeyboardButton("🗑️ حذف قناة", callback_data="remove_channel", style="danger"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel", style="primary"))
        send_q(chat_id, text, reply_markup=kb)

    elif data == "add_channel":
        pending_action[user_id] = {"action": "awaiting_channel"}
        send_q(chat_id, "➕ أرسل يوزر القناة.\nمثال: <code>@mychannel</code>")

    elif data == "remove_channel":
        pending_action[user_id] = {"action": "awaiting_remove_channel"}
        send_q(chat_id, "❌ أرسل يوزر القناة التي تريد حذفها.\nمثال: <code>@mychannel</code>")

    elif data == "admin_settings":
        s = db["settings"]
        send_q(
            chat_id,
            (
                f"⚙️ <b>الإعدادات الحالية</b>\n\n"
                f"💰 التكلفة اليومية: {s['daily_cost']} نقطة\n"
                f"🎁 الخطة المجانية: {'مفعلة ✅' if s['free_plan'] else 'معطلة ❌'}\n"
                f"💎 نقاط البداية: {s['free_points']}\n"
                f"🎁 الهدية اليومية: {s['daily_gift']}\n"
                f"🔗 مكافأة الإحالة: {s['referral_bonus']}\n"
                f"📦 الحد الأقصى للنسخ الاحتياطي: {s.get('max_backups', 200)}"
            ),
        )

    elif data == "admin_system_stats":
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            processes = len(running_processes)
            stats = (
                f"📊 <b>إحصائيات النظام</b>\n\n"
                f"🖥 المعالج: {cpu:.1f}%\n"
                f"🧠 الذاكرة: {mem.used // (1024**2)} / {mem.total // (1024**2)} ميجابايت\n"
                f"💾 القرص: {disk.used // (1024**3)} / {disk.total // (1024**3)} جيجابايت\n"
                f"🔄 العمليات النشطة: {processes}"
            )
        except ImportError:
            stats = "⚠️ مكتبة psutil غير مثبتة، لا يمكن عرض إحصائيات النظام."
        except Exception as e:
            logger.error(f"خطأ في إحصائيات النظام: {e}")
            stats = "❌ حدث خطأ أثناء جلب الإحصائيات."
        send_q(chat_id, stats)

    elif data == "admin_pinned_announcement":
        current = db["settings"].get("pinned_announcement") or "لا يوجد إعلان مثبت"
        pending_action[user_id] = {"action": "awaiting_pinned_announcement"}
        send_q(chat_id, f"📌 الإعلان المثبت الحالي:\n{current}\n\nأرسل النص الجديد للإعلان (أو /cancel للإلغاء):")

    elif data == "admin_welcome_photo":
        pending_action[user_id] = {"action": "awaiting_welcome_photo"}
        send_q(chat_id, "🖼 أرسل الصورة التي تريدها كصورة ترحيبية (صورة أو مستند صورة).")

    elif data == "admin_welcome_message":
        current = db["settings"].get("welcome_message", "👋 مرحباً بك في بوت الاستضافة!")
        pending_action[user_id] = {"action": "awaiting_welcome_message"}
        send_q(chat_id, f"📝 الرسالة الترحيبية الحالية:\n{current}\n\nأرسل النص الجديد:")

    elif data == "admin_support_account":
        current = db["settings"].get("support_account", CONTACT_USERNAME)
        pending_action[user_id] = {"action": "awaiting_support_account"}
        send_q(chat_id, f"📞 حساب الدعم الحالي: {current}\nأرسل الحساب الجديد (مثال: @username):")

    elif data == "admin_trust_channel":
        current = db["settings"].get("trust_channel") or "غير محدد"
        pending_action[user_id] = {"action": "awaiting_trust_channel"}
        send_q(chat_id, f"📡 قناة الثقة الحالية: {current}\nأرسل يوزر القناة الجديد (بدون @) أو Chat ID (مثل -100123456) أو 'إلغاء' لإلغائها:")

    elif data == "admin_ban_management":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user", style="success"),
            types.InlineKeyboardButton("✅ فك حظر مستخدم", callback_data="admin_unban_user", style="success"),
            types.InlineKeyboardButton("📋 قائمة المحظورين", callback_data="admin_banned_list", style="success"),
        )
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel", style="danger"))
        send_q(chat_id, "🚫 <b>إدارة الحظر</b>", reply_markup=kb)

    elif data == "admin_ban_user":
        pending_action[user_id] = {"action": "awaiting_ban_user"}
        send_q(chat_id, "🚫 أرسل آيدي المستخدم الذي تريد حظره:")

    elif data == "admin_unban_user":
        pending_action[user_id] = {"action": "awaiting_unban_user"}
        send_q(chat_id, "✅ أرسل آيدي المستخدم الذي تريد فك حظره:")

    elif data == "admin_banned_list":
        banned = [uid for uid, u in db["users"].items() if u.get("banned")]
        if not banned:
            send_q(chat_id, "📋 لا يوجد مستخدمون محظورون.")
        else:
            text = "🚫 <b>قائمة المحظورين:</b>\n" + "\n".join([f"🆔 {uid} - {get_user_name(uid)}" for uid in banned])
            send_q(chat_id, text)

    elif data == "admin_manage_admins":
        admins = db.get("admins", [ADMIN_ID])
        text = "👥 <b>الأدمن الحاليون:</b>\n" + "\n".join([f"🆔 {aid}" for aid in admins])
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➕ إضافة أدمن", callback_data="admin_add_admin", style="success"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel", style="danger"))
        send_q(chat_id, text, reply_markup=kb)

    elif data == "admin_add_admin":
        pending_action[user_id] = {"action": "awaiting_add_admin"}
        send_q(chat_id, "➕ أرسل آيدي المستخدم الذي تريد إضافته كأدمن:")

    elif data == "admin_detailed_stats":
        total_users = len(db["users"])
        total_files = len(db["files"])
        pending_files = len([f for f in db["files"].values() if f["status"] == "pending"])
        running_files = len([f for f in db["files"].values() if f["status"] == "running"])
        total_orders = len(db["orders"])
        pending_orders = len([o for o in db["orders"].values() if o["status"] == "pending"])
        approved_orders = len([o for o in db["orders"].values() if o["status"] == "approved"])
        total_points = sum(u.get("points", 0) for u in db["users"].values())
        banned_count = len([u for u in db["users"].values() if u.get("banned")])
        active_today = len([u for u in db["users"].values() if u.get("last_activity") and datetime.fromisoformat(u["last_activity"]) > datetime.now() - timedelta(days=1)])

        stats = (
            f"📊 <b>إحصائيات تفصيلية</b>\n\n"
            f"👥 إجمالي المستخدمين: {total_users}\n"
            f"🟢 نشطاء اليوم: {active_today}\n"
            f"🚫 محظورون: {banned_count}\n"
            f"📄 إجمالي الملفات: {total_files}\n"
            f"   - قيد الانتظار: {pending_files}\n"
            f"   - قيد التشغيل: {running_files}\n"
            f"🛒 إجمالي الطلبات: {total_orders}\n"
            f"   - معلقة: {pending_orders}\n"
            f"   - مقبولة: {approved_orders}\n"
            f"💎 إجمالي النقاط: {total_points}\n"
            f"🔄 العمليات النشطة: {len(running_processes)}"
        )
        send_q(chat_id, stats)

    elif data == "admin_export_orders":
        csv_data = export_orders_to_csv()
        if not csv_data:
            send_q(chat_id, "📋 لا توجد طلبات لتصديرها.")
            return
        try:
            bot.send_document(chat_id, ("orders.csv", csv_data), caption="📋 تصدير الطلبات بصيغة CSV")
        except Exception as e:
            logger.error(f"فشل إرسال ملف التصدير: {e}")
            send_q(chat_id, "❌ حدث خطأ أثناء التصدير.")

    elif data == "admin_backup":
        backup_path = backup_uploaded_files()
        if not backup_path:
            send_q(chat_id, "📦 لا توجد ملفات للنسخ الاحتياطي.")
            return
        try:
            with open(backup_path, 'rb') as f:
                bot.send_document(chat_id, f, caption="📦 نسخة احتياطية للملفات المرفوعة")
            os.remove(backup_path)
        except Exception as e:
            logger.error(f"فشل إرسال النسخة الاحتياطية: {e}")
            send_q(chat_id, "❌ حدث خطأ أثناء النسخ الاحتياطي.")

    elif data == "admin_toggle_bot":
        global bot_enabled
        bot_enabled = not bot_enabled
        status = "مفعل ✅" if bot_enabled else "معطل ❌"
        send_q(chat_id, f"🔘 حالة البوت: {status}")

    elif data == "admin_accepted_orders":
        accepted = {oid: o for oid, o in db["orders"].items() if o["status"] == "approved"}
        if not accepted:
            send_q(chat_id, "📋 لا توجد طلبات مقبولة.")
            return
        for oid, o in accepted.items():
            item = db["store"].get(o["item_id"], {})
            send_q(chat_id, f"🛒 طلب #{oid}\n📦 {esc(item.get('name', ''))}\n👤 {get_user_name(o['user'])}\n📅 {o.get('created', '')}")

    elif data == "admin_pending_orders":
        pending = {oid: o for oid, o in db["orders"].items() if o["status"] == "pending"}
        if not pending:
            send_q(chat_id, "📋 لا توجد طلبات معلقة.")
            return
        for oid, o in pending.items():
            item = db["store"].get(o["item_id"], {})
            send_q(chat_id, f"🛒 طلب #{oid}\n📦 {esc(item.get('name', ''))}\n👤 {get_user_name(o['user'])}\n📅 {o.get('created', '')}")

    elif data == "admin_find_order":
        pending_action[user_id] = {"action": "awaiting_find_order"}
        send_q(chat_id, "🔍 أرسل رقم الطلب (الـ ID) الذي تريد البحث عنه:")

    elif data == "admin_latest_users":
        users = sorted(db["users"].items(), key=lambda x: x[1].get("joined", ""), reverse=True)[:10]
        if not users:
            send_q(chat_id, "📋 لا يوجد مستخدمون.")
            return
        text = "🆕 <b>أحدث المستخدمين:</b>\n"
        for uid, u in users:
            text += f"🆔 {uid} - {u.get('username', 'بدون اسم')} (📅 {u.get('joined', '')[:10]})\n"
        send_q(chat_id, text)

    elif data == "admin_all_users_list":
        users = list(db["users"].items())
        if not users:
            send_q(chat_id, "📋 لا يوجد مستخدمون.")
            return
        page = 0
        pending_action[user_id] = {"action": "view_users_page", "page": 0}
        show_users_page(chat_id, user_id, 0)

    elif data == "admin_send_message":
        pending_action[user_id] = {"action": "awaiting_send_user_id"}
        send_q(chat_id, "📨 أرسل آيدي المستخدم المستهدف (أو @username) ثم الرسالة في سطر جديد.\nمثال:\n<code>123456\nنص الرسالة</code>")

    elif data == "admin_active_users":
        active = [uid for uid, u in db["users"].items() if u.get("last_activity") and datetime.fromisoformat(u["last_activity"]) > datetime.now() - timedelta(days=7)]
        if not active:
            send_q(chat_id, "🌟 لا يوجد مستخدمون نشطون خلال الأسبوع الماضي.")
        else:
            text = "🌟 <b>المستخدمون النشطون (آخر 7 أيام):</b>\n" + "\n".join([f"🆔 {uid} - {get_user_name(uid)}" for uid in active[:20]])
            send_q(chat_id, text)

    elif data == "admin_manage_subscriptions":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("💰 تعديل أسعار الاشتراكات", callback_data="admin_edit_subscription_prices", style="success"))
        kb.add(types.InlineKeyboardButton("💎 إدارة VIP", callback_data="admin_manage_vip", style="danger"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel", style="primary"))
        send_q(chat_id, "🔄 <b>إدارة الاشتراكات</b>", reply_markup=kb)

    elif data == "admin_edit_subscription_prices":
        store = db["store"]
        if not store:
            send_q(chat_id, "🛒 لا توجد منتجات حالياً.")
            return
        for iid, item in store.items():
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("✏️ تعديل السعر", callback_data=f"edit_price_{iid}", style="success"))
            send_q(chat_id, f"📦 {esc(item['name'])}\n💰 السعر: {esc(item['price'])}", reply_markup=kb)
        kb_back = types.InlineKeyboardMarkup()
        kb_back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_subscriptions", style="success"))
        send_q(chat_id, "اختر منتجاً لتعديل سعره:", reply_markup=kb_back)

    elif data.startswith("edit_price_"):
        item_id = data[len("edit_price_"):]
        if item_id not in db["store"]:
            send_q(chat_id, "❌ المنتج غير موجود.")
            return
        pending_action[user_id] = {"action": "awaiting_edit_price", "item_id": item_id}
        send_q(chat_id, f"💰 أرسل السعر الجديد للمنتج {esc(db['store'][item_id]['name'])}:")

    elif data == "admin_manage_vip":
        vips = db["settings"].get("vip_plans", [])
        if not vips:
            text = "💎 لا توجد خطط VIP حالياً."
        else:
            text = "💎 <b>خطط VIP الحالية:</b>\n"
            for idx, plan in enumerate(vips):
                text += f"{idx+1}. {plan.get('name', '')} - {plan.get('price', '')} - {plan.get('points', 0)} نقطة\n"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➕ إضافة خطة VIP", callback_data="admin_add_vip_plan", style="success"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_subscriptions", style="danger"))
        send_q(chat_id, text, reply_markup=kb)

    elif data == "admin_add_vip_plan":
        pending_action[user_id] = {"action": "awaiting_vip_plan"}
        send_q(chat_id, "➕ أرسل بيانات خطة VIP بهذا الشكل:\n<code>الاسم|السعر|عدد النقاط</code>\nمثال: VIP شهري|50 درهم|500")

    elif data == "admin_backup_settings":
        current = db["settings"].get("max_backups", 200)
        pending_action[user_id] = {"action": "awaiting_max_backups"}
        send_q(chat_id, f"📦 الحد الأقصى لعدد النسخ الاحتياطية: {current}\nأرسل الرقم الجديد (عدد صحيح):")

def show_users_page(chat_id, user_id, page):
    users = list(db["users"].items())
    page_size = 20
    total = len(users)
    start = page * page_size
    end = min(start + page_size, total)
    if start >= total:
        send_q(chat_id, "📋 لا توجد صفحات إضافية.")
        return
    text = "👥 <b>قائمة المستخدمين:</b>\n"
    for uid, u in users[start:end]:
        text += f"🆔 {uid} - {u.get('username', 'بدون اسم')} (💎 {u.get('points',0)})\n"
    kb = types.InlineKeyboardMarkup(row_width=2)
    if page > 0:
        kb.add(types.InlineKeyboardButton("⬅️ السابق", callback_data=f"users_page_{page-1}", style="success"))
    if end < total:
        kb.add(types.InlineKeyboardButton("➡️ التالي", callback_data=f"users_page_{page+1}", style="danger"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel", style="primary"))
    send_q(chat_id, text, reply_markup=kb)

# ===================== دوال الـ Callback =====================
@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    global bot_enabled
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    if not bot_enabled and not is_admin(user_id):
        bot.answer_callback_query(call.id, "⛔ البوت متوقف حالياً.", show_alert=True)
        return

    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "🚫 أنت محظور.", show_alert=True)
        return

    ensure_user(user_id, call.from_user.username)
    update_last_activity(user_id)

    now = time.time()
    if user_id in cooldown and now - cooldown[user_id] < 2:
        bot.answer_callback_query(call.id, "⏳ انتظر قليلاً قبل الضغط مجدداً.", show_alert=True)
        return
    cooldown[user_id] = now

    try:
        bot.answer_callback_query(call.id)

        if data == "support":
            support = db["settings"].get("support_account", CONTACT_USERNAME)
            if support:
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("📞 تواصل مع الدعم", url=f'https://t.me/{support.lstrip("@")}'))
                send_q(chat_id, f"📞 حساب الدعم: {support}", reply_markup=kb)
            else:
                send_q(chat_id, "📞 لم يتم تعيين حساب دعم بعد.")

        elif data == "trust_channel":
            channel = db["settings"].get("trust_channel")
            if channel:
                kb = types.InlineKeyboardMarkup()
                kb.add(
                    types.InlineKeyboardButton(
                        "📢 افتح قناة الثقة",
                        url="https://t.me/mouhamed_maa"
                    )
                )
                send_q(chat_id, f"📢 قناة الثقة: {channel}", reply_markup=kb)
            else:
                send_q(chat_id, "📢 لم يتم تعيين قناة ثقة بعد.")

        elif data == "check_sub":
            ok, _ = check_force_sub(user_id)
            if ok:
                edit_q("✅ تم التحقق بنجاح، اختَر من القائمة.", chat_id, call.message.message_id, reply_markup=main_menu_kb(user_id))
            else:
                bot.answer_callback_query(call.id, "❌ مازال خاصك تشترك فالقنوات.", show_alert=True)

        elif data == "back_main":
            edit_q("🏠 رجعنا للقائمة الرئيسية.", chat_id, call.message.message_id, reply_markup=main_menu_kb(user_id))

        elif data == "upload_file":
            pending_action[user_id] = {"action": "awaiting_file"}
            send_q(
                chat_id,
                (
                    f"📤 أرسل ملف بايثون (.py) أو جافا سكريبت (.js) أو PHP (.php) أو ZIP (.zip) الآن.\n"
                    f"📅 تكلفة التشغيل اليومية: {db['settings']['daily_cost']} نقطة.\n"
                    f"💎 رصيدك الحالي: {get_points(user_id)}"
                ),
            )

        elif data == "my_files":
            show_my_files(chat_id, user_id)

        elif data == "store":
            show_store(chat_id)

        elif data.startswith("buy_"):
            handle_buy(chat_id, user_id, data[len("buy_"):])

        elif data == "vip_plans":
            show_vip_plans(chat_id)

        elif data.startswith("vip_buy_"):
            plan_idx = data[len("vip_buy_"):]
            handle_vip_buy(chat_id, user_id, plan_idx)

        elif data.startswith("approve_vip_") or data.startswith("reject_vip_"):
            if is_admin(user_id):
                handle_vip_decision(chat_id, data)

        elif data == "my_account":
            show_account(chat_id, user_id)

        elif data == "instructions":
            send_q(
                chat_id,
                (
                    "📖 <b>طريقة الاستعمال</b>\n\n"
                    "1️⃣ اضغط على «رفع ملف 📤» وأرسل ملف البوت بصيغة .py أو .js أو .php أو .zip.\n"
                    f"2️⃣ يتم خصم {db['settings']['daily_cost']} نقطة يومياً أثناء التشغيل.\n"
                    "3️⃣ بعد الموافقة، يبدأ البوت بالعمل تلقائياً.\n"
                    "4️⃣ ادعُ الأصدقاء لتحصل على نقاط إضافية والهدايا اليومية.\n"
                    "5️⃣ عند نفاد الرصيد، يتوقف البوت تلقائياً."
                ),
            )

        elif data == "my_points":
            send_q(
                chat_id,
                f"💎 رصيدك الحالي: <b>{get_points(user_id)}</b> نقطة\n"
                f"📅 تكلفة التشغيل اليومية: {db['settings']['daily_cost']} نقطة",
            )

        elif data == "invite":
            link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
            bonus = db["settings"]["referral_bonus"]
            send_q(
                chat_id,
                f"🔗 <b>رابط الدعوة الخاص بك:</b>\n<code>{link}</code>\n\n🎁 كل صديق يدخل من رابطك = {bonus} نقطة لك!",
            )

        elif data == "daily_gift":
            handle_daily_gift(chat_id, user_id)

        elif data == "ask_admin":
            pending_action[user_id] = {"action": "awaiting_question"}
            send_q(chat_id, "💬 اكتب سؤالك الآن وسيصل مباشرة إلى الإدارة.")

        elif data == "admin_panel" and is_admin(user_id):
            edit_q("🛡️ <b>لوحة الإدارة</b>", chat_id, call.message.message_id, reply_markup=admin_menu_kb())

        elif data.startswith("approve_file_") or data.startswith("reject_file_"):
            if is_admin(user_id):
                handle_file_decision(chat_id, data)

        elif data.startswith("stop_file_") or data.startswith("start_file_") or data.startswith("del_file_"):
            handle_file_action(chat_id, user_id, data)

        elif data.startswith("approve_order_") or data.startswith("reject_order_"):
            if is_admin(user_id):
                handle_order_decision(chat_id, data)

        elif data.startswith("users_page_"):
            page = int(data.split("_")[2])
            show_users_page(chat_id, user_id, page)

        elif data.startswith("file_detail_"):
            fid = data[len("file_detail_"):]
            show_file_detail(chat_id, user_id, fid)

        elif data.startswith("file_log_"):
            fid = data[len("file_log_"):]
            show_file_log(chat_id, user_id, fid)

        elif data.startswith("file_change_token_"):
            fid = data[len("file_change_token_"):]
            change_file_token(chat_id, user_id, fid)

        elif data.startswith("file_change_admin_"):
            fid = data[len("file_change_admin_"):]
            change_file_admin(chat_id, user_id, fid)

        elif data.startswith("file_update_"):
            fid = data[len("file_update_"):]
            update_file_prompt(chat_id, user_id, fid)

        elif data == "rules":
            send_q(chat_id, RULES_TEXT)

        elif data == "help":
            send_q(chat_id, HELP_TEXT)

        elif data == "admin_send_points" and is_admin(user_id):
            pending_action[user_id] = {"action": "awaiting_send_points_user"}
            send_q(chat_id, "➕ أرسل آيدي المستخدم الذي تريد إضافة نقاط له:")

        elif (data.startswith("admin_") or data in ("additem", "add_channel", "remove_channel") or data.startswith("delitem_") or data.startswith("edit_price_")) and is_admin(user_id):
            handle_admin_callback(chat_id, user_id, data)

    except Exception as e:
        logger.error(f"خطأ في معالجة الـ callback {data} من المستخدم {user_id}: {e}")
        try:
            bot.send_message(chat_id, "حدث خطأ أثناء معالجة طلبك، حاول مرة أخرى.")
        except:
            pass

# ===================== دوال الرسائل النصية المعلقة =====================
@bot.message_handler(func=lambda m: m.from_user.id in pending_action, content_types=["text"])
def handle_pending_text(message):
    user_id = message.from_user.id
    action = pending_action[user_id].get("action")

    if is_user_banned(user_id):
        reply_q(message, "🚫 أنت محظور.")
        pending_action.pop(user_id, None)
        return

    try:
        if action == "awaiting_broadcast" and is_admin(user_id):
            count = 0
            for uid in list(db["users"].keys()):
                try:
                    send_q(
                        int(uid),
                        (
                            "📣 <b>إعلان جديد من الإدارة</b>\n\n"
                            f"{esc(message.text)}"
                        ),
                    )
                    count += 1
                except Exception as e:
                    logger.warning(f"فشل إرسال الإذاعة للمستخدم {uid}: {e}")
            reply_q(message, f"✅ تم إرسال الإذاعة إلى {count} مستخدم.")

        elif action == "awaiting_question":
            username = message.from_user.username or "بدون_يوزر"
            admin_caption = (
                "💬 <b>سؤال جديد من مستخدم</b>\n\n"
                f"👤 اليوزر: @{esc(username)}\n"
                f"🆔 الآيدي: {user_id}\n\n"
                f"📝 السؤال:\n{esc(message.text)}"
            )
            sent_msg = bot.send_message(
                ADMIN_ID,
                q(admin_caption),
                parse_mode="HTML"
            )
            question_messages[sent_msg.message_id] = user_id
            reply_q(message, "✅ وصل سؤالك للإدارة، وانتظر الرد.")

        elif action == "awaiting_new_item" and is_admin(user_id):
            try:
                name, points, price = message.text.split("|")
                db["store"][short_id()] = {"name": name.strip(), "points": int(points.strip()), "price": price.strip()}
                save_db()
                reply_q(message, "✅ تمت إضافة المنتج بنجاح.")
            except ValueError:
                reply_q(message, "❌ الصيغة غير صحيحة. استعمل: <code>الاسم|النقاط|السعر</code>")
            except Exception as e:
                logger.error(f"خطأ في إضافة منتج: {e}")
                reply_q(message, "❌ حدث خطأ أثناء إضافة المنتج.")

        elif action == "awaiting_daily_cost" and is_admin(user_id):
            try:
                db["settings"]["daily_cost"] = int(message.text.strip())
                save_db()
                reply_q(message, "✅ تم تحديث التكلفة اليومية بنجاح.")
            except ValueError:
                reply_q(message, "❌ خاصك تكتب رقم فقط.")

        elif action == "awaiting_daily_gift" and is_admin(user_id):
            try:
                db["settings"]["daily_gift"] = int(message.text.strip())
                save_db()
                reply_q(message, "✅ تم تحديث الهدية اليومية بنجاح.")
            except ValueError:
                reply_q(message, "❌ خاصك تكتب رقم فقط.")

        elif action == "awaiting_channel" and is_admin(user_id):
            db["settings"]["channels"].append(message.text.strip())
            save_db()
            reply_q(message, "✅ تمت إضافة القناة بنجاح.")

        elif action == "awaiting_remove_channel" and is_admin(user_id):
            ch = message.text.strip()
            if ch in db["settings"]["channels"]:
                db["settings"]["channels"].remove(ch)
                save_db()
                reply_q(message, f"✅ تم حذف القناة {ch}.")
            else:
                reply_q(message, f"❌ القناة {ch} غير موجودة.")

        elif action == "awaiting_pinned_announcement" and is_admin(user_id):
            db["settings"]["pinned_announcement"] = message.text
            save_db()
            reply_q(message, "📌 تم تحديث الإعلان المثبت بنجاح.")

        elif action == "awaiting_welcome_photo" and is_admin(user_id):
            reply_q(message, "🖼 يرجى إرسال صورة وليس نصاً. استخدم /cancel للإلغاء.")

        elif action == "awaiting_welcome_message" and is_admin(user_id):
            db["settings"]["welcome_message"] = message.text
            save_db()
            reply_q(message, "📝 تم تحديث الرسالة الترحيبية بنجاح.")

        elif action == "awaiting_support_account" and is_admin(user_id):
            db["settings"]["support_account"] = message.text.strip()
            save_db()
            reply_q(message, f"📞 تم تحديث حساب الدعم إلى {message.text}.")

        elif action == "awaiting_trust_channel" and is_admin(user_id):
            if message.text.lower() == "إلغاء":
                db["settings"]["trust_channel"] = None
                save_db()
                reply_q(message, "📡 تم إلغاء قناة الثقة.")
            else:
                success, msg = verify_and_set_trust_channel(message.text.strip())
                if success:
                    db["settings"]["trust_channel"] = message.text.strip()
                    save_db()
                    reply_q(message, msg)
                else:
                    reply_q(message, msg)

        elif action == "awaiting_ban_user" and is_admin(user_id):
            try:
                target = int(message.text.strip())
                uid = str(target)
                if uid in db["users"]:
                    db["users"][uid]["banned"] = True
                    save_db()
                    reply_q(message, f"🚫 تم حظر المستخدم {target}.")
                else:
                    reply_q(message, "❌ المستخدم غير موجود.")
            except ValueError:
                reply_q(message, "❌ يجب إدخال رقم آيدي صحيح.")

        elif action == "awaiting_unban_user" and is_admin(user_id):
            try:
                target = int(message.text.strip())
                uid = str(target)
                if uid in db["users"]:
                    db["users"][uid]["banned"] = False
                    save_db()
                    reply_q(message, f"✅ تم فك حظر المستخدم {target}.")
                else:
                    reply_q(message, "❌ المستخدم غير موجود.")
            except ValueError:
                reply_q(message, "❌ يجب إدخال رقم آيدي صحيح.")

        elif action == "awaiting_add_admin" and is_admin(user_id):
            try:
                target = int(message.text.strip())
                if target not in db["admins"]:
                    db["admins"].append(target)
                    save_db()
                    reply_q(message, f"✅ تم إضافة المستخدم {target} كأدمن.")
                else:
                    reply_q(message, f"ℹ️ المستخدم {target} بالفعل أدمن.")
            except ValueError:
                reply_q(message, "❌ يجب إدخال رقم آيدي صحيح.")

        elif action == "awaiting_find_order" and is_admin(user_id):
            order_id = message.text.strip()
            order = db["orders"].get(order_id)
            if not order:
                reply_q(message, f"❌ لا يوجد طلب بالرقم {order_id}.")
                return
            item = db["store"].get(order["item_id"], {})
            text = (
                f"📋 <b>تفاصيل الطلب #{order_id}</b>\n"
                f"👤 المستخدم: {get_user_name(order['user'])}\n"
                f"📦 المنتج: {esc(item.get('name', ''))}\n"
                f"💰 السعر: {esc(item.get('price', ''))}\n"
                f"💎 النقاط: {item.get('points', 0)}\n"
                f"📅 التاريخ: {order.get('created', '')}\n"
                f"📌 الحالة: {order.get('status', '')}"
            )
            send_q(chat_id, text)

        elif action == "awaiting_send_user_id" and is_admin(user_id):
            lines = message.text.split("\n", 1)
            if len(lines) < 2:
                reply_q(message, "❌ يجب إدخال الآيدي والرسالة في سطرين.\nمثال:\n123456\nنص الرسالة")
                return
            identifier = lines[0].strip()
            msg_text = lines[1].strip()
            target_user_id = None
            if identifier.startswith('@'):
                username = identifier[1:]
                for uid, u in db["users"].items():
                    if u.get("username", "").lower() == username.lower():
                        target_user_id = int(uid)
                        break
            else:
                try:
                    target_user_id = int(identifier)
                except ValueError:
                    pass
            if target_user_id is None:
                reply_q(message, "❌ لم أجد مستخدمًا بهذا المعرف.")
                return
            try:
                bot.send_message(
                    target_user_id,
                    f"📨 <b>رسالة من الإدارة</b>\n\n{esc(msg_text)}",
                    parse_mode="HTML"
                )
                reply_q(message, f"✅ تم إرسال الرسالة إلى المستخدم {target_user_id}.")
            except Exception as e:
                logger.error(f"فشل إرسال الرسالة: {e}")
                reply_q(message, f"❌ فشل إرسال الرسالة: {e}")

        elif action == "awaiting_edit_price" and is_admin(user_id):
            item_id = pending_action[user_id].get("item_id")
            if not item_id or item_id not in db["store"]:
                reply_q(message, "❌ المنتج غير موجود.")
                pending_action.pop(user_id, None)
                return
            new_price = message.text.strip()
            db["store"][item_id]["price"] = new_price
            save_db()
            reply_q(message, f"✅ تم تحديث سعر المنتج {db['store'][item_id]['name']} إلى {new_price}.")

        elif action == "awaiting_vip_plan" and is_admin(user_id):
            try:
                name, price, points = message.text.split("|")
                plan = {
                    "name": name.strip(),
                    "price": price.strip(),
                    "points": int(points.strip())
                }
                db["settings"].setdefault("vip_plans", []).append(plan)
                save_db()
                reply_q(message, "✅ تمت إضافة خطة VIP بنجاح.")
            except ValueError:
                reply_q(message, "❌ الصيغة غير صحيحة. استعمل: <code>الاسم|السعر|النقاط</code>")
            except Exception as e:
                logger.error(f"خطأ في إضافة خطة VIP: {e}")
                reply_q(message, "❌ حدث خطأ.")

        elif action == "awaiting_max_backups" and is_admin(user_id):
            try:
                new_val = int(message.text.strip())
                if new_val < 1:
                    reply_q(message, "❌ يجب أن يكون الرقم أكبر من 0.")
                    return
                db["settings"]["max_backups"] = new_val
                save_db()
                reply_q(message, f"✅ تم تحديث الحد الأقصى للنسخ الاحتياطية إلى {new_val}.")
            except ValueError:
                reply_q(message, "❌ يجب إدخال رقم صحيح.")

        elif action == "awaiting_token_change":
            fid = pending_action[user_id].get("fid")
            if not fid or fid not in db["files"]:
                reply_q(message, "❌ الملف غير موجود.")
                pending_action.pop(user_id, None)
                return
            f = db["files"][fid]
            if str(user_id) != f["owner"] and not is_admin(user_id):
                reply_q(message, "🔒 ماعندكش الصلاحية.")
                pending_action.pop(user_id, None)
                return
            new_token = message.text.strip()
            try:
                with open(f["path"], "r", encoding="utf-8") as file:
                    content = file.read()
                pattern = r'(BOT_TOKEN\s*=\s*["\'])([^"\']*)(["\'])'
                if re.search(pattern, content):
                    new_content = re.sub(pattern, rf'\g<1>{new_token}\g<3>', content)
                else:
                    new_content = f'BOT_TOKEN = "{new_token}"\n' + content
                with open(f["path"], "w", encoding="utf-8") as file:
                    file.write(new_content)
                reply_q(message, "✅ تم تغيير التوكن بنجاح.")
            except Exception as e:
                logger.error(f"خطأ في تغيير التوكن: {e}")
                reply_q(message, f"❌ حدث خطأ: {e}")
            pending_action.pop(user_id, None)

        elif action == "awaiting_admin_change":
            fid = pending_action[user_id].get("fid")
            if not fid or fid not in db["files"]:
                reply_q(message, "❌ الملف غير موجود.")
                pending_action.pop(user_id, None)
                return
            f = db["files"][fid]
            if str(user_id) != f["owner"] and not is_admin(user_id):
                reply_q(message, "🔒 ماعندكش الصلاحية.")
                pending_action.pop(user_id, None)
                return
            new_admin = message.text.strip()
            try:
                with open(f["path"], "r", encoding="utf-8") as file:
                    content = file.read()
                pattern = r'(ADMIN_ID\s*=\s*)(\d+)'
                if re.search(pattern, content):
                    new_content = re.sub(pattern, rf'\g<1>{new_admin}', content)
                else:
                    new_content = f'ADMIN_ID = {new_admin}\n' + content
                with open(f["path"], "w", encoding="utf-8") as file:
                    file.write(new_content)
                reply_q(message, "✅ تم تغيير معرف الأدمن بنجاح.")
            except Exception as e:
                logger.error(f"خطأ في تغيير معرف الأدمن: {e}")
                reply_q(message, f"❌ حدث خطأ: {e}")
            pending_action.pop(user_id, None)

        elif action == "awaiting_send_points_user" and is_admin(user_id):
            try:
                target = int(message.text.strip())
                uid = str(target)
                if uid not in db["users"]:
                    reply_q(message, "❌ المستخدم غير موجود.")
                    pending_action.pop(user_id, None)
                    return
                pending_action[user_id]["target_user"] = target
                pending_action[user_id]["action"] = "awaiting_send_points_amount"
                reply_q(message, f"✅ المستخدم {target} موجود. أرسل الآن عدد النقاط التي تريد إضافتها:")
            except ValueError:
                reply_q(message, "❌ يجب إدخال رقم آيدي صحيح.")
                pending_action.pop(user_id, None)

        elif action == "awaiting_send_points_amount" and is_admin(user_id):
            target = pending_action[user_id].get("target_user")
            if not target:
                reply_q(message, "❌ حدث خطأ، حاول مرة أخرى.")
                pending_action.pop(user_id, None)
                return
            try:
                amount = int(message.text.strip())
                if amount <= 0:
                    reply_q(message, "❌ يجب أن يكون عدد النقاط أكبر من صفر.")
                    return
                add_points(target, amount)
                try:
                    bot.send_message(
                        target,
                        f"🎉 تمت إضافة <b>{amount}</b> نقطة إلى رصيدك من قبل الإدارة.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"فشل إرسال إشعار النقاط للمستخدم {target}: {e}")
                reply_q(message, f"✅ تمت إضافة {amount} نقطة إلى المستخدم {target} بنجاح.")
                pending_action.pop(user_id, None)
            except ValueError:
                reply_q(message, "❌ يجب إدخال رقم صحيح لعدد النقاط.")

        pending_action.pop(user_id, None)
    except Exception as e:
        logger.error(f"خطأ في معالجة النص المعلق للمستخدم {user_id}: {e}")
        reply_q(message, "حدث خطأ أثناء معالجة طلبك، حاول مرة أخرى.")
        pending_action.pop(user_id, None)

@bot.message_handler(content_types=["photo", "document"])
def handle_photo_for_welcome(message):
    user_id = message.from_user.id
    action = pending_action.get(user_id, {}).get("action")
    if action == "awaiting_welcome_photo" and is_admin(user_id):
        try:
            if message.photo:
                file_id = message.photo[-1].file_id
            elif message.document and message.document.mime_type.startswith("image/"):
                file_id = message.document.file_id
            else:
                reply_q(message, "🖼 يرجى إرسال صورة صالحة (jpg/png).")
                return
            db["settings"]["welcome_photo"] = file_id
            save_db()
            reply_q(message, "🖼 تم تحديث الصورة الترحيبية بنجاح.")
            pending_action.pop(user_id, None)
        except Exception as e:
            logger.error(f"خطأ في استقبال الصورة الترحيبية: {e}")
            reply_q(message, "❌ حدث خطأ أثناء حفظ الصورة.")

# ===================== الميزات الجديدة =====================

@bot.message_handler(commands=['sendmsg'])
def cmd_sendmsg(message):
    if not is_admin(message.from_user.id):
        reply_q(message, "❌ هذا الأمر خاص بالأدمن فقط.")
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            reply_q(message, "⚠️ استخدم: <code>/sendmsg @username الرسالة</code> أو <code>/sendmsg user_id الرسالة</code>")
            return
        identifier = parts[1]
        msg_text = parts[2]
        target_user_id = None
        if identifier.startswith('@'):
            username = identifier[1:].strip()
            for uid, u in db["users"].items():
                if u.get("username", "").lower() == username.lower():
                    target_user_id = int(uid)
                    break
        else:
            try:
                target_user_id = int(identifier)
            except ValueError:
                pass
        if target_user_id is None:
            reply_q(message, "❌ لم أجد مستخدمًا بهذا المعرف.")
            return
        try:
            bot.send_message(
                target_user_id,
                f"📨 <b>رسالة من الإدارة</b>\n\n{esc(msg_text)}",
                parse_mode="HTML"
            )
            reply_q(message, f"✅ تم إرسال الرسالة إلى المستخدم {target_user_id}.")
        except Exception as e:
            logger.error(f"فشل إرسال الرسالة للمستخدم {target_user_id}: {e}")
            reply_q(message, f"❌ فشل إرسال الرسالة: {e}")
    except Exception as e:
        logger.error(f"خطأ في أمر sendmsg: {e}")
        reply_q(message, "❌ حدث خطأ أثناء معالجة الأمر.")

@bot.message_handler(func=lambda m: m.reply_to_message is not None and m.reply_to_message.message_id in question_messages, content_types=["text"])
def handle_reply_to_question(message):
    if not is_admin(message.from_user.id):
        reply_q(message, "❌ هذا الرد مسموح فقط للأدمن.")
        return
    user_id = question_messages.pop(message.reply_to_message.message_id, None)
    if not user_id:
        reply_q(message, "⚠️ لم أجد المستخدم المرتبط بهذه الرسالة.")
        return
    try:
        bot.send_message(
            user_id,
            f"📩 <b>رد الإدارة على استفسارك</b>\n\n{esc(message.text)}",
            parse_mode="HTML"
        )
        reply_q(message, f"✅ تم إرسال الرد إلى المستخدم {user_id}.")
    except Exception as e:
        logger.error(f"فشل إرسال رد الإدارة للمستخدم {user_id}: {e}")
        reply_q(message, f"❌ فشل إرسال الرد: {e}")

@bot.message_handler(commands=['stats', 'status'])
def cmd_stats(message):
    if not is_admin(message.from_user.id):
        reply_q(message, "❌ هذا الأمر خاص بالأدمن فقط.")
        return
    total_users = len(db["users"])
    total_files = len(db["files"])
    pending_files = len([f for f in db["files"].values() if f["status"] == "pending"])
    running_files = len([f for f in db["files"].values() if f["status"] == "running"])
    approved_files = len([f for f in db["files"].values() if f["status"] in ("approved", "running")])
    total_points = sum(u.get("points", 0) for u in db["users"].values())
    total_orders = len(db["orders"])
    pending_orders = len([o for o in db["orders"].values() if o["status"] == "pending"])
    active_processes = len(running_processes)
    stats_text = (
        f"📊 <b>إحصائيات النظام</b>\n\n"
        f"👥 المستخدمين: {total_users}\n"
        f"📄 الملفات الكلية: {total_files}\n"
        f"   - قيد الانتظار: {pending_files}\n"
        f"   - قيد التشغيل: {running_files}\n"
        f"   - تمت الموافقة: {approved_files}\n"
        f"💎 إجمالي النقاط: {total_points}\n"
        f"🛒 الطلبات الكلية: {total_orders}\n"
        f"   - قيد الانتظار: {pending_orders}\n"
        f"🔄 العمليات النشطة: {active_processes}"
    )
    send_q(message.chat.id, stats_text)

# ===================== التشغيل =====================
if __name__ == "__main__":
    cleanup_missing_files_from_db()
    clean_temp_decrypted_files()
    clean_orphaned_files()
    for fid, f in db["files"].items():
        if f.get("status") == "running":
            if os.path.exists(f.get("path", "")):
                threading.Thread(target=start_hosted_bot, args=(fid,), daemon=True).start()
            else:
                logger.warning(f"الملف {f.get('path')} غير موجود، تم تعيين الحالة إلى stopped")
                f["status"] = "stopped"
                save_db()
    threading.Thread(target=billing_loop, daemon=True).start()
    threading.Thread(target=auto_backup, daemon=True).start()
    threading.Thread(target=monitor_storage_loop, daemon=True).start()
    threading.Thread(target=cleanup_loop, daemon=True).start()
    logger.info("🤖 البوت شغال...")
    bot.infinity_polling(skip_pending=True)
