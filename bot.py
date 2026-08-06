#!/usr/bin/env python3
"""
TanyaHargaBot - Alat dan teman pemburu saldo gold (XAUUSD) di MT5 dengan bahasa Indonesia
Menu lengkap: harga aktual, arus, sinyal transaksi, harga puncak/lembah, isu/rumor pasar, ringkasan, sistem & strategi
"""

import os
import sys
import logging
import asyncio
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

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

buat_sinyal_pintar = None
try:
    from services.signal_engine import buat_sinyal_pintar as _bsp
    buat_sinyal_pintar = _bsp
except Exception as _e:
    logging.getLogger(__name__).warning(f"Gagal import signal_engine: {_e}")

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN tidak ditemukan di .env")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

if buat_sinyal_pintar:
    logger.info("Engine sinyal pintar (Sinyal A-E) aktif")
else:
    logger.warning("Engine sinyal pintar TIDAK aktif — cek folder services/")


def menu_utama() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("💰 Harga Aktual"), KeyboardButton("📐 GT")],
        [KeyboardButton("📈 Arus"), KeyboardButton("🎯 Sinyal")],
        [KeyboardButton("📊 Puncak & Lembah"), KeyboardButton("📰 Isu & Rumor")],
        [KeyboardButton("📚 Sistem & Strategi"), KeyboardButton("📋 Ringkasan Lengkap")],
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
            InlineKeyboardButton("📊 Puncak/Lembah", callback_data="pl"),
            InlineKeyboardButton("📰 Isu", callback_data="isu"),
        ],
        [
            InlineKeyboardButton("📚 Strategi", callback_data="strategi"),
            InlineKeyboardButton("📋 Lengkap", callback_data="full"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _h(text) -> str:
    if text is None:
        return "-"
    s = str(text)
    return s.replace("&", "&").replace("<", "<").replace(">", ">")


def _n(v, digits=2) -> str:
    if v is None:
        return "-"
    try:
        f = float(v)
        if digits == 0:
            return str(int(round(f)))
        return f"{f:.{digits}f}"
    except Exception:
        return str(v)


def _pts(v) -> str:
    if v is None:
        return "-"
    try:
        n = int(round(float(v)))
        return str(n)
    except Exception:
        return str(v)


def _md(text: str) -> str:
    if text is None:
        return "-"
    s = str(text)
    for ch in ("_", "*", "`", "["):
        s = s.replace(ch, "\\" + ch)
    return s


async def _fetch_data(timeout: float = 12.0) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, get_gold_data),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return {"error": "Timeout mengambil data (lebih dari {:.0f} detik). Coba lagi.".format(timeout)}
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
                    try:
                        change_pct = round((float(change) / float(open_p)) * 100, 3)
                    except Exception:
                        change_pct = None

                if change is not None:
                    try:
                        c = float(change)
                        if c > 0.5:
                            arus, arus_desc = "NAIK 📈", "Neto positif"
                        elif c < -0.5:
                            arus, arus_desc = "TURUN 📉", "Neto negatif"
                        else:
                            arus, arus_desc = "DATAR ↔️", "Neto sempit"
                    except Exception:
                        arus, arus_desc = "N/A", "Data arus terbatas"
                else:
                    arus, arus_desc = "N/A", "Data arus terbatas"

                raw = mt5d.get("raw")
                if not isinstance(raw, dict):
                    raw = mt5d

                julat = mt5d.get("julat")
                if julat is None:
                    julat = mt5d.get("jangkauan")
                if julat is None and isinstance(raw, dict):
                    julat = raw.get("julat") or raw.get("jangkauan")
                if julat is None and high is not None and low is not None:
                    try:
                        julat = round(float(high) - float(low), 2)
                    except Exception:
                        julat = None

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
                    "spread": mt5d.get("spread") or (raw.get("spread") if isinstance(raw, dict) else None),
                    "neto": mt5d.get("neto") if mt5d.get("neto") is not None else (raw.get("neto") if isinstance(raw, dict) else None),
                    "inti": mt5d.get("inti") or (raw.get("inti") if isinstance(raw, dict) else None),
                    "julat": julat,
                    "tinggi": mt5d.get("tinggi") or high,
                    "bawah": mt5d.get("bawah") or low,
                    "awal": mt5d.get("awal") or open_p,
                    "time": mt5d.get("time", datetime.now().strftime("%d/%m/%Y %H:%M")),
                    "source": mt5d.get("source", "MT5/Genesis"),
                    "symbol": mt5d.get("symbol") or (raw.get("symbol") if isinstance(raw, dict) else "XAUUSD"),
                    "raw": raw,
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
            arus, arus_desc = "NAIK ✈️", "Terbang — harga di atas MA"
        elif ma_fast < ma_slow * 0.9995:
            arus, arus_desc = "TURUN ⚓", "Junam — harga di bawah MA"
        else:
            arus, arus_desc = "DATAR ↔️", "Konsolidasi — arah belum jelas"

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
            "raw": {},
        }
    except Exception as e:
        logger.error(f"Error ambil data: {e}")
        return {"error": f"Gagal mengambil data: {e}"}


