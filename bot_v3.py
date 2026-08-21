"""
Fast Thumbnail Bot (v3 — Pyrogram / raw MTProto)
---------------------------------------------------
این نسخه دقیقاً همون تکنیکیه که ربات‌هایی مثل VideosCoverBot استفاده می‌کنن:

- به‌جای Bot API معمولی (HTTP)، مستقیم از MTProto خام (Pyrogram) استفاده می‌کنیم.
- چون از لایه‌ی HTTP رسمی رد نمی‌شیم، اون heuristic تلگرام که thumbnail
  سفارشی رو برای ویدیوهای کوچیک نادیده می‌گیره، اینجا اعمال نمی‌شه.
- ویدیو با file_id از سرور تلگرام reuse می‌شه (بدون دانلود/آپلود کامل).
- فقط thumbnail (حداکثر ۲۰۰ کیلوبایت) آپلود می‌شه.

نیازمندی‌ها:
    pip install pyrogram tgcrypto pillow

برای اجرا سه تا چیز لازم داری:
    1) BOT_TOKEN از @BotFather
    2) API_ID و API_HASH از my.telegram.org (رایگان، با اکانت تلگرام خودت بساز)

اجرا:
    export API_ID="1234567"
    export API_HASH="abcdef1234567890abcdef1234567890"
    export BOT_TOKEN="123456789:AAExampleTokenHere"
    python bot_v3.py
"""

import io
import json
import logging
import os
from pathlib import Path

from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message

# ---------------------------------------------------------------------------
# تنظیمات پایه — این سه‌تا رو حتماً باید پر کنی
# ---------------------------------------------------------------------------

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

BASE_DIR = Path(__file__).parent
COVERS_DIR = BASE_DIR / "covers"
DATA_FILE = BASE_DIR / "users.json"

COVERS_DIR.mkdir(exist_ok=True)

THUMB_MAX_SIDE = 320
THUMB_MAX_BYTES = 200 * 1024

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ذخیره‌سازی ساده (JSON — برای پروژه‌ی واقعی از دیتابیس واقعی استفاده کن)
# ---------------------------------------------------------------------------

def load_data() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {}


def save_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_user(data: dict, user_id: int) -> dict:
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"has_cover": False, "auto_apply": True}
    return data[uid]


def cover_path_for(user_id: int) -> Path:
    return COVERS_DIR / f"{user_id}.jpg"


# ---------------------------------------------------------------------------
# آماده‌سازی thumbnail طبق محدودیت‌های تلگرام
# ---------------------------------------------------------------------------

def prepare_thumbnail(raw_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.thumbnail((THUMB_MAX_SIDE, THUMB_MAX_SIDE), Image.LANCZOS)

    quality = 90
    buf = io.BytesIO()
    while quality >= 30:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= THUMB_MAX_BYTES:
            break
        quality -= 10

    return buf.getvalue()


# ---------------------------------------------------------------------------
# راه‌اندازی کلاینت Pyrogram
# ---------------------------------------------------------------------------

app = Client(
    "fast_thumbnail_bot",   # اسم فایل سشن (خودکار ساخته می‌شه: fast_thumbnail_bot.session)
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


WELCOME_TEXT = (
    "Hi {name}!\n\n"
    "🎬 **Fast Thumbnail Bot** خوش اومدی!\n\n"
    "- به ویدیوهات یه کاور دلخواه اضافه کن، آنی!\n\n"
    "**نحوه‌ی کار:**\n"
    "1. عکس (کاور) رو بفرست.\n"
    "2. ویدیو رو بفرست؛ ربات خودش کاور رو روش می‌ذاره.\n\n"
    "**دستورات:**\n"
    "/settings - تنظیمات ربات\n"
    "/show_cover - دیدن کاور فعلی\n"
    "/del_cover - پاک کردن کاور ذخیره‌شده"
)


@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    await message.reply_text(WELCOME_TEXT.format(name=message.from_user.first_name))


@app.on_message(filters.command("show_cover"))
async def show_cover(client: Client, message: Message):
    path = cover_path_for(message.from_user.id)
    if path.exists():
        await message.reply_photo(str(path), caption="کاور فعلی شما 👆")
    else:
        await message.reply_text("هنوز کاوری ذخیره نکردی. یه عکس بفرست تا ذخیره بشه.")


@app.on_message(filters.command("del_cover"))
async def del_cover(client: Client, message: Message):
    user_id = message.from_user.id
    path = cover_path_for(user_id)
    data = load_data()
    user = get_user(data, user_id)

    if path.exists():
        path.unlink()
        user["has_cover"] = False
        save_data(data)
        await message.reply_text("کاور شما پاک شد. ✅")
    else:
        await message.reply_text("کاوری برای پاک کردن وجود نداره.")


@app.on_message(filters.command("settings"))
async def settings_cmd(client: Client, message: Message):
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    data = load_data()
    user = get_user(data, message.from_user.id)
    status = "روشن ✅" if user.get("auto_apply", True) else "خاموش ❌"

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"اعمال خودکار کاور: {status}", callback_data="toggle_auto")]]
    )
    await message.reply_text("⚙️ تنظیمات ربات:", reply_markup=keyboard)


@app.on_callback_query(filters.regex("^toggle_auto$"))
async def settings_callback(client: Client, callback_query):
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    data = load_data()
    user = get_user(data, callback_query.from_user.id)
    user["auto_apply"] = not user.get("auto_apply", True)
    save_data(data)

    status = "روشن ✅" if user["auto_apply"] else "خاموش ❌"
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"اعمال خودکار کاور: {status}", callback_data="toggle_auto")]]
    )
    await callback_query.edit_message_text("⚙️ تنظیمات ربات:", reply_markup=keyboard)
    await callback_query.answer()


# ---------------------------------------------------------------------------
# دریافت عکس -> resize و ذخیره
# ---------------------------------------------------------------------------

@app.on_message(filters.photo)
async def handle_photo(client: Client, message: Message):
    user_id = message.from_user.id

    raw_bytes = await client.download_media(message.photo.file_id, in_memory=True)
    thumb_bytes = prepare_thumbnail(raw_bytes.getvalue())

    path = cover_path_for(user_id)
    path.write_bytes(thumb_bytes)

    data = load_data()
    user = get_user(data, user_id)
    user["has_cover"] = True
    save_data(data)

    await message.reply_text("✅ کاور ذخیره شد! حالا یه ویدیو بفرست.")


# ---------------------------------------------------------------------------
# دریافت ویدیو -> اعمال کاور، آنی، بدون دانلود/آپلود ویدیو
# ---------------------------------------------------------------------------

@app.on_message(filters.video)
async def handle_video(client: Client, message: Message):
    user_id = message.from_user.id
    data = load_data()
    user = get_user(data, user_id)

    cover_file = cover_path_for(user_id)
    if not cover_file.exists() or not user.get("auto_apply", True):
        await message.reply_text(
            "کاوری ثبت نشده یا اعمال خودکار خاموشه. اول یه عکس بفرست یا از /settings روشنش کن."
        )
        return

    video = message.video

    # نکته‌ی کلیدی: video=file_id یعنی reuse (بدون دانلود/آپلود)
    # thumb=مسیر فایل لوکال یعنی فقط همین آپلود می‌شه (سریع، چون کوچیکه)
    await message.reply_video(
        video=video.file_id,
        thumb=str(cover_file),
        width=video.width,
        height=video.height,
        duration=video.duration,
        caption=message.caption,
        supports_streaming=True,
    )


# ---------------------------------------------------------------------------
# اجرا
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("ربات در حال اجراست...")
    app.run()
