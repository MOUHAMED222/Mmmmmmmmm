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

# ===================== إعدادات التسجيل =====================
LOG_FILE = os.path.join("logs", "bot.log")
os.makedirs("logs", exist_ok=True)

handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ===================== الإعدادات العامة =====================
USER_DATA_DIR = os.path.abspath("user_data")
BOT_TOKEN = "8663385334:AAEovM7W9ReA00araBDDOloakHhkkecu1fg"
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
📜 القوانين
1. يمنع رفع ملفات تحتوي على محتوى غير قانوني.
2. يمنع استخدام البوت لأغراض ضارة أو تخريبية.
3. يحق للإدارة حظر أي مستخدم يخالف القوانين.
4. يجب الالتزام بسياسة الاستخدام العادل.
5. أي انتهاك للقوانين يعرض حسابك للحظر الفوري.
شكرًا لالتزامك بالقوانين.
"""

HELP_TEXT = """
❓ المساعدة
🔹 رفع ملف: اضغط على "رفع ملف" وأرسل ملف .py / .js / .php / .zip.
🔹 النقاط: شراء من المتجر، دعوة الأصدقاء، أو الهدية اليومية.
🔹 مشكلة؟ تواصل مع الدعم.
🔹 توقف البوت؟ قد يكون بسبب نفاد الرصيد.
"""

# ===================== نظام الحماية =====================
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography غير مثبتة، الحماية معطلة.")

SECURITY_KEY_FILE = "security.key"
INTEGRITY_FILE = "integrity.json"
DECRYPTED_TEMP_DIR = "temp_decrypted"
SECURITY_ACTIVATED = False

def get_or_create_security_key():
    if os.path.exists(SECURITY_KEY_FILE):
        with open(SECURITY_KEY_FILE, "rb") as f:
            return f.read()
    if CRYPTO_AVAILABLE:
        key = Fernet.generate_key()
        with open(SECURITY_KEY_FILE, "wb") as f:
            f.write(key)
        os.chmod(SECURITY_KEY_FILE, 0o600)
        logger.info("تم توليد مفتاح أمان جديد.")
        return key
    return None

def get_cipher():
    if not CRYPTO_AVAILABLE:
        return None
    key = get_or_create_security_key()
    return Fernet(key) if key else None

def encrypt_data(data: bytes) -> bytes:
    cipher = get_cipher()
    return cipher.encrypt(data) if cipher else data

def decrypt_data(data: bytes) -> bytes:
    cipher = get_cipher()
    if cipher:
        try:
            return cipher.decrypt(data)
        except Exception:
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
    except:
        pass
    return False

def encrypt_file(filepath: str) -> bool:
    if not CRYPTO_AVAILABLE:
        return False
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        encrypted = encrypt_data(data)
        with open(filepath + ".enc", "wb") as f:
            f.write(encrypted)
        os.remove(filepath)
        logger.info(f"تم تشفير {filepath}")
        return True
    except Exception as e:
        logger.error(f"فشل تشفير {filepath}: {e}")
        return False

def decrypt_file_to_temp(filepath: str) -> str:
    if not CRYPTO_AVAILABLE or not os.path.exists(filepath) or not filepath.endswith(".enc"):
        return filepath
    try:
        with open(filepath, "rb") as f:
            encrypted = f.read()
        decrypted = decrypt_data(encrypted)
        os.makedirs(DECRYPTED_TEMP_DIR, exist_ok=True)
        temp_path = os.path.join(DECRYPTED_TEMP_DIR, os.path.basename(filepath).replace(".enc", ""))
        with open(temp_path, "wb") as f:
            f.write(decrypted)
        logger.info(f"فك تشفير إلى {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"فشل فك التشفير: {e}")
        return filepath

def calculate_file_hash(filepath: str) -> str:
    if not os.path.exists(filepath):
        return ""
    hash_sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def update_integrity():
    if not CRYPTO_AVAILABLE:
        return
    integrity = {}
    for f in [__file__, DB_FILE, SECURITY_KEY_FILE, "requirements.txt", ".env"]:
        if f and os.path.exists(f):
            integrity[f] = calculate_file_hash(f)
    if os.path.exists(UPLOADS_DIR):
        for root, _, files in os.walk(UPLOADS_DIR):
            for file in files:
                if file.endswith(".enc"):
                    integrity[os.path.join(root, file)] = calculate_file_hash(os.path.join(root, file))
    with open(INTEGRITY_FILE, "w") as f:
        json.dump(integrity, f, indent=2)
    logger.info("تم تحديث ملف السلامة.")

def check_integrity():
    if not CRYPTO_AVAILABLE or not os.path.exists(INTEGRITY_FILE):
        return
    with open(INTEGRITY_FILE, "r") as f:
        stored = json.load(f)
    issues = []
    for path, h in stored.items():
        if not os.path.exists(path):
            issues.append(f"⚠️ مفقود: {path}")
        elif calculate_file_hash(path) != h:
            issues.append(f"⚠️ تغير: {path}")
    if issues:
        bot.send_message(ADMIN_ID, f"🚨 تحذير أمني!\n" + "\n".join(issues), parse_mode="HTML")

def start_security_system():
    global SECURITY_ACTIVATED
    if SECURITY_ACTIVATED or not CRYPTO_AVAILABLE:
        return
    if os.path.exists(DB_FILE) and not is_encrypted_file(DB_FILE):
        with open(DB_FILE, "r") as f:
            data = f.read()
        encrypted = encrypt_data(data.encode())
        with open(DB_FILE, "wb") as f:
            f.write(encrypted)
    update_integrity()
    check_integrity()
    SECURITY_ACTIVATED = True
    logger.info("✅ تم تفعيل الحماية.")

def clean_temp_decrypted_files():
    if os.path.exists(DECRYPTED_TEMP_DIR):
        shutil.rmtree(DECRYPTED_TEMP_DIR, ignore_errors=True)

# ===================== قاعدة البيانات =====================
db_lock = threading.Lock()
STATUS_AR = {
    "pending": "⏳ قيد الانتظار",
    "approved": "✅ موافق عليه",
    "rejected": "❌ مرفوض",
    "running": "▶️ شغال",
    "stopped": "⏹️ متوقف"
}

FILE_ICONS = {"py": "🐍", "js": "🟨", "php": "🐘", "zip": "📦", "default": "📄"}

def load_db() -> Dict[str, Any]:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "rb") as f:
                raw = f.read()
            decrypted = decrypt_data(raw)
            return json.loads(decrypted.decode('utf-8'))
        except:
            with open(DB_FILE, "r") as f:
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
    settings = db.setdefault("settings", {})
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
        logger.info("تم ترقية قاعدة البيانات.")

migrate_db()
db["settings"]["free_points"] = 100
db["settings"]["referral_bonus"] = 15
db["settings"]["daily_cost"] = 10
db["settings"]["daily_gift"] = 10
save_db()

pending_action = {}
running_processes = {}
cooldown = {}
question_messages = {}
bot_enabled = True

# ===================== أدوات مساعدة =====================
def now_iso(): return datetime.now().isoformat()
def short_id(): return uuid.uuid4().hex[:8]
def is_admin(user_id): return int(user_id) in db.get("admins", [ADMIN_ID]) or int(user_id) == ADMIN_ID
def get_points(user_id): return db["users"].get(str(user_id), {}).get("points", 0)
def add_points(user_id, amount):
    uid = str(user_id)
    if uid in db["users"]:
        db["users"][uid]["points"] += amount
        save_db()
def get_user_name(user_id):
    uid = str(user_id)
    return db["users"].get(uid, {}).get("username") or f"مستخدم {uid}"
def esc(value): return html.escape("" if value is None else str(value))
def q(text): return f"<blockquote>{text}</blockquote>"
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
    except:
        return bot.edit_message_caption(caption=q(text), chat_id=chat_id, message_id=message_id, **kwargs)

def get_user_photo_file_id(user_id):
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count:
            return photos.photos[0][-1].file_id
    except:
        pass
    return None

def send_user_card(chat_id, user_id, caption, reply_markup=None):
    photo_id = get_user_photo_file_id(user_id)
    if photo_id:
        try:
            return bot.send_photo(chat_id, photo_id, caption=q(caption), reply_markup=reply_markup, parse_mode="HTML")
        except:
            pass
    return bot.send_message(chat_id, q(caption), reply_markup=reply_markup, parse_mode="HTML")

def send_admin_user_card(chat_id, user_id, caption, reply_markup=None):
    return send_user_card(chat_id, user_id, caption, reply_markup)

def update_last_activity(user_id):
    uid = str(user_id)
    if uid in db["users"]:
        db["users"][uid]["last_activity"] = now_iso()
        save_db()

def is_user_banned(user_id):
    return db["users"].get(str(user_id), {}).get("banned", False)

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
                bot.send_message(int(ref_by), q(f"🎉 انضم مستخدم جديد عبر رابطك! +{bonus} نقطة."), parse_mode="HTML")
            except:
                pass
        try:
            reg_caption = f"🆕 مستخدم جديد: {uid}\n👤 {esc(username or 'بدون اسم')}\n🔗 {esc(ref_by or 'لا يوجد')}\n💎 {db['settings']['free_points']} نقطة"
            send_admin_user_card(ADMIN_ID, user_id, reg_caption)
        except:
            pass
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
        except:
            not_joined.append(ch)
    return len(not_joined) == 0, not_joined

def clean_orphaned_files():
    if not os.path.exists(UPLOADS_DIR):
        return
    for filename in os.listdir(UPLOADS_DIR):
        filepath = os.path.join(UPLOADS_DIR, filename)
        if not any(f.get("path") == filepath for f in db["files"].values()):
            try:
                os.remove(filepath)
                logger.info(f"حذف ملف يتيم: {filepath}")
            except Exception as e:
                logger.error(f"فشل حذف {filepath}: {e}")

def cleanup_missing_files_from_db():
    to_remove = []
    for fid, f in db["files"].items():
        if not os.path.exists(f.get("path", "")):
            to_remove.append(fid)
    for fid in to_remove:
        db["files"].pop(fid, None)
    if to_remove:
        save_db()
        logger.info(f"تم إزالة {len(to_remove)} ملفات غير موجودة.")

# ===================== دوال قناة الثقة =====================
def _parse_chat_identifier(raw):
    s = raw.strip()
    if s.startswith('@'):
        try:
            return bot.get_chat(s).id
        except:
            return s
    try:
        return int(s)
    except:
        return s

def verify_and_set_trust_channel(channel_input):
    if not channel_input:
        return False, "❌ لم يتم إدخال معرف القناة."
    chat_id = _parse_chat_identifier(channel_input)
    try:
        bot.get_chat(chat_id)
        bot_member = bot.get_chat_member(chat_id, bot.get_me().id)
        if bot_member.status in ("left", "kicked"):
            return False, "❌ البوت ليس عضواً في القناة."
        bot.send_message(chat_id, "📡 تم تفعيل قناة الثقة.", parse_mode="HTML")
        return True, f"✅ تم تفعيل قناة الثقة ({chat_id})."
    except Exception as e:
        return False, f"❌ فشل: {str(e)}"

def send_to_trust_channel(text):
    channel = db["settings"].get("trust_channel")
    if not channel:
        return
    chat_id = _parse_chat_identifier(channel)
    try:
        bot.send_message(chat_id, q(text), parse_mode="HTML")
    except Exception as e:
        logger.error(f"فشل النشر في قناة الثقة: {e}")

def send_to_vip_channel(text):
    if VIP_CHANNEL_ID:
        try:
            bot.send_message(VIP_CHANNEL_ID, q(text), parse_mode="HTML")
        except Exception as e:
            logger.error(f"فشل الإرسال إلى VIP: {e}")

def export_orders_to_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["رقم الطلب", "المستخدم", "اسم المنتج", "السعر", "النقاط", "الحالة", "التاريخ"])
    for oid, order in db["orders"].items():
        item = db["store"].get(order["item_id"], {})
        user_info = db["users"].get(order["user"], {})
        writer.writerow([oid, f"{user_info.get('username', '')} ({order['user']})", item.get("name", ""), item.get("price", ""), item.get("points", 0), order.get("status", ""), order.get("created", "")])
    return output.getvalue().encode('utf-8')

# ===================== النسخ الاحتياطي التلقائي =====================
BACKUP_INTERVAL = 300

def auto_backup():
    while True:
        try:
            time.sleep(BACKUP_INTERVAL)
            create_full_backup_and_send_to_channel(BACKUP_CHANNEL)
            max_backups = db["settings"].get("max_backups", 200)
            backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("full_backup_") and f.endswith(".zip")], key=lambda f: os.path.getmtime(os.path.join(BACKUP_DIR, f)))
            while len(backups) > max_backups:
                os.remove(os.path.join(BACKUP_DIR, backups.pop(0)))
        except Exception as e:
            logger.error(f"خطأ في النسخ الاحتياطي: {e}")

def backup_uploaded_files():
    if not os.path.exists(UPLOADS_DIR) or not os.listdir(UPLOADS_DIR):
        return None
    backup_path = os.path.join(BACKUP_DIR, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(UPLOADS_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, start=os.path.dirname(UPLOADS_DIR)))
    return backup_path

def create_full_backup_and_send_to_channel(channel_input):
    chat_id = _parse_chat_identifier(channel_input)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"full_backup_{timestamp}.zip")
    try:
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f in [DB_FILE, UPLOADS_DIR, LOGS_DIR, __file__, "requirements.txt"]:
                if os.path.exists(f):
                    zipf.write(f, os.path.basename(f))
        with open(backup_path, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"📦 نسخة احتياطية كاملة\n🕒 {timestamp}")
        logger.info(f"✅ تم إرسال النسخة الاحتياطية إلى {channel_input}")
    except Exception as e:
        logger.error(f"فشل إنشاء النسخة الاحتياطية: {e}")
    finally:
        try:
            os.remove(backup_path)
        except:
            pass

# ===================== لوحات المفاتيح =====================
def main_menu_kb(user_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📤 رفع ملف", callback_data="upload_file"),
        types.InlineKeyboardButton("📁 ملفاتي", callback_data="my_files"),
    )
    kb.add(
        types.InlineKeyboardButton("🛒 المتجر", callback_data="store"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="my_account"),
    )
    kb.add(
        types.InlineKeyboardButton("💎 نقاطي", callback_data="my_points"),
        types.InlineKeyboardButton("🎁 الهدية اليومية", callback_data="daily_gift"),
    )
    kb.add(
        types.InlineKeyboardButton("👥 دعوة الأصدقاء", callback_data="invite"),
        types.InlineKeyboardButton("💎 باقات VIP", callback_data="vip_plans"),
    )
    kb.add(
        types.InlineKeyboardButton("📢 قناة الثقة", callback_data="trust_channel"),
        types.InlineKeyboardButton("❓ استفسار", callback_data="ask_admin"),
    )
    kb.add(
        types.InlineKeyboardButton("📜 القوانين", callback_data="rules"),
        types.InlineKeyboardButton("ℹ️ المساعدة", callback_data="help"),
    )
    if is_admin(user_id):
        kb.add(types.InlineKeyboardButton("🛡️ لوحة الإدارة", callback_data="admin_panel"))
    return kb

def admin_menu_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📤 طلبات رفع", callback_data="admin_upload_requests"),
        types.InlineKeyboardButton("🛒 طلبات منتجات", callback_data="admin_order_requests"),
    )
    kb.add(
        types.InlineKeyboardButton("👥 المستخدمين", callback_data="admin_users"),
        types.InlineKeyboardButton("🎁 الخطة المجانية", callback_data="admin_free_plan"),
    )
    kb.add(
        types.InlineKeyboardButton("📣 إذاعة", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📄 كل الملفات", callback_data="admin_all_files"),
    )
    kb.add(
        types.InlineKeyboardButton("🛍️ إدارة المتجر", callback_data="admin_manage_store"),
        types.InlineKeyboardButton("📦 الطلبات", callback_data="admin_order_requests"),
    )
    kb.add(
        types.InlineKeyboardButton("⚙️ إعدادات النقاط", callback_data="admin_points_settings"),
        types.InlineKeyboardButton("🎁 الهدية اليومية", callback_data="admin_daily_gift_settings"),
    )
    kb.add(
        types.InlineKeyboardButton("📡 القنوات", callback_data="admin_channels"),
        types.InlineKeyboardButton("📊 إحصائيات النظام", callback_data="admin_system_stats"),
    )
    kb.add(
        types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="admin_settings"),
        types.InlineKeyboardButton("📌 إعلان مثبت", callback_data="admin_pinned_announcement"),
    )
    kb.add(
        types.InlineKeyboardButton("🖼 صورة ترحيبية", callback_data="admin_welcome_photo"),
        types.InlineKeyboardButton("📝 رسالة ترحيبية", callback_data="admin_welcome_message"),
    )
    kb.add(
        types.InlineKeyboardButton("📞 حساب الدعم", callback_data="admin_support_account"),
        types.InlineKeyboardButton("📢 قناة الثقة", callback_data="admin_trust_channel"),
    )
    kb.add(
        types.InlineKeyboardButton("🚫 الحظر والإدارة", callback_data="admin_ban_management"),
        types.InlineKeyboardButton("👥 إدارة الأدمن", callback_data="admin_manage_admins"),
    )
    kb.add(
        types.InlineKeyboardButton("💎 إرسال نقاط", callback_data="admin_send_points"),
        types.InlineKeyboardButton("📊 إحصائيات تفصيلية", callback_data="admin_detailed_stats"),
    )
    kb.add(
        types.InlineKeyboardButton("📤 تصدير الطلبات", callback_data="admin_export_orders"),
        types.InlineKeyboardButton("💾 نسخ احتياطي", callback_data="admin_backup"),
    )
    kb.add(
        types.InlineKeyboardButton("🔘 تشغيل/إيقاف البوت", callback_data="admin_toggle_bot"),
        types.InlineKeyboardButton("✅ طلبات مقبولة", callback_data="admin_accepted_orders"),
    )
    kb.add(
        types.InlineKeyboardButton("⏳ طلبات معلقة", callback_data="admin_pending_orders"),
        types.InlineKeyboardButton("🔍 بحث برقم الطلب", callback_data="admin_find_order"),
    )
    kb.add(
        types.InlineKeyboardButton("🆕 أحدث المستخدمين", callback_data="admin_latest_users"),
        types.InlineKeyboardButton("👥 جميع المستخدمين", callback_data="admin_all_users_list"),
    )
    kb.add(
        types.InlineKeyboardButton("📨 إرسال رسالة", callback_data="admin_send_message"),
        types.InlineKeyboardButton("🌟 النشطين", callback_data="admin_active_users"),
    )
    kb.add(
        types.InlineKeyboardButton("🔄 إدارة الاشتراكات", callback_data="admin_manage_subscriptions"),
        types.InlineKeyboardButton("⚙️ إعدادات النسخ الاحتياطي", callback_data="admin_backup_settings"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main"),
    )
    return kb

# ===================== دوال تثبيت المكتبات (محسنة) =====================
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
    "dateutil": "python-dateutil", "yaml": "pyyaml", "PIL": "pillow",
    "telegram": "python-telegram-bot", "telebot": "pyTelegramBotAPI",
    "aiogram": "aiogram", "requests": "requests", "aiohttp": "aiohttp",
    "beautifulsoup4": "beautifulsoup4", "bs4": "beautifulsoup4", "lxml": "lxml",
    "selenium": "selenium", "numpy": "numpy", "pandas": "pandas",
    "matplotlib": "matplotlib", "Pillow": "Pillow", "psutil": "psutil",
    "flask": "flask", "fastapi": "fastapi", "uvicorn": "uvicorn",
    "sqlalchemy": "sqlalchemy", "motor": "motor", "pymongo": "pymongo",
    "redis": "redis", "celery": "celery", "cryptography": "cryptography",
    "pycryptodome": "pycryptodome", "python-dotenv": "python-dotenv",
    "pydantic": "pydantic", "rich": "rich", "colorama": "colorama",
    "emoji": "emoji", "faker": "faker", "schedule": "schedule",
    "yt-dlp": "yt-dlp", "moviepy": "moviepy", "openai": "openai",
    "transformers": "transformers", "torch": "torch", "tensorflow": "tensorflow",
    "scikit-learn": "scikit-learn", "discord.py": "discord.py",
    "websockets": "websockets", "gTTS": "gTTS", "SpeechRecognition": "SpeechRecognition",
    "pydub": "pydub", "mutagen": "mutagen", "instaloader": "instaloader",
    "docker": "docker", "paramiko": "paramiko", "bcrypt": "bcrypt",
    "pyjwt": "pyjwt", "xmltodict": "xmltodict", "feedparser": "feedparser",
    "asyncpg": "asyncpg", "pymysql": "pymysql", "psycopg2": "psycopg2",
}

def get_imports(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return set()
    imports = set()
    try:
        tree = ast.parse(content)
    except SyntaxError:
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
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split('.')[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '__import__':
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                imports.add(node.args[0].value.split('.')[0])
    return imports

def install_package_with_retries(container_manager, user_id, package_name, install_name=None, retries=3):
    if install_name is None:
        install_name = package_name
    container_manager.run_command_in_container(user_id, "mkdir -p /app/.local", detach=False)
    for attempt in range(1, retries+1):
        try:
            env = {'PYTHONUSERBASE': '/app/.local', 'PATH': '/app/.local/bin:/usr/local/bin:/usr/bin:/bin'}
            cmd = f"pip install --user {install_name} --no-cache-dir"
            if attempt == retries:
                cmd += " --upgrade"
            output = container_manager.run_command_in_container(user_id, cmd, detach=False, environment=env)
            if output and ("Successfully installed" in output or "Requirement already satisfied" in output):
                return True
            if attempt == 1 and install_name != package_name:
                alt_cmd = f"pip install --user {package_name} --no-cache-dir"
                alt_output = container_manager.run_command_in_container(user_id, alt_cmd, detach=False, environment=env)
                if alt_output and ("Successfully installed" in alt_output or "Requirement already satisfied" in alt_output):
                    return True
        except Exception as e:
            logger.error(f"خطأ في تثبيت {install_name}: {e}")
        time.sleep(2)
    return False

def install_requirements_in_container(container_manager, user_id, file_path) -> bool:
    if not container_manager.is_available():
        return False
    base_dir = os.path.dirname(file_path)
    req_file = os.path.join(base_dir, "requirements.txt")
    if not os.path.exists(req_file):
        return True
    container_path = "/app/files/requirements.txt"
    if not container_manager.copy_file_to_container(user_id, req_file, container_path):
        return False
    container_manager.run_command_in_container(user_id, "mkdir -p /app/.local", detach=False)
    env = {'PYTHONUSERBASE': '/app/.local', 'PATH': '/app/.local/bin:/usr/local/bin:/usr/bin:/bin'}
    cmd = f"pip install --user -r /app/files/requirements.txt --no-cache-dir"
    output = container_manager.run_command_in_container(user_id, cmd, detach=False, environment=env)
    if output and ("Successfully installed" in output or "Requirement already satisfied" in output):
        return True
    # فشل، حاول كل حزمة على حدة
    try:
        with open(req_file, 'r') as f:
            packages = [re.split(r'[=<>!]', line.strip())[0] for line in f if line.strip() and not line.startswith('#')]
        success = True
        for pkg in packages:
            install_name = PACKAGE_ALIASES.get(pkg, pkg)
            if not install_package_with_retries(container_manager, user_id, pkg, install_name):
                success = False
        return success
    except:
        return False

def install_imported_requirements(container_manager, user_id, file_path) -> bool:
    if not container_manager.is_available():
        return False
    imports = get_imports(file_path)
    external = [pkg for pkg in imports if pkg not in BUILTIN_MODULES]
    if not external:
        return True
    container_manager.run_command_in_container(user_id, "mkdir -p /app/.local", detach=False)
    success = True
    for pkg in external:
        install_name = PACKAGE_ALIASES.get(pkg, pkg)
        env = {'PYTHONUSERBASE': '/app/.local', 'PATH': '/app/.local/bin:/usr/local/bin:/usr/bin:/bin'}
        check_cmd = f"python3 -c 'import {pkg}' 2>/dev/null && echo installed || echo not_installed"
        check = container_manager.run_command_in_container(user_id, check_cmd, detach=False, environment=env)
        if check and "installed" in check:
            continue
        if not install_package_with_retries(container_manager, user_id, pkg, install_name):
            success = False
    return success

# ===================== نظام الحاويات =====================
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    logger.warning("docker غير مثبتة، لن يعمل نظام الحاويات.")

CONTAINER_IMAGE = "python:3.11-slim"  # الصورة الأساسية
MAX_STORAGE_MB = 500
os.makedirs(USER_DATA_DIR, exist_ok=True)

class ContainerManager:
    def __init__(self):
        self.docker_client = None
        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
                self.docker_client.ping()
                logger.info("✅ تم الاتصال بـ Docker.")
            except Exception as e:
                logger.error(f"❌ فشل الاتصال بـ Docker: {e}")
                self.docker_client = None
        else:
            logger.warning("⚠️ Docker غير متوفر.")

    def is_available(self):
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
        total = 0
        for root, _, files in os.walk(user_dir):
            for f in files:
                total += os.path.getsize(os.path.join(root, f))
        return total // (1024 * 1024)

    def enforce_storage_limit(self, user_id: str, additional_size_mb: int) -> bool:
        return self.get_user_storage_usage(user_id) + additional_size_mb <= MAX_STORAGE_MB

    def ensure_container(self, user_id: str) -> Optional[str]:
        if not self.is_available():
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
        except docker.errors.NotFound:
            return self._create_container(user_id)
        except Exception as e:
            logger.error(f"خطأ في ensure_container: {e}")
            if "Conflict" in str(e):
                try:
                    old = self.docker_client.containers.get(container_name)
                    old.remove(force=True)
                    return self._create_container(user_id)
                except:
                    pass
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
            except:
                logger.info(f"سحب الصورة {CONTAINER_IMAGE} ...")
                self.docker_client.images.pull(CONTAINER_IMAGE)

            container = self.docker_client.containers.create(
                image=CONTAINER_IMAGE,
                name=container_name,
                command="tail -f /dev/null",
                working_dir="/app",
                volumes={user_dir: {"bind": "/app", "mode": "rw"}},
                read_only=False,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=64M"},
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
            logger.info(f"✅ تم إنشاء حاوية {container_name}")

            # تثبيت Node.js و PHP مباشرة باستخدام apt (بدون curl)
            if not self._install_runtime_dependencies(user_id):
                logger.error(f"فشل تثبيت الاعتماديات للمستخدم {user_id}")
                container.stop()
                container.remove()
                return None

            return container_name
        except Exception as e:
            logger.error(f"فشل إنشاء حاوية: {e}")
            return None

    # ============= التعديل الجوهري: تثبيت Node.js و PHP عبر apt بدون curl =============
    def _install_runtime_dependencies(self, user_id: str) -> bool:
        if not self.is_available():
            return False

        # تحديث apt وتثبيت Node.js و PHP و Composer مباشرة من مستودعات Debian
        install_cmds = [
            "apt-get update -qq",
            "apt-get install -y -qq nodejs npm php php-cli php-mbstring php-xml php-curl php-zip php-bcmath php-json composer",
            "npm install -g npm@latest"  # تحديث npm
        ]

        for cmd in install_cmds:
            output = self.run_command_in_container(user_id, cmd, detach=False)
            if output is None:
                logger.error(f"فشل تنفيذ: {cmd}")
                return False
            time.sleep(2)

        # التحقق من التثبيت
        check_node = self.run_command_in_container(user_id, "node --version", detach=False)
        check_php = self.run_command_in_container(user_id, "php --version", detach=False)
        check_composer = self.run_command_in_container(user_id, "composer --version", detach=False)

        if check_node is None or "not found" in check_node.lower():
            logger.error("فشل تثبيت Node.js")
            return False
        if check_php is None or "not found" in check_php.lower():
            logger.error("فشل تثبيت PHP")
            return False
        if check_composer is None or "not found" in check_composer.lower():
            logger.error("فشل تثبيت Composer")
            return False

        logger.info(f"✅ تم تثبيت Node.js: {check_node[:20]}, PHP: {check_php[:20]}, Composer: {check_composer[:20]}")
        return True

    def run_command_in_container(self, user_id: str, command: str, detach: bool = True,
                                 workdir: str = "/app", environment: Optional[Dict[str, str]] = None) -> Optional[str]:
        if not self.is_available():
            return None
        container_name = self.get_user_container_name(user_id)
        try:
            container = self.docker_client.containers.get(container_name)
            env_list = [f"{k}={v}" for k, v in environment.items()] if environment else None
            if detach:
                exec_id = self.docker_client.api.exec_create(container.id, cmd, workdir=workdir, environment=env_list)['Id']
                self.docker_client.api.exec_start(exec_id, detach=True)
                return exec_id
            else:
                result = container.exec_run(cmd, workdir=workdir, detach=False, stream=False, environment=env_list)
                if result.exit_code != 0:
                    logger.error(f"الأمر '{cmd}' فشل بكود {result.exit_code}: {result.output.decode('utf-8', errors='replace')}")
                    return None
                return result.output.decode('utf-8', errors='replace').strip()
        except Exception as e:
            logger.error(f"خطأ في run_command: {e}")
            return None

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
                tar.add(local_path, arcname=os.path.basename(container_path))
            tar_data.seek(0)
            return container.put_archive(os.path.dirname(container_path), tar_data)
        except Exception as e:
            logger.error(f"فشل نسخ الملف: {e}")
            return False

    def copy_file_from_container(self, user_id: str, container_path: str, local_path: str) -> bool:
        if not self.is_available():
            return False
        container_name = self.get_user_container_name(user_id)
        try:
            container = self.docker_client.containers.get(container_name)
            result = container.exec_run(["cat", container_path], detach=False, stream=False)
            if result.exit_code != 0:
                return False
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(result.output)
            return True
        except Exception as e:
            logger.error(f"فشل نسخ من الحاوية: {e}")
            return False

    def install_imported_requirements(self, user_id: str, file_path: str) -> bool:
        return install_imported_requirements(self, user_id, file_path)

    def install_requirements_in_container(self, user_id: str, file_path: str) -> bool:
        return install_requirements_in_container(self, user_id, file_path)

    def install_node_dependencies(self, user_id: str, file_path: str) -> bool:
        if not self.is_available():
            return False
        base_dir = os.path.dirname(file_path)
        pkg_file = os.path.join(base_dir, "package.json")
        if not os.path.exists(pkg_file):
            return True
        container_path = "/app/files/package.json"
        if not self.copy_file_to_container(user_id, pkg_file, container_path):
            return False
        cmd = "npm install --prefix /app/files --no-audit --no-fund"
        output = self.run_command_in_container(user_id, cmd, detach=False)
        return output is not None and ("added" in output or "up to date" in output)

    def install_php_dependencies(self, user_id: str, file_path: str) -> bool:
        if not self.is_available():
            return False
        base_dir = os.path.dirname(file_path)
        composer_file = os.path.join(base_dir, "composer.json")
        if not os.path.exists(composer_file):
            return True
        container_path = "/app/files/composer.json"
        if not self.copy_file_to_container(user_id, composer_file, container_path):
            return False
        cmd = "composer install --working-dir=/app/files --no-interaction --no-dev --no-progress"
        output = self.run_command_in_container(user_id, cmd, detach=False)
        return output is not None and ("Installing" in output or "Nothing to install" in output)

    def start_process_and_get_pid(self, user_id: str, base_cmd: str, fid: str, workdir: str = "/app") -> Tuple[Optional[int], Optional[str]]:
        if not self.is_available():
            return None, None
        container_name = self.get_user_container_name(user_id)
        try:
            container = self.docker_client.containers.get(container_name)
            env = {
                'PYTHONUSERBASE': '/app/.local',
                'PYTHONPATH': f"/app/.local/lib/python{get_python_version_in_container(self, user_id)}/site-packages",
                'PATH': '/app/.local/bin:/usr/local/bin:/usr/bin:/bin'
            }
            env_list = [f"{k}={v}" for k, v in env.items()]
            log_file = f"/app/logs/{fid}.log"
            pid_file = f"/app/logs/{fid}.pid"
            full_cmd = f"{base_cmd} > {log_file} 2>&1 & echo $! > {pid_file}"
            shell_cmd = f"sh -c {shlex.quote(full_cmd)}"
            exec_id = self.docker_client.api.exec_create(container.id, shell_cmd, workdir=workdir, environment=env_list)['Id']
            self.docker_client.api.exec_start(exec_id, detach=True)
            time.sleep(2)
            pid_result = container.exec_run(["cat", pid_file], workdir=workdir, detach=False, stream=False)
            if pid_result.exit_code != 0:
                return None, None
            pid_str = pid_result.output.decode().strip()
            if not pid_str.isdigit():
                return None, None
            pid = int(pid_str)
            log_result = container.exec_run(["head", "-c", "500", log_file], workdir=workdir, detach=False, stream=False)
            log_content = log_result.output.decode('utf-8', errors='replace') if log_result.exit_code == 0 else ""
            return pid, log_content
        except Exception as e:
            logger.error(f"خطأ في start_process: {e}")
            return None, None

    def is_process_running(self, user_id: str, pid: int) -> bool:
        if not self.is_available() or not pid:
            return False
        container_name = self.get_user_container_name(user_id)
        try:
            container = self.docker_client.containers.get(container_name)
            result = container.exec_run(["sh", "-c", f"kill -0 {pid}"])
            return result.exit_code == 0
        except:
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
            logger.error(f"خطأ في تنظيف الحاويات: {e}")

    def cleanup_unused_images(self):
        if not self.is_available():
            return
        try:
            self.docker_client.images.prune()
        except Exception as e:
            logger.error(f"خطأ في تنظيف الصور: {e}")

def get_python_version_in_container(container_manager, user_id):
    try:
        output = container_manager.run_command_in_container(user_id, "python3 -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")'", detach=False)
        if output and re.match(r'^\d+\.\d+$', output):
            return output
    except:
        pass
    return "3.11"

container_manager = ContainerManager()

# ===================== دوال استضافة الملفات =====================
def get_file_extension(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return ext[1:] if ext.startswith('.') else ext

def get_file_type_icon(filename: str) -> str:
    ext = get_file_extension(filename)
    return FILE_ICONS.get(ext, FILE_ICONS["default"])

def extract_zip_file(user_id: str, zip_path: str, fid: str) -> List[Dict[str, str]]:
    user_dir = container_manager.get_user_dir(str(user_id))
    extract_dir = os.path.join(user_dir, "files", f"extracted_{fid}")
    os.makedirs(extract_dir, exist_ok=True)
    extracted_files = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            all_names = zip_ref.namelist()
        supported_exts = {'.py', '.js', '.php'}
        for name in all_names:
            if name.endswith('/'):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in supported_exts:
                base_name = os.path.basename(name)
                src_path = os.path.join(extract_dir, name)
                dest_path = os.path.join(user_dir, "files", base_name)
                counter = 1
                while os.path.exists(dest_path):
                    name_part, ext_part = os.path.splitext(base_name)
                    dest_path = os.path.join(user_dir, "files", f"{name_part}_{counter}{ext_part}")
                    counter += 1
                shutil.copy2(src_path, dest_path)
                extracted_files.append({
                    "filename": os.path.basename(dest_path),
                    "path": dest_path,
                    "ext": get_file_extension(dest_path),
                    "original_name": name
                })
        shutil.rmtree(extract_dir, ignore_errors=True)
        return extracted_files
    except Exception as e:
        logger.error(f"فشل استخراج ZIP: {e}")
        return []

def register_extracted_files(user_id: str, extracted_files: List[Dict[str, str]], parent_fid: str) -> int:
    registered = 0
    now = now_iso()
    for f_info in extracted_files:
        fid_new = short_id()
        db["files"][fid_new] = {
            "owner": str(user_id),
            "filename": f_info["filename"],
            "path": f_info["path"],
            "status": "approved",
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

def start_hosted_bot(fid):
    f = db["files"].get(fid)
    if not f or fid in running_processes:
        return
    user_id = f["owner"]
    original_path = f["path"]
    if not os.path.exists(original_path):
        logger.error(f"الملف غير موجود: {original_path}")
        f["status"] = "stopped"
        save_db()
        return
    if not container_manager.is_available():
        logger.error("نظام الحاويات غير متاح.")
        f["status"] = "stopped"
        save_db()
        return
    container_name = container_manager.ensure_container(user_id)
    if not container_name:
        logger.error(f"فشل إنشاء حاوية للمستخدم {user_id}")
        f["status"] = "stopped"
        save_db()
        return
    if original_path.endswith(".enc"):
        temp_path = decrypt_file_to_temp(original_path)
    else:
        temp_path = original_path
    file_size_mb = os.path.getsize(temp_path) // (1024 * 1024)
    if not container_manager.enforce_storage_limit(user_id, file_size_mb):
        logger.error(f"تجاوز حد المساحة للمستخدم {user_id}")
        f["status"] = "stopped"
        save_db()
        try:
            bot.send_message(int(user_id), f"❌ تجاوزت حد المساحة ({MAX_STORAGE_MB} ميجابايت).")
        except:
            pass
        return
    file_ext = get_file_extension(f.get("filename", ""))
    f["file_ext"] = file_ext
    if file_ext == "zip":
        logger.info(f"📦 معالجة ZIP للمستخدم {user_id}")
        extracted = extract_zip_file(user_id, temp_path, fid)
        if not extracted:
            f["status"] = "stopped"
            save_db()
            try:
                bot.send_message(int(user_id), "❌ فشل استخراج ZIP.")
            except:
                pass
            return
        registered = register_extracted_files(user_id, extracted, fid)
        try:
            if os.path.exists(original_path):
                os.remove(original_path)
            if os.path.exists(temp_path) and temp_path != original_path:
                os.remove(temp_path)
        except:
            pass
        db["files"].pop(fid, None)
        save_db()
        try:
            bot.send_message(int(user_id), f"✅ تم استخراج {registered} ملفاً من ZIP.")
        except:
            pass
        return
    container_filename = f"{fid}_{f['filename']}"
    container_path = f"/app/files/{container_filename}"
    if not container_manager.copy_file_to_container(user_id, temp_path, container_path):
        logger.error(f"فشل نسخ الملف إلى الحاوية")
        f["status"] = "stopped"
        save_db()
        return
    deps_success = True
    if file_ext == "py":
        req_installed = container_manager.install_requirements_in_container(user_id, temp_path)
        if not req_installed:
            logger.warning("فشل تثبيت requirements.txt، نحاول تثبيت المكتبات المستوردة.")
        imported_installed = container_manager.install_imported_requirements(user_id, temp_path)
        if not req_installed and not imported_installed:
            deps_success = False
    elif file_ext == "js":
        deps_success = container_manager.install_node_dependencies(user_id, temp_path)
    elif file_ext == "php":
        deps_success = container_manager.install_php_dependencies(user_id, temp_path)
    else:
        f["status"] = "stopped"
        save_db()
        return
    if not deps_success:
        f["status"] = "stopped"
        save_db()
        try:
            bot.send_message(int(user_id), "❌ فشل تثبيت المتطلبات.")
        except:
            pass
        return
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
    pid, log_content = container_manager.start_process_and_get_pid(user_id, base_cmd, fid, workdir="/app")
    if pid is None:
        logger.warning(f"فشل الحصول على PID للبوت {fid}")
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
                        bot.send_message(int(user_id), f"❌ بوتك توقف فوراً:\n<pre>{esc(error_log[:500])}</pre>")
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
    logger.info(f"✅ تم تشغيل البوت {fid} (PID: {pid}, النوع: {file_ext})")

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
                logger.info(f"تم إيقاف البوت {fid} (PID: {pid})")
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
                logger.info(f"خصم {cost} نقطة من المستخدم {owner}")
            else:
                stop_hosted_bot(fid)
                try:
                    send_user_card(int(owner), owner, f"⏹️ توقف بوت {f['filename']} بسبب نفاد الرصيد.")
                except:
                    pass
    except:
        f["last_bill"] = now_iso()
        save_db()

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
                        logger.warning(f"توقف البوت {fid} بشكل غير متوقع")
                        continue
                process_billing(fid, f)
        except Exception as e:
            logger.error(f"خطأ في billing_loop: {e}")

def monitor_storage_loop():
    while True:
        try:
            time.sleep(300)
            users_to_check = set()
            for fid, f in db["files"].items():
                if f.get("status") in ("running", "approved"):
                    users_to_check.add(f["owner"])
            for uid in users_to_check:
                usage = container_manager.get_user_storage_usage(uid)
                if usage > MAX_STORAGE_MB:
                    logger.warning(f"المستخدم {uid} تجاوز حد المساحة: {usage} ميجابايت")
                    for fid, f in list(db["files"].items()):
                        if f["owner"] == uid and f.get("status") == "running":
                            stop_hosted_bot(fid)
                            try:
                                bot.send_message(int(uid), f"⛔ تم إيقاف بوتك بسبب تجاوز حد المساحة {MAX_STORAGE_MB} ميجابايت.")
                            except:
                                pass
        except Exception as e:
            logger.error(f"خطأ في monitor_storage_loop: {e}")

def cleanup_loop():
    while True:
        try:
            time.sleep(3600)
            container_manager.cleanup_stopped_containers()
            container_manager.cleanup_unused_images()
            clean_temp_decrypted_files()
            clean_orphaned_files()
        except Exception as e:
            logger.error(f"خطأ في cleanup_loop: {e}")

# ===================== معالجات البوت =====================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    logger.info(f"Received /start from {message.from_user.id}")
    if not bot_enabled and not is_admin(message.from_user.id):
        reply_q(message, "⛔ البوت متوقف حالياً.")
        return
    user_id = message.from_user.id
    if is_user_banned(user_id):
        reply_q(message, "🚫 أنت محظور.")
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
        kb.add(types.InlineKeyboardButton("✅ تحققت", callback_data="check_sub"))
        send_q(message.chat.id, "⚠️ اشترك في القنوات أولاً:", reply_markup=kb)
        return
    welcome_photo = db["settings"].get("welcome_photo")
    welcome_message = db["settings"].get("welcome_message", "👋 مرحباً بك في بوت الاستضافة!")
    if welcome_photo:
        try:
            bot.send_photo(message.chat.id, welcome_photo, caption=q(welcome_message), reply_markup=main_menu_kb(user_id), parse_mode="HTML")
            return
        except:
            pass
    send_user_card(message.chat.id, user_id, welcome_message, reply_markup=main_menu_kb(user_id))

@bot.message_handler(commands=["cancel"])
def cmd_cancel(message):
    if is_user_banned(message.from_user.id):
        return
    pending_action.pop(message.from_user.id, None)
    reply_q(message, "❌ تم إلغاء العملية.")

@bot.message_handler(content_types=["document"])
def handle_document(message):
    if not bot_enabled and not is_admin(message.from_user.id):
        reply_q(message, "⛔ البوت متوقف.")
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
            reply_q(message, "❌ الصيغة غير مدعومة.")
            return
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        old_path = f["path"]
        try:
            os.remove(old_path)
        except:
            pass
        with open(old_path, "wb") as new_f:
            new_f.write(downloaded)
        f["filename"] = doc.file_name
        f["uploaded_at"] = now_iso()
        f["file_ext"] = get_file_extension(doc.file_name)
        save_db()
        reply_q(message, "✅ تم تحديث الملف.")
        pending_action.pop(user_id, None)
        return
    if pending_action.get(user_id, {}).get("action") != "awaiting_file":
        reply_q(message, "📎 اضغط أولاً على «رفع ملف» من القائمة.")
        return
    doc = message.document
    file_ext = get_file_extension(doc.file_name)
    if file_ext not in ("py", "js", "php", "zip"):
        reply_q(message, "❌ الصيغة غير مدعومة.")
        return
    if get_points(user_id) < db["settings"]["daily_cost"]:
        reply_q(message, f"❌ لا تملك نقاطاً كافية (تحتاج {db['settings']['daily_cost']} نقطة).")
        pending_action.pop(user_id, None)
        return
    file_info = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)
    fid = short_id()
    save_path = os.path.join(UPLOADS_DIR, f"{fid}_{doc.file_name}")
    with open(save_path, "wb") as f:
        f.write(downloaded)
    if CRYPTO_AVAILABLE:
        if encrypt_file(save_path):
            save_path += ".enc"
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
    icon = get_file_type_icon(doc.file_name)
    ext_display = {"py": "بايثون 🐍", "js": "جافا سكريبت 🟨", "php": "بي إتش بي 🐘", "zip": "مضغوط 📦"}.get(file_ext, file_ext)
    reply_q(message, f"✅ تم رفع الملف ({icon} {ext_display})، بانتظار الموافقة.")
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_file_{fid}"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_file_{fid}"),
    )
    username = message.from_user.username or ""
    caption = f"📤 طلب رفع جديد\n👤 @{esc(username)} ({user_id})\n📄 {esc(doc.file_name)}\n📦 {ext_display} {icon}"
    photo_id = get_user_photo_file_id(user_id)
    try:
        if photo_id:
            bot.send_photo(ADMIN_ID, photo_id, caption=q(caption), reply_markup=kb, parse_mode="HTML")
        bot.send_document(ADMIN_ID, doc.file_id, caption=q(f"📄 {esc(doc.file_name)}"), reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"فشل إرسال طلب الرفع للأدمن: {e}")
        bot.send_document(ADMIN_ID, doc.file_id, caption=q(f"📄 {esc(doc.file_name)}"), reply_markup=kb, parse_mode="HTML")

def show_my_files(chat_id, user_id):
    user_files = {fid: f for fid, f in db["files"].items() if f["owner"] == str(user_id)}
    if not user_files:
        send_q(chat_id, "📁 لا توجد ملفات.")
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
        send_q(chat_id, "🔒 لا صلاحية.")
        return
    status_text = STATUS_AR.get(f.get('status', ''), f.get('status', 'غير معروف'))
    icon = get_file_type_icon(f.get('filename', ''))
    ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
    ext_display = {"py": "بايثون 🐍", "js": "جافا سكريبت 🟨", "php": "بي إتش بي 🐘", "zip": "مضغوط 📦"}.get(ext, ext)
    info = f"{icon} <b>{esc(f['filename'])}</b>\n📌 {status_text}\n📦 {ext_display}\n📅 {esc(f.get('uploaded_at', 'غير معروف'))}\n🧾 أيام الفوترة: {f.get('daily_billed', 0)}\n🆔 PID: {f.get('pid', 'لا يوجد')}"
    kb = types.InlineKeyboardMarkup(row_width=2)
    if f["status"] == "running":
        kb.add(types.InlineKeyboardButton("⏹️ إيقاف", callback_data=f"stop_file_{fid}"))
    elif f["status"] in ("approved", "stopped") and ext != "zip":
        kb.add(types.InlineKeyboardButton("▶️ تشغيل", callback_data=f"start_file_{fid}"))
    kb.add(types.InlineKeyboardButton("🗑️ حذف", callback_data=f"del_file_{fid}"))
    kb.add(types.InlineKeyboardButton("📋 سجل", callback_data=f"file_log_{fid}"))
    if ext == "py":
        kb.add(types.InlineKeyboardButton("🔑 تغيير التوكن", callback_data=f"file_change_token_{fid}"))
        kb.add(types.InlineKeyboardButton("🆔 تغيير الأدمن", callback_data=f"file_change_admin_{fid}"))
    kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data=f"file_update_{fid}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="my_files"))
    send_q(chat_id, info, reply_markup=kb)

def show_file_log(chat_id, user_id, fid):
    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if str(user_id) != f["owner"] and not is_admin(user_id):
        send_q(chat_id, "🔒 لا صلاحية.")
        return
    log_path = container_manager.get_log_path(f["owner"], fid)
    if not os.path.exists(log_path):
        send_q(chat_id, "📋 لا يوجد سجل.")
        return
    with open(log_path, 'r') as log_file:
        lines = log_file.readlines()
    last_lines = lines[-50:] if len(lines) > 50 else lines
    log_text = "".join(last_lines)
    if len(log_text) > 4000:
        with open(log_path, "rb") as f_log:
            bot.send_document(chat_id, f_log, caption=f"📋 سجل {esc(f['filename'])}")
    else:
        send_q(chat_id, f"<b>سجل التشغيل (آخر {len(last_lines)} سطر):</b>\n<pre>{esc(log_text)}</pre>")

def change_file_token(chat_id, user_id, fid):
    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if str(user_id) != f["owner"] and not is_admin(user_id):
        send_q(chat_id, "🔒 لا صلاحية.")
        return
    ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
    if ext != "py":
        send_q(chat_id, "❌ فقط لملفات بايثون.")
        return
    pending_action[user_id] = {"action": "awaiting_token_change", "fid": fid}
    send_q(chat_id, "🔑 أرسل التوكن الجديد (مثال: 123456:ABC-DEF):")

def change_file_admin(chat_id, user_id, fid):
    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if str(user_id) != f["owner"] and not is_admin(user_id):
        send_q(chat_id, "🔒 لا صلاحية.")
        return
    ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
    if ext != "py":
        send_q(chat_id, "❌ فقط لملفات بايثون.")
        return
    pending_action[user_id] = {"action": "awaiting_admin_change", "fid": fid}
    send_q(chat_id, "🔑 أرسل معرف الأدمن الجديد (رقم):")

def update_file_prompt(chat_id, user_id, fid):
    f = db["files"].get(fid)
    if not f:
        send_q(chat_id, "❌ الملف غير موجود.")
        return
    if str(user_id) != f["owner"] and not is_admin(user_id):
        send_q(chat_id, "🔒 لا صلاحية.")
        return
    pending_action[user_id] = {"action": "awaiting_file_update", "fid": fid}
    send_q(chat_id, "📤 أرسل الملف الجديد (py/js/php/zip):")

def show_store(chat_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    for item_id, item in db["store"].items():
        kb.add(types.InlineKeyboardButton(f"🛍️ {item['name']} - {item['price']}", callback_data=f"buy_{item_id}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
    send_q(chat_id, "🛍️ اختر باقة:", reply_markup=kb)

def handle_buy(chat_id, user_id, item_id):
    item = db["store"].get(item_id)
    if not item:
        send_q(chat_id, "❌ المنتج غير موجود.")
        return
    order_id = short_id()
    db["orders"][order_id] = {"user": str(user_id), "item_id": item_id, "status": "pending", "created": now_iso()}
    save_db()
    send_q(chat_id, f"✅ تم تسجيل طلبك.\n📦 {item['name']} - {item['price']}\n📩 تواصل مع الدعم: {db['settings'].get('support_account', CONTACT_USERNAME)}")
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_order_{order_id}"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_order_{order_id}"),
    )
    username = db["users"].get(str(user_id), {}).get("username", "")
    admin_caption = f"🛒 طلب شراء جديد\n👤 @{esc(username)} ({user_id})\n📦 {item['name']} - {item['price']}"
    send_admin_user_card(ADMIN_ID, user_id, admin_caption, reply_markup=kb)
    send_to_trust_channel(f"🛒 طلب شراء من @{esc(username)}: {item['name']}")

def show_account(chat_id, user_id):
    u = db["users"].get(str(user_id), {})
    n_files = len([f for f in db["files"].values() if f["owner"] == str(user_id)])
    caption = f"👤 <b>حسابك</b>\n🆔 {user_id}\n💎 النقاط: {u.get('points', 0)}\n📁 الملفات: {n_files}\n👥 الإحالات: {u.get('referrals', 0)}\n📅 الانضمام: {esc(u.get('joined', '')[:10])}"
    send_user_card(chat_id, user_id, caption)

def handle_daily_gift(chat_id, user_id):
    u = db["users"][str(user_id)]
    last = u.get("last_daily")
    if last:
        try:
            if datetime.now() - datetime.fromisoformat(last) < timedelta(hours=24):
                remain = timedelta(hours=24) - (datetime.now() - datetime.fromisoformat(last))
                h = int(remain.total_seconds() // 3600)
                send_q(chat_id, f"⏳ انتظر {h} ساعة.")
                return
        except:
            pass
    gift = db["settings"]["daily_gift"]
    u["points"] += gift
    u["last_daily"] = now_iso()
    save_db()
    send_q(chat_id, f"🎁 حصلت على {gift} نقطة. رصيدك: {u['points']}")

def show_vip_plans(chat_id):
    vips = db["settings"].get("vip_plans", [])
    if not vips:
        send_q(chat_id, "💎 لا توجد خطط VIP.")
        return
    kb = types.InlineKeyboardMarkup(row_width=2)
    for idx, plan in enumerate(vips):
        kb.add(types.InlineKeyboardButton(f"💎 {plan.get('name', '')} - {plan.get('price', '')}", callback_data=f"vip_buy_{idx}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
    send_q(chat_id, "💎 اختر باقة VIP:", reply_markup=kb)

def handle_vip_buy(chat_id, user_id, plan_idx):
    vips = db["settings"].get("vip_plans", [])
    try:
        plan = vips[int(plan_idx)]
    except:
        send_q(chat_id, "❌ الخطة غير موجودة.")
        return
    order_id = short_id()
    db["orders"][order_id] = {"user": str(user_id), "item_id": f"vip_{plan_idx}", "status": "pending", "created": now_iso(), "vip_plan": plan}
    save_db()
    send_q(chat_id, f"✅ تم تسجيل طلب VIP.\n💎 {plan['name']} - {plan['price']}\n📩 تواصل مع الدعم: {db['settings'].get('support_account', CONTACT_USERNAME)}")
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_vip_{order_id}"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_vip_{order_id}"),
    )
    username = db["users"].get(str(user_id), {}).get("username", "")
    admin_caption = f"💎 طلب VIP جديد\n👤 @{esc(username)} ({user_id})\n💎 {plan['name']} - {plan['price']}"
    send_admin_user_card(ADMIN_ID, user_id, admin_caption, reply_markup=kb)
    send_to_vip_channel(f"💎 طلب VIP من @{esc(username)}: {plan['name']}")

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
        send_q(chat_id, "✅ تم قبول VIP.")
        send_to_vip_channel(f"✅ قبول VIP #{order_id}")
        try:
            send_user_card(int(order["user"]), int(order["user"]), f"🎉 تم قبول VIP الخاص بك! +{points_to_add} نقطة.")
        except:
            pass
    else:
        order["status"] = "rejected"
        send_q(chat_id, "❌ تم رفض VIP.")
        try:
            send_user_card(int(order["user"]), int(order["user"]), "❌ تم رفض طلب VIP.")
        except:
            pass
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
        send_q(chat_id, "✅ تمت الموافقة وجاري التشغيل.")
        owner_id = int(f["owner"])
        owner_name = get_user_name(owner_id)
        points = get_points(owner_id)
        daily_cost = db["settings"]["daily_cost"]
        expected_days = points // daily_cost if daily_cost > 0 else 0
        icon = get_file_type_icon(f.get('filename', ''))
        ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
        message_text = f"🚀 تشغيل ملف جديد\n{icon} {f['filename']}\n📦 {ext}\n👤 {esc(owner_name)}\n💎 {points} نقطة\n⏳ {expected_days} يوم (التكلفة: {daily_cost} نقطة/يوم)"
        send_to_trust_channel(message_text)
        try:
            send_user_card(owner_id, owner_id, f"🎉 تم تشغيل ملفك:\n📄 {f['filename']}\n📦 {ext}")
        except:
            pass
    else:
        f["status"] = "rejected"
        save_db()
        send_q(chat_id, "❌ تم رفض الملف.")
        try:
            send_user_card(int(f["owner"]), int(f["owner"]), f"📄 تم رفض ملفك: {f['filename']}")
        except:
            pass

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
        send_q(chat_id, "🔒 لا صلاحية.")
        return
    ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
    if act == "stop":
        stop_hosted_bot(fid)
        send_q(chat_id, "⏹️ تم إيقاف البوت.")
    elif act == "start":
        if ext == "zip":
            send_q(chat_id, "📦 هذا ملف ZIP، سيتم استخراجه عند الموافقة.")
            return
        if get_points(int(f["owner"])) < db["settings"]["daily_cost"]:
            send_q(chat_id, "❌ النقاط غير كافية.")
            return
        threading.Thread(target=start_hosted_bot, args=(fid,), daemon=True).start()
        send_q(chat_id, "▶️ جاري التشغيل.")
    else:
        stop_hosted_bot(fid)
        try:
            os.remove(f["path"])
        except:
            pass
        db["files"].pop(fid, None)
        save_db()
        send_q(chat_id, "🗑️ تم حذف الملف.")

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
        send_q(chat_id, "✅ تم قبول الطلب.")
        send_to_trust_channel(f"✅ قبول طلب شراء: {item.get('name', '')}")
        try:
            send_user_card(int(order["user"]), int(order["user"]), f"🎁 تم تأكيد طلبك! +{item.get('points', 0)} نقطة.")
        except:
            pass
    else:
        order["status"] = "rejected"
        send_q(chat_id, "❌ تم رفض الطلب.")
        try:
            send_user_card(int(order["user"]), int(order["user"]), "📦 تم رفض طلبك.")
        except:
            pass
    save_db()

def handle_admin_callback(chat_id, user_id, data):
    if data == "admin_upload_requests":
        pending = {fid: f for fid, f in db["files"].items() if f["status"] == "pending"}
        if not pending:
            send_q(chat_id, "📂 لا توجد طلبات.")
            return
        for fid, f in pending.items():
            icon = get_file_type_icon(f.get('filename', ''))
            ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_file_{fid}"),
                types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_file_{fid}"),
            )
            send_q(chat_id, f"{icon} {esc(f['filename'])} [{ext}]\n👤 {get_user_name(f['owner'])}", reply_markup=kb)
    elif data == "admin_order_requests":
        pending = {oid: o for oid, o in db["orders"].items() if o["status"] == "pending"}
        if not pending:
            send_q(chat_id, "🛍️ لا توجد طلبات.")
            return
        for oid, o in pending.items():
            item = db["store"].get(o["item_id"], {})
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_order_{oid}"),
                types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_order_{oid}"),
            )
            send_q(chat_id, f"🛒 {item.get('name', '')} - {item.get('price', '')}\n👤 {get_user_name(o['user'])}", reply_markup=kb)
    elif data == "admin_users":
        total = len(db["users"])
        active = len([u for u in db["users"].values() if u.get("points", 0) > 0])
        send_q(chat_id, f"👥 إجمالي: {total}\nنشطاء: {active}")
    elif data == "admin_free_plan":
        db["settings"]["free_plan"] = not db["settings"]["free_plan"]
        save_db()
        state = "مفعلة ✅" if db["settings"]["free_plan"] else "معطلة ❌"
        send_q(chat_id, f"🎁 الخطة المجانية: {state}\n💎 نقاط البداية: {db['settings']['free_points']}")
    elif data == "admin_broadcast":
        pending_action[user_id] = {"action": "awaiting_broadcast"}
        send_q(chat_id, "📣 اكتب الرسالة للإذاعة:")
    elif data == "admin_all_files":
        if not db["files"]:
            send_q(chat_id, "📁 لا توجد ملفات.")
            return
        for fid, f in db["files"].items():
            status_text = STATUS_AR.get(f.get('status', ''), f.get('status', 'غير معروف'))
            icon = get_file_type_icon(f.get('filename', ''))
            ext = f.get('file_ext', get_file_extension(f.get('filename', '')))
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("⏹️ إيقاف", callback_data=f"stop_file_{fid}"),
                types.InlineKeyboardButton("🗑️ حذف", callback_data=f"del_file_{fid}"),
            )
            send_q(chat_id, f"{icon} <b>{esc(f['filename'])}</b> [{ext}]\n{status_text}\n👤 {get_user_name(f['owner'])}", reply_markup=kb)
    elif data == "admin_manage_store":
        kb = types.InlineKeyboardMarkup(row_width=2)
        for iid, item in db["store"].items():
            kb.add(types.InlineKeyboardButton(f"🗑️ حذف: {item['name']}", callback_data=f"delitem_{iid}"))
        kb.add(types.InlineKeyboardButton("➕ إضافة منتج", callback_data="additem"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        send_q(chat_id, "🛒 إدارة المتجر", reply_markup=kb)
    elif data == "additem":
        pending_action[user_id] = {"action": "awaiting_new_item"}
        send_q(chat_id, "➕ أرسل: الاسم|النقاط|السعر")
    elif data.startswith("delitem_"):
        item_id = data[len("delitem_"):]
        if item_id in db["store"]:
            del db["store"][item_id]
            save_db()
            send_q(chat_id, "🗑️ تم حذف المنتج.")
        else:
            send_q(chat_id, "❌ المنتج غير موجود.")
    elif data == "admin_points_settings":
        pending_action[user_id] = {"action": "awaiting_daily_cost"}
        send_q(chat_id, f"💰 التكلفة اليومية: {db['settings']['daily_cost']}\nأرسل القيمة الجديدة (رقم):")
    elif data == "admin_daily_gift_settings":
        pending_action[user_id] = {"action": "awaiting_daily_gift"}
        send_q(chat_id, f"🎁 الهدية اليومية: {db['settings']['daily_gift']}\nأرسل القيمة الجديدة (رقم):")
    elif data == "admin_channels":
        channels = db["settings"]["channels"]
        text = "📡 القنوات:\n" + ("\n".join(channels) if channels else "لا توجد قنوات.")
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➕ إضافة", callback_data="add_channel"))
        kb.add(types.InlineKeyboardButton("🗑️ حذف", callback_data="remove_channel"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        send_q(chat_id, text, reply_markup=kb)
    elif data == "add_channel":
        pending_action[user_id] = {"action": "awaiting_channel"}
        send_q(chat_id, "➕ أرسل يوزر القناة (مثال: @mychannel):")
    elif data == "remove_channel":
        pending_action[user_id] = {"action": "awaiting_remove_channel"}
        send_q(chat_id, "❌ أرسل يوزر القناة للحذف:")
    elif data == "admin_settings":
        s = db["settings"]
        send_q(chat_id, f"⚙️ الإعدادات\n💰 التكلفة: {s['daily_cost']}\n🎁 الخطة المجانية: {'مفعلة' if s['free_plan'] else 'معطلة'}\n💎 نقاط البداية: {s['free_points']}\n🎁 الهدية: {s['daily_gift']}\n🔗 مكافأة الإحالة: {s['referral_bonus']}")
    elif data == "admin_system_stats":
        try:
            import psutil
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            processes = len(running_processes)
            send_q(chat_id, f"📊 النظام\n🖥 CPU: {cpu}%\n🧠 RAM: {mem.used//(1024**2)}/{mem.total//(1024**2)} ميجابايت\n💾 القرص: {disk.used//(1024**3)}/{disk.total//(1024**3)} جيجابايت\n🔄 عمليات نشطة: {processes}")
        except:
            send_q(chat_id, "⚠️ لم نتمكن من جلب الإحصائيات.")
    elif data == "admin_pinned_announcement":
        current = db["settings"].get("pinned_announcement") or "لا يوجد"
        pending_action[user_id] = {"action": "awaiting_pinned_announcement"}
        send_q(chat_id, f"📌 الإعلان المثبت:\n{current}\nأرسل النص الجديد (أو /cancel):")
    elif data == "admin_welcome_photo":
        pending_action[user_id] = {"action": "awaiting_welcome_photo"}
        send_q(chat_id, "🖼 أرسل الصورة الترحيبية:")
    elif data == "admin_welcome_message":
        current = db["settings"].get("welcome_message", "👋 مرحباً بك!")
        pending_action[user_id] = {"action": "awaiting_welcome_message"}
        send_q(chat_id, f"📝 الرسالة الحالية:\n{current}\nأرسل النص الجديد:")
    elif data == "admin_support_account":
        current = db["settings"].get("support_account", CONTACT_USERNAME)
        pending_action[user_id] = {"action": "awaiting_support_account"}
        send_q(chat_id, f"📞 حساب الدعم: {current}\nأرسل الحساب الجديد:")
    elif data == "admin_trust_channel":
        current = db["settings"].get("trust_channel") or "غير محدد"
        pending_action[user_id] = {"action": "awaiting_trust_channel"}
        send_q(chat_id, f"📡 قناة الثقة: {current}\nأرسل المعرف الجديد (أو 'إلغاء'):")
    elif data == "admin_ban_management":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("🚫 حظر", callback_data="admin_ban_user"))
        kb.add(types.InlineKeyboardButton("✅ فك حظر", callback_data="admin_unban_user"))
        kb.add(types.InlineKeyboardButton("📋 المحظورين", callback_data="admin_banned_list"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        send_q(chat_id, "🚫 إدارة الحظر", reply_markup=kb)
    elif data == "admin_ban_user":
        pending_action[user_id] = {"action": "awaiting_ban_user"}
        send_q(chat_id, "🚫 أرسل آيدي المستخدم للحظر:")
    elif data == "admin_unban_user":
        pending_action[user_id] = {"action": "awaiting_unban_user"}
        send_q(chat_id, "✅ أرسل آيدي المستخدم لفك الحظر:")
    elif data == "admin_banned_list":
        banned = [uid for uid, u in db["users"].items() if u.get("banned")]
        if not banned:
            send_q(chat_id, "📋 لا يوجد محظورون.")
        else:
            text = "🚫 المحظورون:\n" + "\n".join([f"🆔 {uid}" for uid in banned])
            send_q(chat_id, text)
    elif data == "admin_manage_admins":
        admins = db.get("admins", [ADMIN_ID])
        text = "👥 الأدمن:\n" + "\n".join([f"🆔 {aid}" for aid in admins])
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➕ إضافة أدمن", callback_data="admin_add_admin"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        send_q(chat_id, text, reply_markup=kb)
    elif data == "admin_add_admin":
        pending_action[user_id] = {"action": "awaiting_add_admin"}
        send_q(chat_id, "➕ أرسل آيدي المستخدم للإضافة كأدمن:")
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
        send_q(chat_id, f"📊 إحصائيات تفصيلية\n👥 المستخدمين: {total_users}\n🚫 محظورون: {banned_count}\n📄 الملفات: {total_files}\n   - معلقة: {pending_files}\n   - شغالة: {running_files}\n🛒 الطلبات: {total_orders}\n   - معلقة: {pending_orders}\n   - مقبولة: {approved_orders}\n💎 النقاط: {total_points}")
    elif data == "admin_export_orders":
        csv_data = export_orders_to_csv()
        if not csv_data:
            send_q(chat_id, "📋 لا توجد طلبات.")
            return
        bot.send_document(chat_id, ("orders.csv", csv_data), caption="📋 تصدير الطلبات")
    elif data == "admin_backup":
        backup_path = backup_uploaded_files()
        if not backup_path:
            send_q(chat_id, "📦 لا توجد ملفات للنسخ.")
            return
        with open(backup_path, 'rb') as f:
            bot.send_document(chat_id, f, caption="📦 نسخة احتياطية للملفات")
        os.remove(backup_path)
    elif data == "admin_toggle_bot":
        global bot_enabled
        bot_enabled = not bot_enabled
        send_q(chat_id, f"🔘 البوت: {'مفعل' if bot_enabled else 'معطل'}")
    elif data == "admin_accepted_orders":
        accepted = {oid: o for oid, o in db["orders"].items() if o["status"] == "approved"}
        if not accepted:
            send_q(chat_id, "📋 لا توجد طلبات مقبولة.")
            return
        for oid, o in accepted.items():
            item = db["store"].get(o["item_id"], {})
            send_q(chat_id, f"🛒 طلب #{oid}\n📦 {item.get('name', '')}\n👤 {get_user_name(o['user'])}")
    elif data == "admin_pending_orders":
        pending = {oid: o for oid, o in db["orders"].items() if o["status"] == "pending"}
        if not pending:
            send_q(chat_id, "📋 لا توجد طلبات معلقة.")
            return
        for oid, o in pending.items():
            item = db["store"].get(o["item_id"], {})
            send_q(chat_id, f"🛒 طلب #{oid}\n📦 {item.get('name', '')}\n👤 {get_user_name(o['user'])}")
    elif data == "admin_find_order":
        pending_action[user_id] = {"action": "awaiting_find_order"}
        send_q(chat_id, "🔍 أرسل رقم الطلب:")
    elif data == "admin_latest_users":
        users = sorted(db["users"].items(), key=lambda x: x[1].get("joined", ""), reverse=True)[:10]
        if not users:
            send_q(chat_id, "📋 لا يوجد مستخدمون.")
            return
        text = "🆕 أحدث المستخدمين:\n" + "\n".join([f"🆔 {uid} - {u.get('username', 'بدون اسم')} (📅 {u.get('joined', '')[:10]})" for uid, u in users])
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
        send_q(chat_id, "📨 أرسل:\n<code>user_id\nالرسالة</code>")
    elif data == "admin_active_users":
        active = [uid for uid, u in db["users"].items() if u.get("last_activity") and datetime.fromisoformat(u["last_activity"]) > datetime.now() - timedelta(days=7)]
        if not active:
            send_q(chat_id, "🌟 لا يوجد نشطاء خلال 7 أيام.")
        else:
            text = "🌟 النشطاء (آخر 7 أيام):\n" + "\n".join([f"🆔 {uid}" for uid in active[:20]])
            send_q(chat_id, text)
    elif data == "admin_manage_subscriptions":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("💰 تعديل الأسعار", callback_data="admin_edit_subscription_prices"))
        kb.add(types.InlineKeyboardButton("💎 إدارة VIP", callback_data="admin_manage_vip"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        send_q(chat_id, "🔄 إدارة الاشتراكات", reply_markup=kb)
    elif data == "admin_edit_subscription_prices":
        store = db["store"]
        if not store:
            send_q(chat_id, "🛒 لا توجد منتجات.")
            return
        for iid, item in store.items():
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("✏️ تعديل", callback_data=f"edit_price_{iid}"))
            send_q(chat_id, f"📦 {item['name']}\n💰 السعر: {item['price']}", reply_markup=kb)
        kb_back = types.InlineKeyboardMarkup()
        kb_back.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_subscriptions"))
        send_q(chat_id, "اختر منتجاً:", reply_markup=kb_back)
    elif data.startswith("edit_price_"):
        item_id = data[len("edit_price_"):]
        if item_id not in db["store"]:
            send_q(chat_id, "❌ المنتج غير موجود.")
            return
        pending_action[user_id] = {"action": "awaiting_edit_price", "item_id": item_id}
        send_q(chat_id, f"💰 أرسل السعر الجديد لـ {db['store'][item_id]['name']}:")
    elif data == "admin_manage_vip":
        vips = db["settings"].get("vip_plans", [])
        if not vips:
            text = "💎 لا توجد خطط VIP."
        else:
            text = "💎 خطط VIP:\n" + "\n".join([f"{idx+1}. {plan.get('name', '')} - {plan.get('price', '')} ({plan.get('points', 0)} نقطة)" for idx, plan in enumerate(vips)])
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➕ إضافة خطة", callback_data="admin_add_vip_plan"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_subscriptions"))
        send_q(chat_id, text, reply_markup=kb)
    elif data == "admin_add_vip_plan":
        pending_action[user_id] = {"action": "awaiting_vip_plan"}
        send_q(chat_id, "➕ أرسل: الاسم|السعر|النقاط")
    elif data == "admin_backup_settings":
        current = db["settings"].get("max_backups", 200)
        pending_action[user_id] = {"action": "awaiting_max_backups"}
        send_q(chat_id, f"📦 الحد الأقصى للنسخ: {current}\nأرسل الرقم الجديد:")

def show_users_page(chat_id, user_id, page):
    users = list(db["users"].items())
    page_size = 20
    total = len(users)
    start = page * page_size
    end = min(start + page_size, total)
    if start >= total:
        send_q(chat_id, "📋 لا توجد صفحات إضافية.")
        return
    text = "👥 المستخدمين:\n" + "\n".join([f"🆔 {uid} - {u.get('username', 'بدون اسم')} (💎 {u.get('points',0)})" for uid, u in users[start:end]])
    kb = types.InlineKeyboardMarkup(row_width=2)
    if page > 0:
        kb.add(types.InlineKeyboardButton("⬅️ السابق", callback_data=f"users_page_{page-1}"))
    if end < total:
        kb.add(types.InlineKeyboardButton("➡️ التالي", callback_data=f"users_page_{page+1}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    send_q(chat_id, text, reply_markup=kb)

# ===================== دوال الـ Callback =====================
@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    global bot_enabled
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    if not bot_enabled and not is_admin(user_id):
        bot.answer_callback_query(call.id, "⛔ البوت متوقف.", show_alert=True)
        return
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "🚫 أنت محظور.", show_alert=True)
        return
    ensure_user(user_id, call.from_user.username)
    update_last_activity(user_id)

    now = time.time()
    if user_id in cooldown and now - cooldown[user_id] < 2:
        bot.answer_callback_query(call.id, "⏳ انتظر قليلاً.", show_alert=True)
        return
    cooldown[user_id] = now

    try:
        bot.answer_callback_query(call.id)

        if data == "support":
            support = db["settings"].get("support_account", CONTACT_USERNAME)
            if support:
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("📞 تواصل", url=f'https://t.me/{support.lstrip("@")}'))
                send_q(chat_id, f"📞 حساب الدعم: {support}", reply_markup=kb)
            else:
                send_q(chat_id, "📞 لم يتم تعيين حساب دعم.")
        elif data == "trust_channel":
            channel = db["settings"].get("trust_channel")
            if channel:
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("📢 افتح القناة", url=f'https://t.me/{channel.lstrip("@")}'))
                send_q(chat_id, f"📢 قناة الثقة: {channel}", reply_markup=kb)
            else:
                send_q(chat_id, "📢 لم يتم تعيين قناة ثقة.")
        elif data == "check_sub":
            ok, _ = check_force_sub(user_id)
            if ok:
                edit_q("✅ تم التحقق.", chat_id, call.message.message_id, reply_markup=main_menu_kb(user_id))
            else:
                bot.answer_callback_query(call.id, "❌ مازال الاشتراك مفقوداً.", show_alert=True)
        elif data == "back_main":
            edit_q("🏠 القائمة الرئيسية.", chat_id, call.message.message_id, reply_markup=main_menu_kb(user_id))
        elif data == "upload_file":
            pending_action[user_id] = {"action": "awaiting_file"}
            send_q(chat_id, f"📤 أرسل ملف .py/.js/.php/.zip\n💎 التكلفة اليومية: {db['settings']['daily_cost']} نقطة\n📊 رصيدك: {get_points(user_id)}")
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
            send_q(chat_id, "📖 1. ارفع ملف .py/.js/.php/.zip\n2. انتظر الموافقة\n3. سيعمل تلقائياً\n4. تكلفة يومية: {db['settings']['daily_cost']} نقطة\n5. ادعُ أصدقاءك للحصول على نقاط.")
        elif data == "my_points":
            send_q(chat_id, f"💎 رصيدك: {get_points(user_id)} نقطة\n📅 التكلفة اليومية: {db['settings']['daily_cost']} نقطة")
        elif data == "invite":
            link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
            bonus = db["settings"]["referral_bonus"]
            send_q(chat_id, f"🔗 رابط دعوتك:\n<code>{link}</code>\n🎁 مكافأة: {bonus} نقطة لكل صديق.")
        elif data == "daily_gift":
            handle_daily_gift(chat_id, user_id)
        elif data == "ask_admin":
            pending_action[user_id] = {"action": "awaiting_question"}
            send_q(chat_id, "💬 اكتب سؤالك:")
        elif data == "admin_panel" and is_admin(user_id):
            edit_q("🛡️ لوحة الإدارة", chat_id, call.message.message_id, reply_markup=admin_menu_kb())
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
            send_q(chat_id, "➕ أرسل آيدي المستخدم لإضافة نقاط له:")
        elif (data.startswith("admin_") or data in ("additem", "add_channel", "remove_channel") or data.startswith("delitem_") or data.startswith("edit_price_")) and is_admin(user_id):
            handle_admin_callback(chat_id, user_id, data)
    except Exception as e:
        logger.error(f"خطأ في callback: {e}")
        try:
            bot.send_message(chat_id, "حدث خطأ، حاول مرة أخرى.")
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
                    bot.send_message(int(uid), f"📣 <b>إعلان</b>\n\n{esc(message.text)}", parse_mode="HTML")
                    count += 1
                except:
                    pass
            reply_q(message, f"✅ تم الإرسال إلى {count} مستخدم.")
        elif action == "awaiting_question":
            username = message.from_user.username or "بدون_يوزر"
            admin_caption = f"💬 سؤال من @{esc(username)} ({user_id})\n\n{esc(message.text)}"
            sent_msg = bot.send_message(ADMIN_ID, q(admin_caption), parse_mode="HTML")
            question_messages[sent_msg.message_id] = user_id
            reply_q(message, "✅ وصل سؤالك للإدارة.")
        elif action == "awaiting_new_item" and is_admin(user_id):
            try:
                name, points, price = message.text.split("|")
                db["store"][short_id()] = {"name": name.strip(), "points": int(points.strip()), "price": price.strip()}
                save_db()
                reply_q(message, "✅ تمت الإضافة.")
            except:
                reply_q(message, "❌ الصيغة غير صحيحة. استعمل: الاسم|النقاط|السعر")
        elif action == "awaiting_daily_cost" and is_admin(user_id):
            try:
                db["settings"]["daily_cost"] = int(message.text.strip())
                save_db()
                reply_q(message, "✅ تم التحديث.")
            except:
                reply_q(message, "❌ يجب إدخال رقم.")
        elif action == "awaiting_daily_gift" and is_admin(user_id):
            try:
                db["settings"]["daily_gift"] = int(message.text.strip())
                save_db()
                reply_q(message, "✅ تم التحديث.")
            except:
                reply_q(message, "❌ يجب إدخال رقم.")
        elif action == "awaiting_channel" and is_admin(user_id):
            db["settings"]["channels"].append(message.text.strip())
            save_db()
            reply_q(message, "✅ تمت الإضافة.")
        elif action == "awaiting_remove_channel" and is_admin(user_id):
            ch = message.text.strip()
            if ch in db["settings"]["channels"]:
                db["settings"]["channels"].remove(ch)
                save_db()
                reply_q(message, f"✅ تم حذف {ch}.")
            else:
                reply_q(message, f"❌ {ch} غير موجودة.")
        elif action == "awaiting_pinned_announcement" and is_admin(user_id):
            db["settings"]["pinned_announcement"] = message.text
            save_db()
            reply_q(message, "📌 تم التحديث.")
        elif action == "awaiting_welcome_message" and is_admin(user_id):
            db["settings"]["welcome_message"] = message.text
            save_db()
            reply_q(message, "📝 تم التحديث.")
        elif action == "awaiting_support_account" and is_admin(user_id):
            db["settings"]["support_account"] = message.text.strip()
            save_db()
            reply_q(message, f"📞 تم التحديث إلى {message.text}.")
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
                    reply_q(message, f"🚫 تم حظر {target}.")
                else:
                    reply_q(message, "❌ المستخدم غير موجود.")
            except:
                reply_q(message, "❌ يجب إدخال رقم آيدي صحيح.")
        elif action == "awaiting_unban_user" and is_admin(user_id):
            try:
                target = int(message.text.strip())
                uid = str(target)
                if uid in db["users"]:
                    db["users"][uid]["banned"] = False
                    save_db()
                    reply_q(message, f"✅ تم فك حظر {target}.")
                else:
                    reply_q(message, "❌ المستخدم غير موجود.")
            except:
                reply_q(message, "❌ يجب إدخال رقم آيدي صحيح.")
        elif action == "awaiting_add_admin" and is_admin(user_id):
            try:
                target = int(message.text.strip())
                if target not in db["admins"]:
                    db["admins"].append(target)
                    save_db()
                    reply_q(message, f"✅ تمت إضافة {target} كأدمن.")
                else:
                    reply_q(message, f"ℹ️ {target} أدمن بالفعل.")
            except:
                reply_q(message, "❌ يجب إدخال رقم آيدي صحيح.")
        elif action == "awaiting_find_order" and is_admin(user_id):
            order_id = message.text.strip()
            order = db["orders"].get(order_id)
            if not order:
                reply_q(message, f"❌ لا يوجد طلب {order_id}.")
                return
            item = db["store"].get(order["item_id"], {})
            text = f"📋 تفاصيل الطلب #{order_id}\n👤 {get_user_name(order['user'])}\n📦 {item.get('name', '')}\n💰 {item.get('price', '')}\n📅 {order.get('created', '')}\n📌 {order.get('status', '')}"
            send_q(chat_id, text)
        elif action == "awaiting_send_user_id" and is_admin(user_id):
            lines = message.text.split("\n", 1)
            if len(lines) < 2:
                reply_q(message, "❌ يجب أن يكون السطر الأول آيدي والثاني الرسالة.")
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
                except:
                    pass
            if target_user_id is None:
                reply_q(message, "❌ لم أجد المستخدم.")
                return
            try:
                bot.send_message(target_user_id, f"📨 <b>رسالة من الإدارة</b>\n\n{esc(msg_text)}", parse_mode="HTML")
                reply_q(message, f"✅ تم الإرسال إلى {target_user_id}.")
            except Exception as e:
                reply_q(message, f"❌ فشل الإرسال: {e}")
        elif action == "awaiting_edit_price" and is_admin(user_id):
            item_id = pending_action[user_id].get("item_id")
            if not item_id or item_id not in db["store"]:
                reply_q(message, "❌ المنتج غير موجود.")
                pending_action.pop(user_id, None)
                return
            new_price = message.text.strip()
            db["store"][item_id]["price"] = new_price
            save_db()
            reply_q(message, f"✅ تم تحديث السعر إلى {new_price}.")
        elif action == "awaiting_vip_plan" and is_admin(user_id):
            try:
                name, price, points = message.text.split("|")
                plan = {"name": name.strip(), "price": price.strip(), "points": int(points.strip())}
                db["settings"].setdefault("vip_plans", []).append(plan)
                save_db()
                reply_q(message, "✅ تمت إضافة خطة VIP.")
            except:
                reply_q(message, "❌ الصيغة غير صحيحة. استعمل: الاسم|السعر|النقاط")
        elif action == "awaiting_max_backups" and is_admin(user_id):
            try:
                new_val = int(message.text.strip())
                if new_val < 1:
                    reply_q(message, "❌ يجب أن يكون أكبر من 0.")
                    return
                db["settings"]["max_backups"] = new_val
                save_db()
                reply_q(message, f"✅ تم التحديث إلى {new_val}.")
            except:
                reply_q(message, "❌ يجب إدخال رقم صحيح.")
        elif action == "awaiting_token_change":
            fid = pending_action[user_id].get("fid")
            if not fid or fid not in db["files"]:
                reply_q(message, "❌ الملف غير موجود.")
                pending_action.pop(user_id, None)
                return
            f = db["files"][fid]
            if str(user_id) != f["owner"] and not is_admin(user_id):
                reply_q(message, "🔒 لا صلاحية.")
                pending_action.pop(user_id, None)
                return
            new_token = message.text.strip()
            try:
                with open(f["path"], "r") as file:
                    content = file.read()
                pattern = r'(BOT_TOKEN\s*=\s*["\'])([^"\']*)(["\'])'
                if re.search(pattern, content):
                    new_content = re.sub(pattern, rf'\g<1>{new_token}\g<3>', content)
                else:
                    new_content = f'BOT_TOKEN = "{new_token}"\n' + content
                with open(f["path"], "w") as file:
                    file.write(new_content)
                reply_q(message, "✅ تم تغيير التوكن.")
            except Exception as e:
                reply_q(message, f"❌ فشل: {e}")
            pending_action.pop(user_id, None)
        elif action == "awaiting_admin_change":
            fid = pending_action[user_id].get("fid")
            if not fid or fid not in db["files"]:
                reply_q(message, "❌ الملف غير موجود.")
                pending_action.pop(user_id, None)
                return
            f = db["files"][fid]
            if str(user_id) != f["owner"] and not is_admin(user_id):
                reply_q(message, "🔒 لا صلاحية.")
                pending_action.pop(user_id, None)
                return
            new_admin = message.text.strip()
            try:
                with open(f["path"], "r") as file:
                    content = file.read()
                pattern = r'(ADMIN_ID\s*=\s*)(\d+)'
                if re.search(pattern, content):
                    new_content = re.sub(pattern, rf'\g<1>{new_admin}', content)
                else:
                    new_content = f'ADMIN_ID = {new_admin}\n' + content
                with open(f["path"], "w") as file:
                    file.write(new_content)
                reply_q(message, "✅ تم تغيير معرف الأدمن.")
            except Exception as e:
                reply_q(message, f"❌ فشل: {e}")
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
                reply_q(message, f"✅ المستخدم {target} موجود. أرسل عدد النقاط:")
            except:
                reply_q(message, "❌ يجب إدخال رقم آيدي صحيح.")
                pending_action.pop(user_id, None)
        elif action == "awaiting_send_points_amount" and is_admin(user_id):
            target = pending_action[user_id].get("target_user")
            if not target:
                reply_q(message, "❌ حدث خطأ.")
                pending_action.pop(user_id, None)
                return
            try:
                amount = int(message.text.strip())
                if amount <= 0:
                    reply_q(message, "❌ يجب أن يكون أكبر من صفر.")
                    return
                add_points(target, amount)
                try:
                    bot.send_message(target, f"🎉 تمت إضافة <b>{amount}</b> نقطة من الإدارة.", parse_mode="HTML")
                except:
                    pass
                reply_q(message, f"✅ تمت إضافة {amount} نقطة إلى {target}.")
                pending_action.pop(user_id, None)
            except:
                reply_q(message, "❌ يجب إدخال رقم صحيح.")
        pending_action.pop(user_id, None)
    except Exception as e:
        logger.error(f"خطأ في handle_pending_text: {e}")
        reply_q(message, "حدث خطأ، حاول مرة أخرى.")
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
                reply_q(message, "🖼 يرجى إرسال صورة.")
                return
            db["settings"]["welcome_photo"] = file_id
            save_db()
            reply_q(message, "🖼 تم تحديث الصورة.")
            pending_action.pop(user_id, None)
        except Exception as e:
            reply_q(message, f"❌ فشل: {e}")

# ===================== الميزات الجديدة =====================
@bot.message_handler(commands=['sendmsg'])
def cmd_sendmsg(message):
    if not is_admin(message.from_user.id):
        reply_q(message, "❌ هذا الأمر للأدمن فقط.")
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            reply_q(message, "⚠️ استخدم: /sendmsg @username الرسالة")
            return
        identifier = parts[1]
        msg_text = parts[2]
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
            except:
                pass
        if target_user_id is None:
            reply_q(message, "❌ لم أجد المستخدم.")
            return
        bot.send_message(target_user_id, f"📨 <b>رسالة من الإدارة</b>\n\n{esc(msg_text)}", parse_mode="HTML")
        reply_q(message, f"✅ تم الإرسال إلى {target_user_id}.")
    except Exception as e:
        reply_q(message, f"❌ فشل: {e}")

@bot.message_handler(func=lambda m: m.reply_to_message is not None and m.reply_to_message.message_id in question_messages, content_types=["text"])
def handle_reply_to_question(message):
    if not is_admin(message.from_user.id):
        reply_q(message, "❌ هذا الرد للأدمن فقط.")
        return
    user_id = question_messages.pop(message.reply_to_message.message_id, None)
    if not user_id:
        reply_q(message, "⚠️ لم أجد المستخدم.")
        return
    try:
        bot.send_message(user_id, f"📩 <b>رد الإدارة</b>\n\n{esc(message.text)}", parse_mode="HTML")
        reply_q(message, f"✅ تم إرسال الرد إلى {user_id}.")
    except Exception as e:
        reply_q(message, f"❌ فشل: {e}")

@bot.message_handler(commands=['stats', 'status'])
def cmd_stats(message):
    if not is_admin(message.from_user.id):
        reply_q(message, "❌ هذا الأمر للأدمن فقط.")
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
    stats_text = f"📊 إحصائيات النظام\n👥 المستخدمين: {total_users}\n📄 الملفات: {total_files}\n   - معلقة: {pending_files}\n   - شغالة: {running_files}\n   - معتمدة: {approved_files}\n💎 النقاط: {total_points}\n🛒 الطلبات: {total_orders}\n   - معلقة: {pending_orders}\n🔄 العمليات النشطة: {active_processes}"
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