def get_isu() -> str:
    daftar = [
        "📌 Keputusan suku bunga The Fed & statement-nya sangat mempengaruhi gold.",
        "📌 Data CPI & Non-Farm Payroll (NFP) AS rutin digarap trader gold.",
        "📌 Kekuatan Dolar (DXY) biasanya berkorelasi negatif dengan XAUUSD.",
        "📌 Ketegangan geopolitik sering memicu demand safe-haven ke emas.",
        "📌 Ekspektasi inflasi & yield obligasi AS memengaruhi harga gold.",
        "📌 Bersiaplah sebelum kesempatan datang.",
        "📌 Keberuntungan berpihak pada yang telah mempersiapkan diri.",
        "📌 Latih diri hari ini agar tantangan besok terasa akrab, bukan menakutkan.",
        "📌 Posisi besar di COMEX / CFTC bisa jadi sinyal arah jangka menengah.",
        "📌 Kalender high-impact (FOMC, CPI, NFP) sebaiknya dihindari memburu agresif.",
    ]
    terpilih = random.sample(daftar, k=4)
    return "\n\n".join(terpilih)


def format_strategi(data: Dict[str, Any] = None) -> str:
    if data is None:
        data = {}
    rekomendasi = ""
    if data and not data.get("error") and data.get("arus"):
        arus = data.get("arus", "")
        lembah = data.get("lembah", 0)
        puncak = data.get("puncak", 0)
        if "NAIK" in arus:
            rekomendasi = (
                f"\n🟢 <b>Rekomendasi saat ini (Arus NAIK):</b>\n"
                f"• Utamakan <b>Ikut golongan Neto naik / Ayunan ke bawah Buy</b>\n"
                f"• Masuk transaksi ideal: Mendekati perhentian bawah / MA\n"
                f"• Hindari melawan arus dengan sell agresif\n"
                f"• Target: dekat puncak {_n(puncak)}"
            )
        elif "TURUN" in arus:
            rekomendasi = (
                f"\n🔴 <b>Rekomendasi saat ini (Arus TURUN):</b>\n"
                f"• Utamakan <b>Ikut golongan Neto turun / Ayunan ke atas Sell</b>\n"
                f"• Masuk transaksi ideal: Mendekati puncak / MA\n"
                f"• Hindari melawan arus dengan buy agresif\n"
                f"• Target: dekat lembah {_n(lembah)}"
            )
        else:
            rekomendasi = (
                f"\n🟠 <b>Rekomendasi saat ini (MENDATAR):</b>\n"
                f"• Utamakan <b>Memburu Julat / Gelombang Rata</b>\n"
                f"• Buy dekat lembah dan rendah, Sell dekat puncak dan tinggi\n"
                f"• Atau tunggu trobosan yang jelas (konfirmasi volume/momentum)\n"
                f"• Hindari masuk secara tergesa-gesa di tengah gelombang"
            )
    text = (
        "📚 <b>Sistem & Strategi Memburu saldo Gold (XAUUSD)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>1. Sistem Mengikuti Arus</b>\n"
        "• Ikuti arah arus utama (H1/H4/D1)\n"
        "• Masuk: harga saat mundur naik atau turun / puncak-lembah dinamis\n"
        "• SL: di luar struktur terakhir\n"
        "• Cocok saat pasar berarus kuat\n\n"
        "<b>2. Strategi Trobosan</b>\n"
        "• Tunggu harga menembus dengan jelas perhentian bawah/atas\n"
        "• Konfirmasi: GT kuat + volume/momentum\n"
        "• Masuk setelah pengujian (lebih aman)\n"
        "• SL: di dalam level yang ditembus\n\n"
        "<b>3. Strategi Gelombang Datar (Julat)</b>\n"
        "• Buy di lembah, Sell di puncak\n"
        "• Target: harga tengah atau sisi lawan\n"
        "• Sangat cocok saat GT menunjukkan julat sempit / mendatar\n\n"
        "<b>4. Mancing dengan Data GT</b>\n"
        "• Gunakan tabel GT (Tinggi/Atas/Bawah/Rendah/Awal/Neto/Inti/Julat)\n"
        "• Entry cepat di M1-M5 saat neto jelas + harga di ekstrem\n"
        "• Risk sangat ketat (5-15 poin)\n\n"
        "<b>5. Risk Management (WAJIB)</b>\n"
        "• Risk per transaksi maksimal 1–2% equity\n"
        "• Risk:Reward minimal 1:1.5 atau 1:2\n"
        "• Jangan menambah posisi minus tanpa sistem\n"
        "• Hindari transaksi 15 menit sebelum/setelah high-impact news\n\n"
        "<b>6. Waktu yang Paling Aktif Gold</b>\n"
        "• London (Buka 14:00 WIB) & New York (Buka 19:30–20:00 WIB)\n"
        "• Volatilitas tertinggi → peluang terbaik + risiko tertinggi\n"
        f"{rekomendasi}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <i>Ini hanya edukasi & ide. Bukan saran finansial. "
        "Selalu sesuaikan dengan gaya pemburuan saldo & pengaturan risiko-mu sendiri.</i>"
    )
    return text


