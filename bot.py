#!/usr/bin/env python3
"""
TanyaHargaBot - Bot Telegram teman untuk menanyakan harga Gold (XAUUSD) di MT5
Fitur: harga aktual, tren, faktual, sinyal, isu/rumor
"""

import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests
import yfinance as yf
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

# ==================== KONFIGURASI ====================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN tidak ditemukan di .env")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==================== DATA SOURCE ====================
def get_gold_price_yf() -> Optional[Dict[str, Any]]:
    """Ambil harga XAUUSD dari Yahoo Finance (proxy untuk MT5)."""
    try:
        ticker = yf.Ticker("GC=F")  # Gold Futures
        info = ticker.info
        hist = ticker.history(period="5d", interval="1h")

        if hist.empty:
            # Fallback ke XAUUSD=X
            ticker = yf.Ticker("XAUUSD=X")
            hist = ticker.history(period="5d", interval="1h")
            info = ticker.info

        if hist.empty:
            return None

        last = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else last

        price = float(last["Close"])
        open_p = float(last["Open"])
        high = float(last["High"])
        low = float(last["Low"])
        change = price - float(prev["Close"])
        change_pct = (change / float(prev["Close"])) * 100 if prev["Close"] else 0

        # Tren sederhana berdasarkan MA
        closes = hist["Close"].tail(24)
        ma_short = closes.tail(6).mean()
        ma_long = closes.mean()
        trend = "NAIK 📈" if ma_short > ma_long else "TURUN 📉" if ma_short < ma_long else "SIDEWAYS ↔️"

        return {
            "price": round(price, 2),
            "open": round(open_p, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 3),
            "trend": trend,
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "source": "Yahoo Finance (GC=F / XAUUSD)",
        }
    except Exception as e:
        logger.error(f"Error yfinance: {e}")
        return None


def get_gold_price_metals() -> Optional[Dict[str, Any]]:
    """Fallback: ambil dari metals-api style atau free endpoint sederhana."""
    try:
        # Gunakan endpoint publik sederhana (bisa diganti dengan API key sendiri)
        url = "https://api.metals.live/v1/spot/gold"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                price = float(data[0].get("price", 0))
                return {
                    "price": round(price, 2),
                    "open": None,
                    "high": None,
                    "low": None,
                    "change": None,
                    "change_pct": None,
                    "trend": "N/A",
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "source": "metals.live",
                }
    except Exception as e:
        logger.error(f"Error metals.live: {e}")
    return None


