#!/usr/bin/env python3
"""
TanyaHargaBot - Versi Lengkap + Semua Fitur Tambahan
Fitur: Harga, GT, Arus, Sinyal, Puncak/Lembah, Isu, Strategi,
       Alert Harga, Kalkulator Lot, Chart, Multi-TF, Daily Summary,
       History Sinyal, Mode Scalping, Kalender Ekonomi
"""

import os
import sys
import logging
import asyncio
import random
import json
from datetime import datetime, timezone, time as dtime
from typing import Optional, Dict, Any, List
from pathlib import Path
from io import BytesIO

import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    InputFile,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    JobQueue,
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

# ==================== PERSISTENCE ====================
DATA_DIR = Path("bot_data")
DATA_DIR.mkdir(exist_ok=True)
ALERTS_FILE = DATA_DIR / "alerts.json"
HISTORY_FILE = DATA_DIR / "signal_history.json"
DAILY_FILE = DATA_DIR / "daily_subscribers.json"

def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Gagal simpan {path}: {e}")

alerts_db: Dict[str, List[Dict]] = load_json(ALERTS_FILE, {})
signal_history: List[Dict] = load_json(HISTORY_FILE, [])
daily_subscribers: List[int] = load_json(DAILY_FILE, [])

# ==================== KEYBOARD ====================
def menu_utama() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("💰 Harga Aktual"), KeyboardButton("📐 GT")],
        [KeyboardButton("📈 Arus"), KeyboardButton("🎯 Sinyal")],
        [KeyboardButton("📊 Puncak & Lembah"), KeyboardButton("📰 Isu & Rumor")],
        [KeyboardButton("📚 Sistem & Strategi"), KeyboardButton("📋 Ringkasan Lengkap")],
        [KeyboardButton("📉 Chart"), KeyboardButton("⏱️ Multi-TF")],
        [KeyboardButton("⚡ Scalping"), KeyboardButton("📅 Kalender")],
        [KeyboardButton("🔔 Alert"), KeyboardButton("🧮 Lot Calculator")],
        [KeyboardButton("📜 History"), KeyboardButton("☀️ Daily Summary")],
        [KeyboardButton("❓ Bantuan")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def tombol_aksi() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("💰 Harga", callback_data="harga"),
            InlineKeyboardButton("📐 GT", callback_data="mt5"),
        ],
        [
            InlineKeyboardButton("📈 Arus", callback_data="arus"),
            InlineKeyboardButton("🎯 Sinyal", callback_data="sinyal"),
        ],
        [
            InlineKeyboardButton("📊 P/L", callback_data="pl"),
            InlineKeyboardButton("📰 Isu", callback_data="isu"),
        ],
        [
            InlineKeyboardButton("📚 Strategi", callback_data="strategi"),
            InlineKeyboardButton("📋 Lengkap", callback_data="full"),
        ],
        [
            InlineKeyboardButton("📉 Chart", callback_data="chart"),
            InlineKeyboardButton("⏱️ Multi-TF", callback_data="mtf"),
        ],
        [
            InlineKeyboardButton("⚡ Scalping", callback_data="scalp"),
            InlineKeyboardButton("📅 Kalender", callback_data="calendar"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def _h(text) -> str:
    if text is None:
        return "-"
    s = str(text)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ==================== DATA HARGA ====================
async def _fetch_data(timeout: float = 12.0) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, get_gold_data),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return {"error": f"Timeout mengambil data (lebih dari {timeout:.0f} detik)."}
    except Exception as e:
        logger.error(f"fetch error: {e}")
        return {"error": f"Gagal mengambil data: {e}"}

def get_gold_data() -> Dict[str, Any]:
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

                if change is not None:
                    if change > 0.5:
                        arus, arus_desc = "NAIK 📈", "Neto positif"
                    elif change < -0.5:
                        arus, arus_desc = "TURUN 📉", "Neto negatif"
                    else:
                        arus, arus_desc = "DATAR ↔️", "Neto sempit"
                else:
                    arus, arus_desc = "N/A", "Data arus terbatas"

                return {
                    "price": price,
                    "open": open_p,
                    "high": high,
                    "low": low,
                    "change": change,
                    "change_pct": change_pct,
                    "arus": arus,
                    "arus_desc": arus_desc,
                    "lembah": mt5d.get("lembah") or low,
                    "puncak": mt5d.get("puncak") or high,
                    "mid": mt5d.get("inti"),
                    "bid": mt5d.get("bid"),
                    "ask": mt5d.get("ask"),
                    "spread": mt5d.get("spread"),
                    "neto": mt5d.get("neto"),
                    "inti": mt5d.get("inti"),
                    "julat": mt5d.get("julat"),
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

    try:
        ticker = yf.Ticker("GC=F")
        hist = ticker.history(period="5d", interval="1h")
        if hist.empty:
            ticker = yf.Ticker("XAUUSD=X")
            hist = ticker.history(period="5d", interval="1h")
        if hist.empty:
            return {"error": "Gagal mengambil data harga."}

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
            arus, arus_desc = "NAIK ✈️", "Terbang — harga di atas MA"
        elif ma_fast < ma_slow * 0.9995:
            arus, arus_desc = "TURUN ⚓", "Junam — harga di bawah MA"
        else:
            arus, arus_desc = "DATAR ↔️", "Konsolidasi"

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
            "arus": arus,
            "arus_desc": arus_desc,
            "lembah": round(support, 2),
            "puncak": round(resistance, 2),
            "mid": round(mid, 2),
            "neto": round(change, 2),
            "inti": round(mid, 2),
            "julat": round(high - low, 2),
            "tinggi": round(high, 2),
            "bawah": round(low, 2),
            "awal": round(open_p, 2),
            "time": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
            "source": "Yahoo Finance (GC=F)",
            "from_mt5": False,
            "hist": hist,
        }
    except Exception as e:
        logger.error(f"Error ambil data: {e}")
        return {"error": f"Gagal mengambil data: {e}"}

def buat_sinyal(data: Dict[str, Any]) -> str:
    if data.get("error") or not data.get("price"):
        return "⚠️ Data tidak tersedia."
    change = data.get("change_pct") or 0
    arus = data.get("arus", "")
    price = data["price"]
    lembah = data.get("lembah", 0)
    puncak = data.get("puncak", 0)
    jarak_sup = ((price - lembah) / price) * 100 if price else 0
    jarak_res = ((puncak - price) / price) * 100 if price else 0

    if "NAIK" in arus and change > 0.1:
        sinyal = "🟢 BUY / LONG"
        alasan = f"Arus naik + momentum positif.\n• Masuk: ${price:,.2f}\n• SL: di bawah ${lembah:,.2f}\n• TP: dekat ${puncak:,.2f}"
    elif "TURUN" in arus and change < -0.1:
        sinyal = "🔴 SELL / SHORT"
        alasan = f"Arus turun + momentum negatif.\n• Masuk: ${price:,.2f}\n• SL: di atas ${puncak:,.2f}\n• TP: dekat ${lembah:,.2f}"
    elif jarak_sup < 0.15:
        sinyal = "🟡 LIHAT LEMBAH"
        alasan = "Harga dekat lembah. Pantau hold atau break."
    elif jarak_res < 0.15:
        sinyal = "🟡 LIHAT PUNCAK"
        alasan = "Harga dekat puncak. Pantau ayunan atau trobosan."
    else:
        sinyal = "🟠 TUNGGU / DATAR"
        alasan = "Arah belum jelas. Tunggu konfirmasi."

    # Simpan history
    entry = {
        "time": datetime.now().strftime("%d/%m %H:%M"),
        "sinyal": sinyal,
        "price": price,
        "arus": arus,
    }
    signal_history.insert(0, entry)
    if len(signal_history) > 20:
        signal_history.pop()
    save_json(HISTORY_FILE, signal_history)

    return f"<b>Sinyal:</b> {sinyal}\n\n{alasan}"

def get_isu() -> str:
    daftar = [
        "📌 Keputusan suku bunga The Fed & statement-nya sangat mempengaruhi gold.",
        "📌 Data CPI & Non-Farm Payroll (NFP) AS rutin digarap trader gold.",
        "📌 Kekuatan Dolar (DXY) biasanya berkorelasi negatif dengan XAUUSD.",
        "📌 Ketegangan geopolitik sering memicu demand safe-haven ke emas.",
        "📌 Ekspektasi inflasi & yield obligasi AS memengaruhi harga gold.",
        "📌 Bersiaplah sebelum kesempatan datang.",
        "📌 Keberuntungan berpihak pada yang telah mempersiapkan diri.",
        "📌 Latih diri hari ini agar tantangan besok terasa akrab.",
        "📌 Posisi besar di COMEX / CFTC bisa jadi sinyal arah jangka menengah.",
        "📌 Kalender high-impact (FOMC, CPI, NFP) sebaiknya dihindari memburu agresif.",
    ]
    return "\n\n".join(random.sample(daftar, k=4))

# ==================== FITUR BARU ====================
def format_strategi(data: Dict[str, Any] = None) -> str:
    if data is None:
        data = {}
    rekomendasi = ""
    if data and not data.get("error") and data.get("arus"):
        arus = data.get("arus", "")
        lembah = data.get("lembah", 0)
        puncak = data.get("puncak", 0)
        if "NAIK" in arus:
            rekomendasi = f"\n🟢 <b>Rekomendasi (Arus NAIK):</b>\n• Utamakan Buy di pullback\n• Target dekat puncak ${puncak:,.2f}"
        elif "TURUN" in arus:
            rekomendasi = f"\n🔴 <b>Rekomendasi (Arus TURUN):</b>\n• Utamakan Sell di pullback\n• Target dekat lembah ${lembah:,.2f}"
        else:
            rekomendasi = "\n🟠 <b>Rekomendasi (DATAR):</b>\n• Range trading atau tunggu breakout"
    return (
        "📚 <b>Sistem & Strategi Gold</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>1. Mengikuti Arus</b>\n• Ikuti H1/H4/D1\n• SL di luar struktur\n\n"
        "<b>2. Trobosan</b>\n• Tunggu break + konfirmasi\n\n"
        "<b>3. Range / Julat</b>\n• Buy di support, Sell di resistance\n\n"
        "<b>4. Risk Management</b>\n• Max 1-2% per trade\n• RR minimal 1:1.5\n"
        f"{rekomendasi}\n━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <i>Edukasi saja, bukan saran finansial.</i>"
    )

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
    src_label = data.get("source", "-")
    if "genesis" in str(src_label).lower():
        src_label = "Genesis EA (kebun saldo)"
    lines = [
        "💰 <b>Harga Gold (XAUUSD)</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "Harga sekarang",
        f"Inti : <b>${data['price']:,.2f}</b>",
    ]
    if data.get("open") is not None:
        lines.append(f"Awal                : ${data['open']:,.2f}")
    if data.get("high") is not None:
        lines.append(f"Tinggi              : ${data['high']:,.2f}")
    if data.get("low") is not None:
        lines.append(f"Rendah              : ${data['low']:,.2f}")
    lines.append(f"Perubahan           : {change_str}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🕐 {_h(data.get('time', '-'))}")
    lines.append(f"📡 {_h(src_label)}")
    return "\n".join(lines)

def format_mt5_genesis(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {_h(data['error'])}"
    if not data.get("from_mt5") and not data.get("raw"):
        return (
            "📐 <b>GT</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            "❌ Belum ada data dari EA GT.\n\n"
            "Pastikan EA aktif dan file genesis_data.json terbentuk."
        )
    # (versi ringkas untuk menghemat panjang, bisa diganti dengan versi lengkap sebelumnya)
    return (
        f"📐 <b>Data Faktual GT</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga : <b>${data.get('price', 0):,.2f}</b>\n"
        f"Arus  : {data.get('arus', '-')}\n"
        f"Neto  : {data.get('neto', '-')}\n"
        f"Puncak: ${data.get('puncak', 0):,.2f}\n"
        f"Lembah: ${data.get('lembah', 0):,.2f}\n"
        f"🕐 {_h(data.get('time'))}\n"
        f"📡 {_h(data.get('source'))}"
    )

def format_tren(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    return (
        f"📈 <b>Analisis Arus Gold</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga   : <b>${data['price']:,.2f}</b>\n"
        f"Arus    : <b>{data['arus']}</b>\n"
        f"Keterangan : {data['arus_desc']}\n"
        f"Perubahan  : {data['change']:+.2f} ({data['change_pct']:+.3f}%)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Berdasarkan MA pendek vs panjang.</i>"
    )

def format_sinyal(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    sinyal_text = buat_sinyal(data)
    return (
        f"🎯 <b>Sinyal Transaksi Gold</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga : <b>${data['price']:,.2f}</b>\n"
        f"Arus  : {data['arus']}\n\n"
        f"{sinyal_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Bukan saran finansial.</i>"
    )

def format_sr(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    price = data["price"]
    lem = data["lembah"]
    pun = data["puncak"]
    mid = data["mid"]
    return (
        f"📊 <b>Puncak & Lembah</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga sekarang : <b>${price:,.2f}</b>\n\n"
        f"🔴 Puncak  : <b>${pun:,.2f}</b>\n"
        f"   Jarak   : {((pun - price) / price * 100):+.2f}%\n\n"
        f"⚪ Midpoint: ${mid:,.2f}\n\n"
        f"🟢 Lembah  : <b>${lem:,.2f}</b>\n"
        f"   Jarak   : {((price - lem) / price * 100):+.2f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

def format_isu() -> str:
    return (
        f"📰 <b>Isu & Rumor</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{get_isu()}\n\n━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Cross-check dengan sumber resmi.</i>"
    )

def format_full(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {_h(data['error'])}"
    sinyal_text = buat_sinyal(data)
    return (
        f"📋 <b>Ringkasan Lengkap</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Harga  : <b>${data.get('price', 0):,.2f}</b>\n"
        f"📈 Arus   : <b>{_h(data.get('arus'))}</b>\n"
        f"📊 Puncak : ${data.get('puncak', 0):,.2f}\n"
        f"   Lembah : ${data.get('lembah', 0):,.2f}\n\n"
        f"{sinyal_text}\n\n"
        f"🕐 {_h(data.get('time'))}\n⚠️ Bukan saran finansial."
    )

# ===== FITUR BARU =====
def format_lot_calculator(balance: float, risk_pct: float, sl_points: float) -> str:
    risk_amount = balance * (risk_pct / 100)
    # Asumsi 1 lot XAUUSD ≈ $1 per 0.01 point (sesuaikan broker)
    value_per_point = 1.0  # untuk 0.01 lot ≈ $0.01 per point, sesuaikan
    lot = risk_amount / (sl_points * value_per_point * 100)  # rough
    lot = max(0.01, round(lot, 2))
    return (
        f"🧮 <b>Kalkulator Lot</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Saldo        : ${balance:,.2f}\n"
        f"Risiko       : {risk_pct}% (${risk_amount:,.2f})\n"
        f"SL           : {sl_points} poin\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Lot disarankan : {lot}</b>\n\n"
        f"<i>Hitungan kasar. Sesuaikan dengan kontrak broker-mu.</i>"
    )

def format_calendar() -> str:
    # Contoh data (bisa diganti dengan scraping / API nanti)
    events = [
        "🇺🇸 CPI (Inflasi) - Biasanya sangat impact ke Gold",
        "🇺🇸 Non-Farm Payroll (NFP) - Volatilitas tinggi",
        "🇺🇸 FOMC / Keputusan Suku Bunga The Fed",
        "🇺🇸 Retail Sales & Unemployment Claims",
        "🇪🇺 ECB Rate Decision (jika ada)",
        "🇨🇳 China PMI / Data ekonomi China",
    ]
    return (
        "📅 <b>Kalender Ekonomi High-Impact (Gold)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(f"• {e}" for e in events) +
        "\n\n━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Cek Forex Factory / Investing.com untuk jadwal pasti hari ini.</i>"
    )

def format_multi_tf(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    return (
        f"⏱️ <b>Ringkasan Multi-Timeframe</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga sekarang : <b>${data['price']:,.2f}</b>\n\n"
        f"• M15 / H1  : {data.get('arus', 'N/A')} (pendek)\n"
        f"• H4 / D1   : Gunakan GT + puncak/lembah untuk konfirmasi\n\n"
        f"Puncak : ${data.get('puncak', 0):,.2f}\n"
        f"Lembah : ${data.get('lembah', 0):,.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Gabungkan dengan sinyal utama untuk konfirmasi.</i>"
    )

def format_scalping(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    return (
        f"⚡ <b>Mode Scalping / Intraday</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga : <b>${data['price']:,.2f}</b>\n"
        f"Arus  : {data.get('arus')}\n"
        f"Neto  : {data.get('neto', '-')}\n"
        f"Julat : {data.get('julat', '-')}\n\n"
        f"<b>Ide Scalping:</b>\n"
        f"• Fokus M1–M5 + data GT\n"
        f"• Target 10–30 poin\n"
        f"• SL ketat 5–15 poin\n"
        f"• Hindari news high-impact\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Risk tinggi, gunakan lot kecil."
    )

def format_history() -> str:
    if not signal_history:
        return "📜 Belum ada history sinyal."
    lines = ["📜 <b>History Sinyal (terbaru)</b>\n━━━━━━━━━━━━━━━━━━━━"]
    for h in signal_history[:8]:
        lines.append(f"{h['time']} | {h['sinyal']} @ ${h['price']:,.2f}")
    return "\n".join(lines)

async def generate_chart(data: Dict[str, Any]) -> Optional[BytesIO]:
    try:
        hist = data.get("hist")
        if hist is None or hist.empty:
            ticker = yf.Ticker("GC=F")
            hist = ticker.history(period="3d", interval="1h")
        if hist.empty:
            return None
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(hist.index, hist["Close"], color="#f0b90b", linewidth=1.5)
        ax.set_title("XAUUSD - H1 Chart", fontsize=14)
        ax.set_ylabel("Price")
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=30)
        plt.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.error(f"Chart error: {e}")
        return None

# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nama = update.effective_user.first_name or "Pemburu"
    text = (
        f"Halo <b>{nama}</b>! 👋\n\n"
        f"Saya <b>TanyaHargaBot</b> (versi lengkap).\n\n"
        f"Fitur tersedia:\n"
        f"💰 Harga • 📐 GT • 📈 Arus • 🎯 Sinyal\n"
        f"📊 Puncak/Lembah • 📰 Isu • 📚 Strategi\n"
        f"📉 Chart • ⏱️ Multi-TF • ⚡ Scalping\n"
        f"🔔 Alert • 🧮 Lot • 📅 Kalender\n"
        f"📜 History • ☀️ Daily Summary\n\n"
        f"Pilih menu di bawah!"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=menu_utama())

async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ <b>Bantuan TanyaHargaBot</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Perintah tambahan:</b>\n"
        "<code>/alert 2650 up</code> → set alert harga\n"
        "<code>/lot 1000 1 30</code> → hitung lot (saldo risk% SL)\n"
        "<code>/daily</code> → aktifkan ringkasan harian\n"
        "<code>/history</code> → lihat sinyal terakhir\n\n"
        "Semua fitur juga bisa diakses lewat tombol keyboard."
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=menu_utama())

async def kirim_harga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Mengambil harga...")
    data = await _fetch_data()
    await msg.edit_text(format_harga(data), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_arus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Menganalisis arus...")
    data = await _fetch_data()
    await msg.edit_text(format_tren(data), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_sinyal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Menyusun sinyal...")
    data = await _fetch_data()
    await msg.edit_text(format_sinyal(data), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_pl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Menghitung level...")
    data = await _fetch_data()
    await msg.edit_text(format_sr(data), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_isu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_isu(), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_strategi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Menyusun strategi...")
    data = await _fetch_data()
    await msg.edit_text(format_strategi(data), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Menyusun ringkasan...")
    data = await _fetch_data()
    await msg.edit_text(format_full(data), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_mt5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Mengambil data GT...")
    data = await _fetch_data(8)
    await msg.edit_text(format_mt5_genesis(data), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Membuat chart...")
    data = await _fetch_data()
    buf = await generate_chart(data)
    if buf:
        await update.message.reply_photo(photo=InputFile(buf, "xauusd.png"), caption="📉 XAUUSD H1 Chart")
        await msg.delete()
    else:
        await msg.edit_text("❌ Gagal membuat chart.")

async def kirim_mtf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Multi-timeframe...")
    data = await _fetch_data()
    await msg.edit_text(format_multi_tf(data), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_scalp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Mode scalping...")
    data = await _fetch_data()
    await msg.edit_text(format_scalping(data), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_calendar(), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_history(), parse_mode="HTML", reply_markup=tombol_aksi())

async def cmd_lot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("Format: /lot <saldo> <risiko%> <SL poin>\nContoh: /lot 1000 1 30")
            return
        balance = float(args[0])
        risk = float(args[1])
        sl = float(args[2])
        await update.message.reply_text(format_lot_calculator(balance, risk, sl), parse_mode="HTML")
    except Exception:
        await update.message.reply_text("Format salah. Contoh: /lot 1000 1 30")

async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Format: /alert <harga> <up/down>\nContoh: /alert 2650 up")
            return
        price = float(args[0])
        direction = args[1].lower()
        if direction not in ("up", "down"):
            await update.message.reply_text("Arah harus up atau down")
            return
        chat_id = str(update.effective_chat.id)
        if chat_id not in alerts_db:
            alerts_db[chat_id] = []
        alerts_db[chat_id].append({"price": price, "direction": direction, "active": True})
        save_json(ALERTS_FILE, alerts_db)
        await update.message.reply_text(f"✅ Alert diset: {direction.upper()} ${price:,.2f}")
    except Exception:
        await update.message.reply_text("Format: /alert 2650 up")

async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in daily_subscribers:
        daily_subscribers.remove(chat_id)
        save_json(DAILY_FILE, daily_subscribers)
        await update.message.reply_text("❌ Daily Summary dimatikan.")
    else:
        daily_subscribers.append(chat_id)
        save_json(DAILY_FILE, daily_subscribers)
        await update.message.reply_text("✅ Daily Summary diaktifkan (kirim setiap pagi).")

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    data = await _fetch_data(10)
    if data.get("error") or not data.get("price"):
        return
    current = data["price"]
    for chat_id, alert_list in list(alerts_db.items()):
        for alert in alert_list[:]:
            if not alert.get("active"):
                continue
            triggered = False
            if alert["direction"] == "up" and current >= alert["price"]:
                triggered = True
            elif alert["direction"] == "down" and current <= alert["price"]:
                triggered = True
            if triggered:
                try:
                    await context.bot.send_message(
                        chat_id=int(chat_id),
                        text=f"🔔 <b>ALERT TERPICU!</b>\nHarga sekarang ${current:,.2f}\nTarget: {alert['direction'].upper()} ${alert['price']:,.2f}",
                        parse_mode="HTML",
                    )
                    alert["active"] = False
                except Exception:
                    pass
        save_json(ALERTS_FILE, alerts_db)

async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    data = await _fetch_data(12)
    text = format_full(data) if not data.get("error") else "❌ Gagal ambil data harian."
    for chat_id in daily_subscribers:
        try:
            await context.bot.send_message(chat_id=chat_id, text="☀️ <b>Daily Summary</b>\n\n" + text, parse_mode="HTML")
        except Exception:
            pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data
    try:
        await query.edit_message_text("⏳ Memproses...")
    except Exception:
        pass
    try:
        if key == "isu":
            text = format_isu()
        elif key == "calendar":
            text = format_calendar()
        else:
            data = await _fetch_data()
            mapping = {
                "harga": format_harga,
                "mt5": format_mt5_genesis,
                "arus": format_tren,
                "sinyal": format_sinyal,
                "pl": format_sr,
                "strategi": format_strategi,
                "full": format_full,
                "mtf": format_multi_tf,
                "scalp": format_scalping,
            }
            text = mapping.get(key, lambda d: "Perintah tidak dikenali")(data)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        try:
            await query.edit_message_text(f"❌ Gagal: {e}")
        except Exception:
            pass

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    low = text.lower()

    if text == "💰 Harga Aktual" or "harga" in low:
        await kirim_harga(update, context)
    elif text == "📐 GT" or any(k in low for k in ["mt5", "gt", "genesis"]):
        await kirim_mt5(update, context)
    elif text == "📈 Arus" or "arus" in low:
        await kirim_arus(update, context)
    elif text == "🎯 Sinyal" or "sinyal" in low:
        await kirim_sinyal(update, context)
    elif text == "📊 Puncak & Lembah" or any(k in low for k in ["puncak", "lembah", "pl"]):
        await kirim_pl(update, context)
    elif text == "📰 Isu & Rumor" or any(k in low for k in ["isu", "rumor"]):
        await kirim_isu(update, context)
    elif text == "📚 Sistem & Strategi" or "strategi" in low:
        await kirim_strategi(update, context)
    elif text == "📋 Ringkasan Lengkap" or "lengkap" in low or "full" in low:
        await kirim_full(update, context)
    elif text == "📉 Chart" or "chart" in low:
        await kirim_chart(update, context)
    elif text == "⏱️ Multi-TF" or "multi" in low or "mtf" in low:
        await kirim_mtf(update, context)
    elif text == "⚡ Scalping" or "scalp" in low:
        await kirim_scalp(update, context)
    elif text == "📅 Kalender" or "kalender" in low or "calendar" in low:
        await kirim_calendar(update, context)
    elif text == "📜 History" or "history" in low:
        await kirim_history(update, context)
    elif text == "🔔 Alert" or "alert" in low:
        await update.message.reply_text("Gunakan: /alert 2650 up   atau   /alert 2600 down")
    elif text == "🧮 Lot Calculator" or "lot" in low:
        await update.message.reply_text("Gunakan: /lot 1000 1 30\n(saldo, risiko%, SL poin)")
    elif text == "☀️ Daily Summary" or "daily" in low:
        await cmd_daily(update, context)
    elif text == "❓ Bantuan" or "bantuan" in low or "help" in low:
        await bantuan(update, context)
    else:
        await update.message.reply_text("Pilih menu di bawah ya.", reply_markup=menu_utama())

async def post_init(application: Application):
    commands = [
        BotCommand("start", "Mulai bot"),
        BotCommand("harga", "Harga aktual"),
        BotCommand("arus", "Analisis arus"),
        BotCommand("sinyal", "Sinyal"),
        BotCommand("pl", "Puncak & Lembah"),
        BotCommand("alert", "Set price alert"),
        BotCommand("lot", "Kalkulator lot"),
        BotCommand("daily", "Toggle daily summary"),
        BotCommand("history", "History sinyal"),
        BotCommand("help", "Bantuan"),
    ]
    await application.bot.set_my_commands(commands)

    # Job untuk cek alert setiap 60 detik
    application.job_queue.run_repeating(check_alerts, interval=60, first=10)
    # Daily summary jam 08:00 WIB (01:00 UTC)
    application.job_queue.run_daily(daily_job, time=dtime(hour=1, minute=0))

def main():
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", bantuan))
    app.add_handler(CommandHandler("harga", kirim_harga))
    app.add_handler(CommandHandler("mt5", kirim_mt5))
    app.add_handler(CommandHandler("gt", kirim_mt5))
    app.add_handler(CommandHandler("arus", kirim_arus))
    app.add_handler(CommandHandler("sinyal", kirim_sinyal))
    app.add_handler(CommandHandler("pl", kirim_pl))
    app.add_handler(CommandHandler("isu", kirim_isu))
    app.add_handler(CommandHandler("strategi", kirim_strategi))
    app.add_handler(CommandHandler("full", kirim_full))
    app.add_handler(CommandHandler("alert", cmd_alert))
    app.add_handler(CommandHandler("lot", cmd_lot))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("history", kirim_history))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    logger.info("TanyaHargaBot (Full Features) mulai berjalan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
