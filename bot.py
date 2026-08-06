# bot.py
# @tanyahargabot – XAUUSD Genesis Dashboard Bot
# Format 100% sesuai spesifikasi (tanpa $, tanpa koma, Neto ▲/▼)

from __future__ import annotations
import logging
import os
import sys
from pathlib import Path

# pastikan services/ bisa di-import
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ── Load .env otomatis (sebelum baca TOKEN) ──
def _load_dotenv():
    """Muat file .env di folder yang sama dengan bot.py (tanpa dependency ekstra)."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:  # jangan overwrite env yang sudah ada
                    os.environ[key] = value
    except Exception as e:
        print(f"[WARN] Gagal baca .env: {e}")

_load_dotenv()

# Coba juga python-dotenv jika terinstall (lebih robust)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from mt5_helper import get_gold_data, get_account_info
from services.signal_engine import (
    analisis_gt,
    buat_sinyal_pintar,
    format_gt_table,
    format_harga,
    format_sinyal,
    format_arus,
    format_puncak_lembah,
    format_full,
    format_tren,
    _n, _pts, _neto, _h,
)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Keyboard utama
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["💰 Harga", "📊 GT"],
        ["📈 Sinyal", "🌊 Arus"],
        ["🏔 Puncak/Lembah", "📋 Full"],
        ["📉 Tren", "⚙️ Status"],
    ],
    resize_keyboard=True,
)


# ─────────────────────────────────────────────
# HELPER KIRIM PESAN
# ─────────────────────────────────────────────
async def kirim(update: Update, text: str, reply_markup=None):
    """Kirim pesan HTML aman"""
    try:
        if update.callback_query:
            await update.callback_query.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup or MAIN_KEYBOARD,
                disable_web_page_preview=True,
            )
            await update.callback_query.answer()
        else:
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup or MAIN_KEYBOARD,
                disable_web_page_preview=True,
            )
    except Exception as e:
        logger.error(f"kirim error: {e}")
        # fallback plain text
        plain = text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", "")
        if update.message:
            await update.message.reply_text(plain, reply_markup=MAIN_KEYBOARD)


def ambil_analisis() -> dict:
    """Ambil data + analisis GT siap pakai"""
    raw = get_gold_data()
    return analisis_gt(raw)


# ─────────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await kirim(
        update,
        "<b>@tanyahargabot</b>\n"
        "Genesis XAUUSD Dashboard\n\n"
        "Pilih menu di bawah:",
    )


async def cmd_harga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    analisis = ambil_analisis()
    await kirim(update, format_harga(analisis))


async def cmd_gt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    analisis = ambil_analisis()
    await kirim(update, format_gt_table(analisis))


async def cmd_sinyal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    analisis = ambil_analisis()
    await kirim(update, format_sinyal(analisis))


async def cmd_arus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    analisis = ambil_analisis()
    await kirim(update, format_arus(analisis))


async def cmd_puncak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    analisis = ambil_analisis()
    await kirim(update, format_puncak_lembah(analisis))


async def cmd_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    analisis = ambil_analisis()
    await kirim(update, format_full(analisis))


async def cmd_tren(update: Update, context: ContextTypes.DEFAULT_TYPE):
    analisis = ambil_analisis()
    await kirim(update, format_tren(analisis))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = get_gold_data()
    acc = get_account_info()
    source = raw.get("source", "—")
    lines = [
        "<b>Status Bot</b>",
        f"Sumber data : {_h(source)}",
        f"Waktu       : {_h(raw.get('waktu') or raw.get('time') or '—')}",
        f"Bid         : {_n(raw.get('bid'))}",
    ]
    if acc:
        lines += [
            "",
            f"Balance     : {_n(acc.get('balance'))}",
            f"Equity      : {_n(acc.get('equity'))}",
            f"Free Margin : {_n(acc.get('free_margin'))}",
        ]
    await kirim(update, "\n".join(lines))


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Router untuk ReplyKeyboard"""
    text = (update.message.text or "").strip()

    mapping = {
        "💰 Harga": cmd_harga,
        "📊 GT": cmd_gt,
        "📈 Sinyal": cmd_sinyal,
        "🌊 Arus": cmd_arus,
        "🏔 Puncak/Lembah": cmd_puncak,
        "📋 Full": cmd_full,
        "📉 Tren": cmd_tren,
        "⚙️ Status": cmd_status,
        # alias tanpa emoji
        "Harga": cmd_harga,
        "GT": cmd_gt,
        "Sinyal": cmd_sinyal,
        "Arus": cmd_arus,
        "Puncak/Lembah": cmd_puncak,
        "Full": cmd_full,
        "Tren": cmd_tren,
        "Status": cmd_status,
    }

    handler = mapping.get(text)
    if handler:
        await handler(update, context)
    else:
        await kirim(update, "Pilih menu dari keyboard di bawah ya.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}", exc_info=context.error)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    if not TOKEN:
        print("=" * 50)
        print("❌ TELEGRAM_BOT_TOKEN tidak ditemukan!")
        print()
        print("Pastikan file .env ada di folder yang sama dengan bot.py")
        print("Isi .env contoh:")
        print()
        print("  TELEGRAM_BOT_TOKEN=123456:ABC-DEF...")
        print()
        print("Atau set environment variable:")
        print("  set TELEGRAM_BOT_TOKEN=123456:ABC-DEF...   (Windows)")
        print("  export TELEGRAM_BOT_TOKEN=123456:ABC-DEF... (Linux/Mac)")
        print("=" * 50)
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("harga", cmd_harga))
    app.add_handler(CommandHandler("gt", cmd_gt))
    app.add_handler(CommandHandler("sinyal", cmd_sinyal))
    app.add_handler(CommandHandler("arus", cmd_arus))
    app.add_handler(CommandHandler("puncak", cmd_puncak))
    app.add_handler(CommandHandler("full", cmd_full))
    app.add_handler(CommandHandler("tren", cmd_tren))
    app.add_handler(CommandHandler("status", cmd_status))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_error_handler(error_handler)

    logger.info("Bot @tanyahargabot starting…")
    print("✅ Token ditemukan. Bot sedang berjalan...")
    print("   Tekan Ctrl+C untuk menghentikan.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