def format_harga(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {_h(data['error'])}"
    raw = data.get("raw") if isinstance(data.get("raw"), dict) else {}
    inti = data.get("inti") or data.get("price") or raw.get("inti") or raw.get("close") or raw.get("price")
    awal = data.get("awal") or data.get("open") or raw.get("awal") or raw.get("open")
    tinggi = data.get("tinggi") or data.get("high") or raw.get("tinggi") or raw.get("high")
    rendah = data.get("bawah") or data.get("low") or raw.get("bawah") or raw.get("low")
    neto = data.get("neto") if data.get("neto") is not None else raw.get("neto")
    julat = data.get("julat") if data.get("julat") is not None else (
        raw.get("julat") if raw.get("julat") is not None else raw.get("jangkauan")
    )
    atas = raw.get("ch")
    bawah_wick = raw.get("cl")
    if atas is None or bawah_wick is None:
        try:
            o = float(awal) if awal is not None else None
            h = float(tinggi) if tinggi is not None else None
            l = float(rendah) if rendah is not None else None
            c = float(inti) if inti is not None else None
            if o is not None and h is not None and l is not None and c is not None:
                point = 0.01
                if atas is None:
                    atas = int(round((h - max(o, c)) / point))
                if bawah_wick is None:
                    bawah_wick = int(round((min(o, c) - l) / point))
        except Exception:
            pass
    change = data.get("change")
    change_pct = data.get("change_pct")
    if change is None and neto is not None:
        change = neto
    if change is not None:
        try:
            c = float(change)
            tanda = "🟢" if c >= 0 else "🔴"
            change_str = f"{tanda} {_n(c)}"
            if change_pct is not None:
                change_str += f" ({float(change_pct):+.3f}%)"
        except Exception:
            change_str = str(change)
    else:
        change_str = "-"
    tf_raw = str(raw.get("timeframe") or "")
    if tf_raw.startswith("PERIOD_"):
        tf_raw = tf_raw.replace("PERIOD_", "", 1)
    tf_label = tf_raw if tf_raw and tf_raw != "-" else "M1"
    src_label = "Genesis EA Kebun Saldo"
    if not data.get("from_mt5"):
        src_label = data.get("source") or "Yahoo Finance"
    lines = [
        "💰 <b>Harga Gold (XAUUSD)</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Harga Live {tf_label}",
        f"Inti : {_n(inti)}",
        f"Awal : {_n(awal)}",
        f"Tinggi : {_n(tinggi)}",
        f"Rendah : {_n(rendah)}",
        f"Perubahan : {change_str}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Tinggi : {_n(tinggi)}",
        f"Atas : {_pts(atas)}",
        f"Bawah : {_pts(bawah_wick)}",
        f"Rendah : {_n(rendah)}",
        f"Awal : {_n(awal)}",
        f"Neto : {_pts(neto)}",
        f"Inti : {_n(inti)}",
        f"Julat : {_pts(julat)}",
        "",
        f"Perubahan : {change_str}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🕐 {_h(data.get('time', '-'))}",
        f"📡 {_h(src_label)}",
    ]
    return "\n".join(lines)


# REST OF FILE CONTINUES IN NEXT COMMIT - SEE d0d6596 FOR FULL
# Temporary: download full from:
# https://raw.githubusercontent.com/kebunsaldo/tanyahargabot/d0d65960990b06e474f6840970227b2a4ae14c3a/bot.py

def main():
    print("bot.py tidak lengkap. Download versi penuh:")
    print("curl -L -o bot.py https://raw.githubusercontent.com/kebunsaldo/tanyahargabot/d0d65960990b06e474f6840970227b2a4ae14c3a/bot.py")

if __name__ == "__main__":
    main()
