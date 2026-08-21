"""
Fast Thumbnail Bot (v2 — instant, no video download/upload)
-------------------------------------------------------------
راز سرعت: به‌جای دانلود کردن کل ویدیو از تلگرام و آپلود دوباره‌اش،
از همون file_id ویدیویی که کاربر فرستاده استفاده می‌کنیم. تلگرام در این
حالت ویدیو رو خودش سمت سرورهاش کپی می‌کنه (پهنای‌باند ربات درگیر نمی‌شه)
و ما فقط یه thumbnail کوچیک (حداکثر ۲۰۰ کیلوبایت) آپلود می‌کنیم.
برای همینه که چند ویدیو رو تو کسری از ثانیه جواب می‌ده.

نیازمندی‌ها:
    pip install python-telegram-bot==21.* pillow

اجرا:
    export BOT_TOKEN="توکن از BotFather"
    python bot.py
"""

import io
import json
import logging
import os
from pathlib import Path

from PIL import Image
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# تنظیمات پایه
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT-YOUR-TOKEN-HERE")

BASE_DIR = Path(__file__).parent
COVERS_DIR = BASE_DIR / "covers"        # عکس‌های کاور آماده‌شده (resize شده) هر کاربر
DATA_FILE = BASE_DIR / "users.json"     # تنظیمات هر کاربر

COVERS_DIR.mkdir(exist_ok=True)

# محدودیت‌های رسمی تلگرام برای thumbnail
THUMB_MAX_SIDE = 320          # پیکسل
THUMB_MAX_BYTES = 200 * 1024  # ۲۰۰ کیلوبایت

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ذخیره‌سازی ساده (JSON روی دیسک — برای پروژه‌ی واقعی از دیتابیس استفاده کنید)
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
# آماده‌سازی عکس کاور مطابق محدودیت‌های تلگرام (≤320px, ≤200KB, JPEG)
# ---------------------------------------------------------------------------

def prepare_thumbnail(raw_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")

    # resize تا هیچ ضلعی از ۳۲۰ پیکسل بیشتر نشه
    img.thumbnail((THUMB_MAX_SIDE, THUMB_MAX_SIDE), Image.LANCZOS)

    # کیفیت JPEG رو کم‌کم پایین می‌آریم تا زیر ۲۰۰ کیلوبایت بشه
    quality = 90
    while quality >= 30:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= THUMB_MAX_BYTES:
            return buf.getvalue()
        quality -= 10

    return buf.getvalue()  # حتی اگه هنوز بزرگه، بهترین حالت ممکن رو برمی‌گردونیم


# ---------------------------------------------------------------------------
# دستورات
# ---------------------------------------------------------------------------

WELCOME_TEXT = (
    "Hi {name}!\n\n"
    "🎬 <b>Fast Thumbnail Bot</b> خوش اومدی!\n\n"
    "- به ویدیوهات یه کاور دلخواه اضافه کن، آنی و بدون تأخیر!\n\n"
    "<b>نحوه‌ی کار:</b>\n"
    "1. عکس (کاور) رو بفرست.\n"
    "2. ویدیو رو بفرست؛ ربات خودش کاور رو روش می‌ذاره.\n\n"
    "<b>دستورات:</b>\n"
    "/settings - تنظیمات ربات\n"
    "/show_cover - دیدن کاور فعلی\n"
    "/del_cover - پاک کردن کاور ذخیره‌شده"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        WELCOME_TEXT.format(name=user.first_name),
        parse_mode=ParseMode.HTML,
    )


async def show_cover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    path = cover_path_for(update.effective_user.id)
    if path.exists():
        await update.message.reply_photo(photo=path.open("rb"), caption="کاور فعلی شما 👆")
    else:
        await update.message.reply_text("هنوز کاوری ذخیره نکردی. یه عکس بفرست تا ذخیره بشه.")


async def del_cover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    path = cover_path_for(user_id)
    data = load_data()
    user = get_user(data, user_id)

    if path.exists():
        path.unlink()
        user["has_cover"] = False
        save_data(data)
        await update.message.reply_text("کاور شما پاک شد. ✅")
    else:
        await update.message.reply_text("کاوری برای پاک کردن وجود نداره.")


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user = get_user(data, update.effective_user.id)
    status = "روشن ✅" if user.get("auto_apply", True) else "خاموش ❌"

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"اعمال خودکار کاور: {status}", callback_data="toggle_auto")]]
    )
    await update.message.reply_text("⚙️ تنظیمات ربات:", reply_markup=keyboard)


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = load_data()
    user = get_user(data, query.from_user.id)

    if query.data == "toggle_auto":
        user["auto_apply"] = not user.get("auto_apply", True)
        save_data(data)
        status = "روشن ✅" if user["auto_apply"] else "خاموش ❌"
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"اعمال خودکار کاور: {status}", callback_data="toggle_auto")]]
        )
        await query.edit_message_text("⚙️ تنظیمات ربات:", reply_markup=keyboard)


# ---------------------------------------------------------------------------
# دریافت عکس -> resize و ذخیره به‌عنوان کاور
# (فقط همین یک آپلود سنگین اتفاق می‌افته؛ چون خود عکس کوچیکه، سریعه)
# ---------------------------------------------------------------------------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    file = await photo.get_file()

    raw_bytes = bytes(await file.download_as_bytearray())
    thumb_bytes = prepare_thumbnail(raw_bytes)

    path = cover_path_for(user_id)
    path.write_bytes(thumb_bytes)

    data = load_data()
    user = get_user(data, user_id)
    user["has_cover"] = True
    save_data(data)

    await update.message.reply_text("✅ کاور ذخیره شد! حالا یه ویدیو بفرست.")


# ---------------------------------------------------------------------------
# دریافت ویدیو -> اعمال کاور بدون دانلود/آپلود ویدیو
# نکته‌ی کلیدی: video=file_id (reuse سمت سرور تلگرام)، فقط thumbnail آپلود می‌شه
# ---------------------------------------------------------------------------

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    data = load_data()
    user = get_user(data, user_id)

    cover_file = cover_path_for(user_id)
    if not cover_file.exists() or not user.get("auto_apply", True):
        await update.message.reply_text(
            "کاوری ثبت نشده یا اعمال خودکار خاموشه. اول یه عکس بفرست یا از /settings روشنش کن."
        )
        return

    video = update.message.video

    with open(cover_file, "rb") as thumb:
        await update.message.reply_video(
            video=video.file_id,          # <-- reuse؛ نه دانلود نه آپلود ویدیو
            thumbnail=thumb,              # <-- فقط این آپلود می‌شه (چند صد کیلوبایت)
            width=video.width,
            height=video.height,
            duration=video.duration,
            caption=update.message.caption,
            supports_streaming=True,
        )


# ---------------------------------------------------------------------------
# راه‌اندازی ربات
# ---------------------------------------------------------------------------

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("show_cover", show_cover))
    app.add_handler(CommandHandler("del_cover", del_cover))

    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^toggle_auto$"))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))

    logger.info("ربات در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
