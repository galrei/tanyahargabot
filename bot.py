#!/usr/bin/env python3
"""
TanyaHargaBot - Teman trader gold (XAUUSD) di MT5
Menu lengkap: harga aktual, tren, sinyal, support/resistance, isu/rumor, ringkasan
"""

import os
import sys
import logging
import asyncio
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests
import yfinance as yf
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

try:
    from mt5_helper import get_harga_lengkap, baca_genesis, get_mt5_price
except ImportError:
    get_harga_lengkap = None
    baca_genesis = None
    get_mt5_price = None

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN tidak ditemukan di .env")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ==================== KEYBOARD MENU ====================
def menu_utama() -> ReplyKeyboardMarkup:
    """Keyboard tetap di bawah chat."""
    keyboard = [
        [KeyboardButton("💰 Harga Aktual"), KeyboardButton("🏦 MT5 / Genesis")],
        [KeyboardButton("📈 Tren"), KeyboardButton("🎯 Sinyal")],
        [KeyboardButton("📊 Support / Resistance"), KeyboardButton("📰 Isu & Rumor")],
        [KeyboardButton("📋 Ringkasan Lengkap"), KeyboardButton("❓ Bantuan")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def tombol_aksi() -> InlineKeyboardMarkup:
    """Tombol cepat setelah melihat hasil."""
    keyboard = [
        [
            InlineKeyboardButton("💰 Harga", callback_data="harga"),
            InlineKeyboardButton("🏦 MT5/Genesis", callback_data="mt5"),
        ],
        [
            InlineKeyboardButton("📈 Tren", callback_data="tren"),
            InlineKeyboardButton("🎯 Sinyal", callback_data="sinyal"),
        ],
        [
            InlineKeyboardButton("📊 S/R", callback_data="sr"),
            InlineKeyboardButton("📰 Isu", callback_data="isu"),
        ],
        [
            InlineKeyboardButton("📋 Lengkap", callback_data="full"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== DATA HARGA ====================
def get_gold_data() -> Dict[str, Any]:
    """
    Prioritas:
    1. Genesis EA / MT5 (faktual broker)
    2. Yahoo Finance (fallback)
    """
    # Coba MT5 / Genesis dulu
    if get_harga_lengkap:
        try:
            mt5d = get_harga_lengkap("XAUUSD")
            if mt5d and mt5d.get("price"):
                price = mt5d["price"]
                open_p = mt5d.get("open") or mt5d.get("awal")
                high = mt5d.get("high") or mt5d.get("tinggi")
                low = mt5d.get("low") or mt5d.get("bawah")
                change = mt5d.get("neto")
                change_pct = None
                if change is not None and open_p:
                    change_pct = round((change / open_p) * 100, 3)

                # Tren sederhana dari neto
                if change is not None:
                    if change > 0.5:
                        trend, trend_desc = "NAIK 📈", "Neto positif"
                    elif change < -0.5:
                        trend, trend_desc = "TURUN 📉", "Neto negatif"
                    else:
                        trend, trend_desc = "SIDEWAYS ↔️", "Neto sempit"
                else:
                    trend, trend_desc = "N/A", "Data tren terbatas"

                return {
                    "price": price,
                    "open": open_p,
                    "high": high,
                    "low": low,
                    "change": change,
                    "change_pct": change_pct,
                    "trend": trend,
                    "trend_desc": trend_desc,
                    "support": mt5d.get("support") or low,
                    "resistance": mt5d.get("resistance") or high,
                    "mid": mt5d.get("inti"),
                    "bid": mt5d.get("bid"),
                    "ask": mt5d.get("ask"),
                    "spread": mt5d.get("spread"),
                    "neto": mt5d.get("neto"),
                    "inti": mt5d.get("inti"),
                    "jangkauan": mt5d.get("jangkauan"),
                    "tinggi": mt5d.get("tinggi") or high,
                    "bawah": mt5d.get("bawah") or low,
                    "awal": mt5d.get("awal") or open_p,
                    "time": mt5d.get("time", datetime.now().strftime("%d/%m/%Y %H:%M")),
                    "source": mt5d.get("source", "MT5/Genesis"),
                    "raw": mt5d.get("raw"),
                    "from_mt5": True,
                }
        except Exception as e:
            logger.warning(f"MT5/Genesis gagal, fallback Yahoo: {e}")

    # Fallback Yahoo Finance
    try:
        ticker = yf.Ticker("GC=F")
        hist = ticker.history(period="10d", interval="1h")

        if hist.empty:
            ticker = yf.Ticker("XAUUSD=X")
            hist = ticker.history(period="10d", interval="1h")

        if hist.empty:
            return {"error": "Gagal mengambil data harga. Coba lagi sebentar."}

        last = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else last

        price = float(last["Close"])
        open_p = float(last["Open"])
        high = float(last["High"])
        low = float(last["Low"])
        change = price - float(prev["Close"])
        change_pct = (change / float(prev["Close"])) * 100 if prev["Close"] else 0

        closes = hist["Close"].tail(48)
        ma_fast = closes.tail(8).mean()
        ma_slow = closes.mean()
        if ma_fast > ma_slow * 1.0005:
            trend, trend_desc = "NAIK 📈", "Bullish — harga di atas MA"
        elif ma_fast < ma_slow * 0.9995:
            trend, trend_desc = "TURUN 📉", "Bearish — harga di bawah MA"
        else:
            trend, trend_desc = "SIDEWAYS ↔️", "Konsolidasi — arah belum jelas"

        recent = hist.tail(48)
        resistance = float(recent["High"].max())
        support = float(recent["Low"].min())
        mid = (resistance + support) / 2

        return {
            "price": round(price, 2),
            "open": round(open_p, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 3),
            "trend": trend,
            "trend_desc": trend_desc,
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "mid": round(mid, 2),
            "neto": round(change, 2),
            "inti": round(mid, 2),
            "jangkauan": round(high - low, 2),
            "tinggi": round(high, 2),
            "bawah": round(low, 2),
            "awal": round(open_p, 2),
            "time": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
            "source": "Yahoo Finance (GC=F)",
            "from_mt5": False,
        }
    except Exception as e:
        logger.error(f"Error ambil data: {e}")
        return {"error": f"Gagal mengambil data: {e}"}


def buat_sinyal(data: Dict[str, Any]) -> str:
    if data.get("error") or not data.get("price"):
        return "⚠️ Data tidak tersedia."

    change = data.get("change_pct") or 0
    trend = data.get("trend", "")
    price = data["price"]
    support = data.get("support", 0)
    resistance = data.get("resistance", 0)

    jarak_sup = ((price - support) / price) * 100 if price else 0
    jarak_res = ((resistance - price) / price) * 100 if price else 0

    if "NAIK" in trend and change > 0.1:
        sinyal = "🟢 BUY / LONG"
        alasan = (
            f"Tren naik + momentum positif.\n"
            f"• Entry sekitar: ${price:,.2f}\n"
            f"• SL ide: di bawah support ${support:,.2f}\n"
            f"• TP ide: dekat resistance ${resistance:,.2f}"
        )
    elif "TURUN" in trend and change < -0.1:
        sinyal = "🔴 SELL / SHORT"
        alasan = (
            f"Tren turun + momentum negatif.\n"
            f"• Entry sekitar: ${price:,.2f}\n"
            f"• SL ide: di atas resistance ${resistance:,.2f}\n"
            f"• TP ide: dekat support ${support:,.2f}"
        )
    elif jarak_sup < 0.15:
        sinyal = "🟡 WATCH SUPPORT"
        alasan = "Harga dekat support. Pantau apakah hold atau break."
    elif jarak_res < 0.15:
        sinyal = "🟡 WATCH RESISTANCE"
        alasan = "Harga dekat resistance. Pantau apakah reject atau breakout."
    else:
        sinyal = "🟠 WAIT / SIDEWAYS"
        alasan = "Arah belum jelas. Tunggu breakout atau konfirmasi lebih kuat."

    return f"**Sinyal:** {sinyal}\n\n{alasan}"


def get_isu() -> str:
    daftar = [
        "📌 Keputusan suku bunga The Fed & statement-nya sangat mempengaruhi gold.",
        "📌 Data CPI & Non-Farm Payroll (NFP) AS rutin digarap trader gold.",
        "📌 Kekuatan Dolar (DXY) biasanya berkorelasi negatif dengan XAUUSD.",
        "📌 Ketegangan geopolitik sering memicu demand safe-haven ke emas.",
        "📌 Ekspektasi inflasi & yield obligasi AS memengaruhi harga gold.",
        "📌 Posisi besar di COMEX / CFTC bisa jadi sinyal arah jangka menengah.",
        "📌 Kalender high-impact (FOMC, CPI, NFP) sebaiknya dihindari trading agresif.",
    ]
    terpilih = random.sample(daftar, k=4)
    return "\n\n".join(terpilih)


# ==================== FORMAT PESAN ====================
def format_harga(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    change = data.get("change")
    change_pct = data.get("change_pct")
    if change is not None:
        tanda = "🟢" if change >= 0 else "🔴"
        change_str = f"{tanda} {change:+.2f}"
        if change_pct is not None:
            change_str += f" ({change_pct:+.3f}%)"
    else:
        change_str = "-"

    lines = [
        "💰 *Harga Gold (XAUUSD)*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Harga sekarang : *${data['price']:,.2f}*",
    ]
    if data.get("open") is not None:
        lines.append(f"Open           : ${data['open']:,.2f}")
    if data.get("high") is not None:
        lines.append(f"High           : ${data['high']:,.2f}")
    if data.get("low") is not None:
        lines.append(f"Low            : ${data['low']:,.2f}")
    lines.append(f"Perubahan      : {change_str}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🕐 {data.get('time', '-')}")
    lines.append(f"📡 {data.get('source', '-')}")
    return "\n".join(lines)


def format_mt5_genesis(data: Dict[str, Any]) -> str:
    """Tampilkan data faktual lengkap ala Genesis EA."""
    if data.get("error"):
        return f"❌ {data['error']}"

    if not data.get("from_mt5") and not data.get("raw"):
        # Coba ambil ulang khusus MT5
        if get_harga_lengkap:
            mt5d = get_harga_lengkap("XAUUSD")
            if mt5d and mt5d.get("price"):
                data = {**data, **mt5d, "from_mt5": True}
            else:
                return (
                    "🏦 *MT5 / Genesis*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "❌ Belum terhubung ke MT5 atau file Genesis.\n\n"
                    "*Cara mengaktifkan:*\n"
                    "1. Pastikan MetaTrader 5 terbuka & login\n"
                    "2. Install: `pip install MetaTrader5`\n"
                    "3. Atau letakkan file `genesis_data.json` dari EA Genesis\n"
                    "   di folder bot / MQL5/Files/\n\n"
                    "Sementara bot memakai Yahoo Finance."
                )

    def f(v):
        if v is None:
            return "-"
        try:
            return f"${float(v):,.2f}"
        except Exception:
            return str(v)

    lines = [
        "🏦 *Data Faktual MT5 / Genesis*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Simbol     : {data.get('symbol', 'XAUUSD')}",
        f"Harga      : *{f(data.get('price'))}*",
    ]
    if data.get("bid") is not None:
        lines.append(f"Bid        : {f(data.get('bid'))}")
    if data.get("ask") is not None:
        lines.append(f"Ask        : {f(data.get('ask'))}")
    if data.get("spread") is not None:
        lines.append(f"Spread     : {data.get('spread')}")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("*Riwayat Angka Faktual*")
    lines.append(f"Awal       : {f(data.get('awal') or data.get('open'))}")
    lines.append(f"Tinggi     : {f(data.get('tinggi') or data.get('high'))}")
    lines.append(f"Bawah      : {f(data.get('bawah') or data.get('low'))}")
    lines.append(f"Neto       : {f(data.get('neto') or data.get('change'))}")
    lines.append(f"Inti       : {f(data.get('inti') or data.get('mid'))}")
    lines.append(f"Jangkauan  : {f(data.get('jangkauan'))}")

    # Field tambahan dari raw Genesis
    raw = data.get("raw") or {}
    skip = {
        "symbol", "time", "waktu", "bid", "ask", "price", "open", "high", "low",
        "close", "neto", "inti", "jangkauan", "tinggi", "bawah", "awal", "rendah",
        "_source", "_file", "source",
    }
    extra = []
    for k, v in raw.items():
        if k.lower() in skip or k.startswith("_"):
            continue
        extra.append(f"{k.capitalize():12}: {v}")
    if extra:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("*Info tambahan Genesis*")
        lines.extend(extra[:12])  # batasi biar tidak kepanjangan

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🕐 {data.get('time', '-')}")
    lines.append(f"📡 {data.get('source', 'MT5/Genesis')}")
    return "\n".join(lines)


def format_tren(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    return (
        f"📈 *Analisis Tren Gold*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga   : *${data['price']:,.2f}*\n"
        f"Tren    : *{data['trend']}*\n"
        f"Keterangan : {data['trend_desc']}\n"
        f"Perubahan  : {data['change']:+.2f} ({data['change_pct']:+.3f}%)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Berdasarkan Moving Average periode pendek vs panjang._"
    )


def format_sinyal(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    sinyal_text = buat_sinyal(data)
    return (
        f"🎯 *Sinyal Trading Gold*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga : *${data['price']:,.2f}*\n"
        f"Tren  : {data['trend']}\n\n"
        f"{sinyal_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ _Bukan saran finansial. Gunakan risk management._"
    )


def format_sr(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    price = data["price"]
    sup = data["support"]
    res = data["resistance"]
    mid = data["mid"]
    return (
        f"📊 *Support & Resistance*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga sekarang : *${price:,.2f}*\n\n"
        f"🔴 Resistance  : *${res:,.2f}*\n"
        f"   Jarak       : {((res - price) / price * 100):+.2f}%\n\n"
        f"⚪ Midpoint    : ${mid:,.2f}\n\n"
        f"🟢 Support     : *${sup:,.2f}*\n"
        f"   Jarak       : {((price - sup) / price * 100):+.2f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Dihitung dari high/low 48 candle terakhir._"
    )


def format_isu() -> str:
    return (
        f"📰 *Isu & Rumor yang Perlu Diperhatikan*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{get_isu()}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Selalu cross-check dengan sumber berita resmi._"
    )


def format_full(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    sinyal_text = buat_sinyal(data)
    return (
        f"📋 *Ringkasan Lengkap Gold (XAUUSD)*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Harga  : *${data['price']:,.2f}*\n"
        f"   Open   : ${data['open']:,.2f}\n"
        f"   High   : ${data['high']:,.2f}\n"
        f"   Low    : ${data['low']:,.2f}\n"
        f"   Change : {data['change']:+.2f} ({data['change_pct']:+.3f}%)\n\n"
        f"📈 Tren   : *{data['trend']}*\n"
        f"   {data['trend_desc']}\n\n"
        f"📊 S/R\n"
        f"   Resistance : ${data['resistance']:,.2f}\n"
        f"   Support    : ${data['support']:,.2f}\n\n"
        f"{sinyal_text}\n\n"
        f"🕐 {data['time']}\n"
        f"⚠️ Bukan saran finansial."
    )


# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    nama = user.first_name or "Trader"
    text = (
        f"Halo *{nama}*! 👋\n\n"
        f"Saya *TanyaHargaBot* — temanmu untuk pantau harga *Gold (XAUUSD)*.\n\n"
        f"Pilih menu di bawah:\n"
        f"• 💰 Harga Aktual\n"
        f"• 🏦 MT5 / Genesis (data faktual broker + EA)\n"
        f"• 📈 Tren\n"
        f"• 🎯 Sinyal\n"
        f"• 📊 Support / Resistance\n"
        f"• 📰 Isu & Rumor\n"
        f"• 📋 Ringkasan Lengkap\n\n"
        f"Semoga trading-mu cuan 🙏"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=menu_utama(),
    )


async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "❓ *Bantuan TanyaHargaBot*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Menu yang tersedia:*\n"
        "💰 *Harga Aktual* — Harga live + OHLC\n"
        "📈 *Tren* — Arah pasar (bullish/bearish/sideways)\n"
        "🎯 *Sinyal* — Ide entry sederhana + SL/TP\n"
        "📊 *Support / Resistance* — Level penting\n"
        "📰 *Isu & Rumor* — Faktor yang sering gerakkan harga\n"
        "📋 *Ringkasan Lengkap* — Semua info sekaligus\n\n"
        "*Perintah teks:*\n"
        "`/start` `/harga` `/tren` `/sinyal` `/sr` `/isu` `/full` `/help`\n\n"
        "Data dari Yahoo Finance (mendekati harga MT5).\n"
        "⚠️ Bukan saran finansial. Selalu pakai risk management."
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=menu_utama(),
    )


async def kirim_harga(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Mengambil harga gold...")
    data = get_gold_data()
    await msg.edit_text(
        format_harga(data),
        parse_mode="Markdown",
        reply_markup=tombol_aksi(),
    )


async def kirim_tren(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menganalisis tren...")
    data = get_gold_data()
    await msg.edit_text(
        format_tren(data),
        parse_mode="Markdown",
        reply_markup=tombol_aksi(),
    )


async def kirim_sinyal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menyusun sinyal...")
    data = get_gold_data()
    await msg.edit_text(
        format_sinyal(data),
        parse_mode="Markdown",
        reply_markup=tombol_aksi(),
    )


async def kirim_sr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menghitung Support & Resistance...")
    data = get_gold_data()
    await msg.edit_text(
        format_sr(data),
        parse_mode="Markdown",
        reply_markup=tombol_aksi(),
    )


async def kirim_isu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        format_isu(),
        parse_mode="Markdown",
        reply_markup=tombol_aksi(),
    )


async def kirim_full(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menyusun ringkasan lengkap...")
    data = get_gold_data()
    await msg.edit_text(
        format_full(data),
        parse_mode="Markdown",
        reply_markup=tombol_aksi(),
    )


async def kirim_mt5(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Mengambil data MT5 / Genesis...")
    data = get_gold_data()
    await msg.edit_text(
        format_mt5_genesis(data),
        parse_mode="Markdown",
        reply_markup=tombol_aksi(),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data_key = query.data

    await query.edit_message_text("⏳ Memproses...")

    if data_key == "harga":
        data = get_gold_data()
        text = format_harga(data)
    elif data_key == "mt5":
        data = get_gold_data()
        text = format_mt5_genesis(data)
    elif data_key == "tren":
        data = get_gold_data()
        text = format_tren(data)
    elif data_key == "sinyal":
        data = get_gold_data()
        text = format_sinyal(data)
    elif data_key == "sr":
        data = get_gold_data()
        text = format_sr(data)
    elif data_key == "isu":
        text = format_isu()
    elif data_key == "full":
        data = get_gold_data()
        text = format_full(data)
    else:
        text = "Perintah tidak dikenali."

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=tombol_aksi(),
    )


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tangani tombol keyboard + kata kunci bebas."""
    text = (update.message.text or "").strip()
    text_lower = text.lower()

    # Tombol keyboard
    if text == "💰 Harga Aktual" or any(k in text_lower for k in ["harga", "price", "berapa"]):
        await kirim_harga(update, context)
    elif text == "🏦 MT5 / Genesis" or any(k in text_lower for k in ["mt5", "genesis", "broker", "faktual"]):
        await kirim_mt5(update, context)
    elif text == "📈 Tren" or "tren" in text_lower or "trend" in text_lower:
        await kirim_tren(update, context)
    elif text == "🎯 Sinyal" or "sinyal" in text_lower or "signal" in text_lower:
        await kirim_sinyal(update, context)
    elif text == "📊 Support / Resistance" or text_lower in ["sr", "s/r"] or "support" in text_lower or "resistance" in text_lower:
        await kirim_sr(update, context)
    elif text == "📰 Isu & Rumor" or any(k in text_lower for k in ["isu", "rumor", "berita", "news"]):
        await kirim_isu(update, context)
    elif text == "📋 Ringkasan Lengkap" or any(k in text_lower for k in ["full", "lengkap", "ringkas"]):
        await kirim_full(update, context)
    elif text == "❓ Bantuan" or "bantuan" in text_lower or "help" in text_lower:
        await bantuan(update, context)
    else:
        await update.message.reply_text(
            "Pilih menu di bawah atau ketik:\n"
            "💰 Harga · 🏦 MT5/Genesis · 📈 Tren · 🎯 Sinyal · 📊 S/R · 📰 Isu · 📋 Lengkap",
            reply_markup=menu_utama(),
        )


async def post_init(application: Application) -> None:
    """Set command list di menu Telegram."""
    commands = [
        BotCommand("start", "Mulai bot & tampilkan menu"),
        BotCommand("harga", "Harga aktual gold"),
        BotCommand("mt5", "Data faktual MT5 / Genesis"),
        BotCommand("tren", "Analisis tren"),
        BotCommand("sinyal", "Sinyal trading"),
        BotCommand("sr", "Support & Resistance"),
        BotCommand("isu", "Isu & rumor pasar"),
        BotCommand("full", "Ringkasan lengkap"),
        BotCommand("help", "Bantuan"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    # Perbaikan event loop Python 3.14 / Windows
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", bantuan))
    app.add_handler(CommandHandler("harga", kirim_harga))
    app.add_handler(CommandHandler("mt5", kirim_mt5))
    app.add_handler(CommandHandler("tren", kirim_tren))
    app.add_handler(CommandHandler("sinyal", kirim_sinyal))
    app.add_handler(CommandHandler("sr", kirim_sr))
    app.add_handler(CommandHandler("isu", kirim_isu))
    app.add_handler(CommandHandler("full", kirim_full))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    logger.info("TanyaHargaBot mulai berjalan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