def get_gold_data() -> Dict[str, Any]:
    """Ambil data harga gold terbaik yang tersedia."""
    data = get_gold_price_yf()
    if data:
        return data
    data = get_gold_price_metals()
    if data:
        return data
    return {
        "price": None,
        "error": "Gagal mengambil data harga. Coba lagi nanti.",
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def generate_signal(data: Dict[str, Any]) -> str:
    """Generate sinyal sederhana berdasarkan tren & perubahan harga."""
    if not data.get("price"):
        return "⚠️ Data tidak tersedia untuk sinyal."

    change = data.get("change_pct") or 0
    trend = data.get("trend", "")

    if "NAIK" in trend and change > 0.15:
        signal = "🟢 BUY / LONG"
        reason = "Tren naik + momentum positif. Pertimbangkan entry long dengan SL di bawah low terbaru."
    elif "TURUN" in trend and change < -0.15:
        signal = "🔴 SELL / SHORT"
        reason = "Tren turun + momentum negatif. Pertimbangkan entry short dengan SL di atas high terbaru."
    elif abs(change) < 0.05:
        signal = "🟡 WAIT / SIDEWAYS"
        reason = "Pergerakan sempit. Tunggu breakout atau konfirmasi arah."
    else:
        signal = "🟠 WATCH"
        reason = "Arah belum jelas. Pantau support/resistance terdekat."

    return f"**Sinyal:** {signal}\n{reason}"


def get_rumor_isu() -> str:
    """Placeholder isu/rumor. Bisa diganti dengan scraping news atau API berita."""
    # Contoh statis + bisa dikembangkan dengan news API
    issues = [
        "📌 Fed rate decision & statement bisa gerakkan harga gold secara signifikan.",
        "📌 Kekhawatiran inflasi & safe-haven demand masih mendukung emas.",
        "📌 Kekuatan USD (DXY) biasanya berkorelasi negatif dengan XAUUSD.",
        "📌 Geopolitik (konflik, pemilihan, dll) sering jadi katalis short-term.",
        "📌 Data Non-Farm Payroll (NFP) & CPI AS selalu diwaspadai trader gold.",
    ]
    import random
    selected = random.sample(issues, k=3)
    return "\n".join(selected)


# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (
        f"Halo {user.first_name or 'Trader'}! 👋\n\n"
        "Saya *TanyaHargaBot* — temanmu untuk pantau harga Gold (XAUUSD) ala MT5.\n\n"
        "Yang bisa saya bantu:\n"
        "• Harga aktual & faktual\n"
        "• Tren singkat\n"
        "• Sinyal sederhana\n"
        "• Isu / rumor pasar\n\n"
        "Ketik /menu atau pilih tombol di bawah."
    )
    keyboard = [
        [
            InlineKeyboardButton("💰 Harga Aktual", callback_data="harga"),
            InlineKeyboardButton("📈 Tren", callback_data="tren"),
        ],
        [
            InlineKeyboardButton("🎯 Sinyal", callback_data="sinyal"),
            InlineKeyboardButton("📰 Isu/Rumor", callback_data="isu"),
        ],
        [
            InlineKeyboardButton("📊 Ringkasan Lengkap", callback_data="full"),
        ],
    ]
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("💰 Harga Aktual", callback_data="harga"),
            InlineKeyboardButton("📈 Tren", callback_data="tren"),
        ],
        [
            InlineKeyboardButton("🎯 Sinyal", callback_data="sinyal"),
            InlineKeyboardButton("📰 Isu/Rumor", callback_data="isu"),
        ],
        [
            InlineKeyboardButton("📊 Ringkasan Lengkap", callback_data="full"),
        ],
    ]
    await update.message.reply_text(
        "Pilih yang ingin ditanyakan:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def harga_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Mengambil harga gold...")
    data = get_gold_data()
    if data.get("price") is None:
        await update.message.reply_text(data.get("error", "Gagal ambil data."))
        return

    msg = (
        f"*💰 Harga Gold (XAUUSD) Aktual*\n\n"
        f"Harga: *${data['price']:,.2f}*\n"
        f"Open: ${data.get('open') or '-'}\n"
        f"High: ${data.get('high') or '-'}\n"
        f"Low: ${data.get('low') or '-'}\n"
        f"Perubahan: {data.get('change', 0):+.2f} ({data.get('change_pct', 0):+.3f}%)\n"
        f"Waktu: {data['time']}\n"
        f"Sumber: {data.get('source', '-')}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def tren_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Menganalisis tren...")
    data = get_gold_data()
    if data.get("price") is None:
        await update.message.reply_text(data.get("error", "Gagal ambil data."))
        return

    msg = (
        f"*📈 Tren Gold (XAUUSD)*\n\n"
        f"Harga sekarang: *${data['price']:,.2f}*\n"
        f"Tren singkat: *{data.get('trend', 'N/A')}*\n"
        f"Perubahan: {data.get('change', 0):+.2f} ({data.get('change_pct', 0):+.3f}%)\n\n"
        f"_Analisis berdasarkan moving average periode pendek vs panjang._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def sinyal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Membuat sinyal...")
    data = get_gold_data()
    if data.get("price") is None:
        await update.message.reply_text(data.get("error", "Gagal ambil data."))
        return

    signal_text = generate_signal(data)
    msg = (
        f"*🎯 Sinyal Gold (XAUUSD)*\n\n"
        f"Harga: *${data['price']:,.2f}*\n"
        f"Tren: {data.get('trend', 'N/A')}\n\n"
        f"{signal_text}\n\n"
        f"⚠️ _Ini bukan saran finansial. Selalu gunakan risk management._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def isu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    isu = get_rumor_isu()
    msg = (
        f"*📰 Isu & Rumor yang Perlu Diperhatikan*\n\n"
        f"{isu}\n\n"
        f"_Update ini bersifat edukatif. Selalu cross-check dengan sumber berita resmi._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def full_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Menyusun ringkasan lengkap...")
    data = get_gold_data()
    if data.get("price") is None:
        await update.message.reply_text(data.get("error", "Gagal ambil data."))
        return

    signal_text = generate_signal(data)
    isu = get_rumor_isu()

    msg = (
        f"*📊 Ringkasan Lengkap Gold (XAUUSD)*\n\n"
        f"*Harga Aktual:* ${data['price']:,.2f}\n"
        f"Open: ${data.get('open') or '-'} | High: ${data.get('high') or '-'} | Low: ${data.get('low') or '-'}\n"
        f"Perubahan: {data.get('change', 0):+.2f} ({data.get('change_pct', 0):+.3f}%)\n"
        f"Tren: *{data.get('trend', 'N/A')}*\n"
        f"Waktu: {data['time']}\n\n"
        f"{signal_text}\n\n"
        f"*Isu/Rumor:*\n{isu}\n\n"
        f"Sumber data: {data.get('source', '-')}\n"
        f"⚠️ Bukan saran finansial."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data_key = query.data
    await query.edit_message_text("⏳ Memproses...")

    if data_key == "harga":
        data = get_gold_data()
        if data.get("price") is None:
            await query.edit_message_text(data.get("error", "Gagal ambil data."))
            return
        msg = (
            f"*💰 Harga Gold (XAUUSD) Aktual*\n\n"
            f"Harga: *${data['price']:,.2f}*\n"
            f"Open: ${data.get('open') or '-'}\n"
            f"High: ${data.get('high') or '-'}\n"
            f"Low: ${data.get('low') or '-'}\n"
            f"Perubahan: {data.get('change', 0):+.2f} ({data.get('change_pct', 0):+.3f}%)\n"
            f"Waktu: {data['time']}\n"
            f"Sumber: {data.get('source', '-')}"
        )
    elif data_key == "tren":
        data = get_gold_data()
        if data.get("price") is None:
            await query.edit_message_text(data.get("error", "Gagal ambil data."))
            return
        msg = (
            f"*📈 Tren Gold (XAUUSD)*\n\n"
            f"Harga sekarang: *${data['price']:,.2f}*\n"
            f"Tren singkat: *{data.get('trend', 'N/A')}*\n"
            f"Perubahan: {data.get('change', 0):+.2f} ({data.get('change_pct', 0):+.3f}%)\n\n"
            f"_Analisis berdasarkan moving average periode pendek vs panjang._"
        )
    elif data_key == "sinyal":
        data = get_gold_data()
        if data.get("price") is None:
            await query.edit_message_text(data.get("error", "Gagal ambil data."))
            return
        signal_text = generate_signal(data)
        msg = (
            f"*🎯 Sinyal Gold (XAUUSD)*\n\n"
            f"Harga: *${data['price']:,.2f}*\n"
            f"Tren: {data.get('trend', 'N/A')}\n\n"
            f"{signal_text}\n\n"
            f"⚠️ _Ini bukan saran finansial. Selalu gunakan risk management._"
        )
    elif data_key == "isu":
        isu = get_rumor_isu()
        msg = (
            f"*📰 Isu & Rumor yang Perlu Diperhatikan*\n\n"
            f"{isu}\n\n"
            f"_Update ini bersifat edukatif. Selalu cross-check dengan sumber berita resmi._"
        )
    elif data_key == "full":
        data = get_gold_data()
        if data.get("price") is None:
            await query.edit_message_text(data.get("error", "Gagal ambil data."))
            return
        signal_text = generate_signal(data)
        isu = get_rumor_isu()
        msg = (
            f"*📊 Ringkasan Lengkap Gold (XAUUSD)*\n\n"
            f"*Harga Aktual:* ${data['price']:,.2f}\n"
            f"Open: ${data.get('open') or '-'} | High: ${data.get('high') or '-'} | Low: ${data.get('low') or '-'}\n"
            f"Perubahan: {data.get('change', 0):+.2f} ({data.get('change_pct', 0):+.3f}%)\n"
            f"Tren: *{data.get('trend', 'N/A')}*\n"
            f"Waktu: {data['time']}\n\n"
            f"{signal_text}\n\n"
            f"*Isu/Rumor:*\n{isu}\n\n"
            f"Sumber data: {data.get('source', '-')}\n"
            f"⚠️ Bukan saran finansial."
        )
    else:
        msg = "Perintah tidak dikenali."

    await query.edit_message_text(msg, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*Perintah yang tersedia:*\n\n"
        "/start - Mulai bot\n"
        "/menu - Tampilkan menu tombol\n"
        "/harga - Harga aktual gold\n"
        "/tren - Analisis tren singkat\n"
        "/sinyal - Sinyal sederhana\n"
        "/isu - Isu & rumor pasar\n"
        "/full - Ringkasan lengkap\n"
        "/help - Bantuan ini\n\n"
        "Bot ini menggunakan data publik (Yahoo Finance) sebagai proxy harga XAUUSD yang mirip dengan yang terlihat di MT5.\n"
        "Untuk data real-time langsung dari broker MT5, kamu bisa integrasikan MetaTrader5 Python package (perlu terminal MT5 terpasang)."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Balas pesan teks bebas dengan deteksi kata kunci sederhana."""
    text = (update.message.text or "").lower()
    if any(k in text for k in ["harga", "price", "berapa", "aktual"]):
        await harga_cmd(update, context)
    elif any(k in text for k in ["tren", "trend", "arah"]):
        await tren_cmd(update, context)
    elif any(k in text for k in ["sinyal", "signal", "entry"]):
        await sinyal_cmd(update, context)
    elif any(k in text for k in ["isu", "rumor", "berita", "news"]):
        await isu_cmd(update, context)
    elif any(k in text for k in ["full", "lengkap", "ringkas"]):
        await full_cmd(update, context)
    else:
        await update.message.reply_text(
            "Ketik /menu atau salah satu perintah: /harga /tren /sinyal /isu /full"
        )


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("harga", harga_cmd))
    app.add_handler(CommandHandler("tren", tren_cmd))
    app.add_handler(CommandHandler("sinyal", sinyal_cmd))
    app.add_handler(CommandHandler("isu", isu_cmd))
    app.add_handler(CommandHandler("full", full_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("TanyaHargaBot mulai berjalan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
