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

# Pastikan folder project ada di sys.path (agar import services.* selalu jalan)
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

# Sinyal pintar berbasis GT (Sinyal A-E)
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


# ==================== KEYBOARD MENU ====================
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
    """Format angka TANPA koma ribuan. Contoh: 4271.53"""
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
    """Format poin (neto/julat/atas/bawah) tanpa koma."""
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


# ==================== DATA HARGA ====================

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


# ==================== FORMAT PESAN ====================
def format_harga(data: Dict[str, Any]) -> str:
    """
    Format Harga Live sesuai contoh user:
    - tanpa koma ribuan
    - tampilkan data GT LIVE (Tinggi/Atas/Bawah/Rendah/Awal/Neto/Inti/Julat)
    """
    if data.get("error"):
        return f"❌ {_h(data['error'])}"

    raw = data.get("raw") if isinstance(data.get("raw"), dict) else {}

    # Ambil nilai LIVE
    inti = data.get("inti") or data.get("price") or raw.get("inti") or raw.get("close") or raw.get("price")
    awal = data.get("awal") or data.get("open") or raw.get("awal") or raw.get("open")
    tinggi = data.get("tinggi") or data.get("high") or raw.get("tinggi") or raw.get("high")
    rendah = data.get("bawah") or data.get("low") or raw.get("bawah") or raw.get("low")
    neto = data.get("neto") if data.get("neto") is not None else raw.get("neto")
    julat = data.get("julat") if data.get("julat") is not None else (
        raw.get("julat") if raw.get("julat") is not None else raw.get("jangkauan")
    )

    # Atas / Bawah (wick)
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

    # Perubahan (pakai change dari data, fallback ke neto)
    change = data.get("change")
    change_pct = data.get("change_pct")
    if change is None and neto is not None:
        # neto di Genesis biasanya dalam points; tampilkan apa adanya
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

    # Label TF
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


def format_mt5_genesis(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {_h(data['error'])}"

    raw = data.get("raw") if isinstance(data.get("raw"), dict) else {}

    if not data.get("from_mt5") and not raw:
        return (
            "📐 <b>GT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "❌ Belum ada data dari EA GT.\n\n"
            "<b>Cek langkah ini:</b>\n"
            "1. EA sudah di-compile & aktif di chart\n"
            "2. File terbentuk di:\n"
            "   <code>%APPDATA%/MetaQuotes/Terminal/Common/Files/genesis_data.json</code>\n"
            "3. Restart bot setelah file ada\n\n"
            "Sementara menu <b>Harga Aktual</b> memakai Yahoo Finance."
        )

    def num(v, digits=2):
        return _n(v, digits)

    def pts(v):
        if v is None:
            return "-"
        try:
            n = int(round(float(v)))
            return f"{n:+d}" if n != 0 else "0"
        except Exception:
            return str(v)

    def bar_dict(d):
        return d if isinstance(d, dict) else {}

    def hitung_atas_bawah(open_p, high, low, close, neto=None):
        try:
            o, h, l, c = float(open_p), float(high), float(low), float(close)
        except (TypeError, ValueError):
            return None, None
        point = 0.01
        try:
            atas = int(round((h - max(o, c)) / point))
            bawah = int(round((min(o, c) - l) / point))
            return atas, bawah
        except Exception:
            return None, None

    gt1 = bar_dict(raw.get("gt1"))
    gt2 = bar_dict(raw.get("gt2"))
    gt3 = bar_dict(raw.get("gt3"))

    live_open = data.get("awal") or data.get("open") or raw.get("open") or raw.get("awal")
    live_high = data.get("tinggi") or data.get("high") or raw.get("high") or raw.get("tinggi")
    live_low = data.get("bawah") or data.get("low") or raw.get("low") or raw.get("bawah")
    live_close = data.get("inti") or data.get("close") or raw.get("close") or raw.get("inti")
    live_neto = data.get("neto") if data.get("neto") is not None else raw.get("neto")
    live_range = data.get("julat") if data.get("julat") is not None else (
        raw.get("julat") if raw.get("julat") is not None else raw.get("jangkauan")
    )

    live_atas = raw.get("ch")
    live_bawah = raw.get("cl")
    if live_atas is None or live_bawah is None:
        a, b = hitung_atas_bawah(live_open, live_high, live_low, live_close, live_neto)
        if live_atas is None:
            live_atas = a
        if live_bawah is None:
            live_bawah = b

    def atas_bawah_bar(g):
        if not g:
            return None, None
        return hitung_atas_bawah(g.get("open"), g.get("high"), g.get("low"), g.get("close"), g.get("neto"))

    a1, b1 = atas_bawah_bar(gt1)
    a2, b2 = atas_bawah_bar(gt2)
    a3, b3 = atas_bawah_bar(gt3)

    def col(v, width=9):
        s = num(v) if not isinstance(v, str) else v
        if s == "-":
            return s.center(width)
        if len(s) > width:
            s = s[:width]
        return s.rjust(width)

    def col_pts(v, width=9):
        return pts(v).rjust(width)

    rows = []
    rows.append("           GT3       GT2      GT1    LIVE")
    rows.append("──────    ──────   ──────   ──────   ─────")
    rows.append(f"Tinggi  {col(gt3.get('high'))} {col(gt2.get('high'))} {col(gt1.get('high'))} {col(live_high)}")
    rows.append(f"Atas    {col_pts(a3)} {col_pts(a2)} {col_pts(a1)} {col_pts(live_atas)}")
    rows.append(f"Bawah   {col_pts(b3)} {col_pts(b2)} {col_pts(b1)} {col_pts(live_bawah)}")
    rows.append(f"Rendah  {col(gt3.get('low'))} {col(gt2.get('low'))} {col(gt1.get('low'))} {col(live_low)}")
    rows.append(f"Awal    {col(gt3.get('open'))} {col(gt2.get('open'))} {col(gt1.get('open'))} {col(live_open)}")
    rows.append(f"Neto    {col_pts(gt3.get('neto'))} {col_pts(gt2.get('neto'))} {col_pts(gt1.get('neto'))} {col_pts(live_neto)}")
    rows.append(f"Inti    {col(gt3.get('close'))} {col(gt2.get('close'))} {col(gt1.get('close'))} {col(live_close)}")
    rows.append(f"Julat   {col_pts(gt3.get('julat'))} {col_pts(gt2.get('julat'))} {col_pts(gt1.get('julat'))} {col_pts(live_range)}")
    table = "\n".join(rows)

    simbol = _h(data.get("symbol") or raw.get("symbol") or "XAUUSD")
    harga = num(data.get("price") or raw.get("price"))
    bid = num(data.get("bid") or raw.get("bid"))
    ask = num(data.get("ask") or raw.get("ask"))
    spread = raw.get("spread") if raw.get("spread") is not None else data.get("spread")
    tf_raw = str(raw.get("timeframe") or "-")
    if tf_raw.startswith("PERIOD_"):
        tf_raw = tf_raw.replace("PERIOD_", "", 1)
    tf = _h(tf_raw)
    waktu = _h(data.get("time") or raw.get("time") or "-")
    sumber = _h("Genesis EA Kebun Saldo")

    balance = raw.get("balance")
    equity = raw.get("equity")
    buy_exp = raw.get("buy_exp") or "-"
    sell_exp = raw.get("sell_exp") or "-"
    symbol_pl = raw.get("symbol_pl")
    symbol_pl_pts = raw.get("symbol_pl_pts")
    margin_level_str = raw.get("margin_level_str") or "-"
    so_price = raw.get("so_price") or "-"
    eq_to_so = raw.get("eq_to_so") or "-"
    pts_to_so = raw.get("pts_to_so") or "-"

    if symbol_pl is not None:
        try:
            pl_v = float(symbol_pl)
            pl_pts = int(symbol_pl_pts) if symbol_pl_pts is not None else 0
            if pl_v > 0.005:
                pl_str = f"+{_n(pl_v)} (+{pl_pts} pts)"
            elif pl_v < -0.005:
                pl_str = f"{_n(pl_v)} ({pl_pts} pts)"
            else:
                pl_str = f"{_n(pl_v)} (0 pts)"
        except Exception:
            pl_str = str(symbol_pl)
    else:
        pl_str = "-"

    text = (
        f"📐 <b>Data Faktual GT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Simbol  : <b>{simbol}</b>  |  TF: {tf}\n"
        f"Harga   : <b>{harga}</b>\n"
        f"Bid/Ask : {bid} / {ask}\n"
        f"Spread  : {spread if spread is not None else '-'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Genesis Riwayat Angka Faktual Informasi Keuangan</b>\n"
        f"<i>Tinggi · Atas · Bawah · Rendah · Awal · Neto · Inti · Julat</i>\n"
        f"<pre>{table}</pre>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Posisi & Akun</b>\n"
        f"<pre>"
        f"Balance      : {num(balance)}\n"
        f"Equity       : {num(equity)}\n"
        f"Buy Exp      : {_h(buy_exp)}\n"
        f"Sell Exp     : {_h(sell_exp)}\n"
        f"Symbol P/L   : {_h(pl_str)}\n"
        f"Margin Level : {_h(margin_level_str)}\n"
        f"SO Price     : {_h(so_price)}\n"
        f"Eq to SO     : {_h(eq_to_so)}\n"
        f"Pts to SO    : {_h(pts_to_so)}"
        f"</pre>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {waktu}\n"
        f"📡 {sumber}"
    )
    return text


def format_tren(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {_h(data['error'])}"
    ch = data.get("change")
    cp = data.get("change_pct")
    try:
        ch_str = f"{_n(ch)}" if ch is not None else "-"
        if cp is not None:
            ch_str += f" ({float(cp):+.3f}%)"
    except Exception:
        ch_str = str(ch)
    return (
        f"📈 <b>Analisis Arus Gold</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga   : <b>{_n(data.get('price'))}</b>\n"
        f"Arus    : <b>{_h(data.get('arus'))}</b>\n"
        f"Keterangan : {_h(data.get('arus_desc'))}\n"
        f"Perubahan  : {ch_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Berdasarkan Moving Average periode pendek vs panjang.</i>"
    )


def format_sinyal(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {_h(data['error'])}"

    if buat_sinyal_pintar is not None:
        try:
            return buat_sinyal_pintar(data)
        except Exception as e:
            logger.error(f"Error buat_sinyal_pintar: {e}")
            return (
                f"🎯 <b>Sinyal</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"❌ Error engine sinyal: {_h(str(e))}\n"
                f"Harga: {_n(data.get('price', 0))}\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )

    price = data.get("price", 0)
    arus = data.get("arus", "-")
    return (
        f"🎯 <b>Sinyal Transaksi Gold</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga : <b>{_n(price)}</b>\n"
        f"Arus  : {_h(arus)}\n\n"
        f"⚠️ Engine sinyal pintar belum tersedia.\n"
        f"Pastikan folder <code>services/signal_engine.py</code> ada\n"
        f"dan bot dijalankan dari folder project.\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Bukan saran finansial. Gunakan risk management.</i>"
    )


def format_sr(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {_h(data['error'])}"
    price = data["price"]
    lem = data["lembah"]
    pun = data["puncak"]
    mid = data["mid"]
    return (
        f"📊 <b>Puncak & Lembah</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga sekarang : <b>{_n(price)}</b>\n\n"
        f"🔴 Puncak  : <b>{_n(pun)}</b>\n"
        f"   Jarak       : {((pun - price) / price * 100):+.2f}%\n\n"
        f"⚪ Midpoint    : {_n(mid)}\n\n"
        f"🟢 Lembah     : <b>{_n(lem)}</b>\n"
        f"   Jarak       : {((price - lem) / price * 100):+.2f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Dihitung dari tinggi/rendah 48 bar terakhir.</i>"
    )


def format_isu() -> str:
    return (
        f"📰 <b>Isu & Rumor yang Perlu Diperhatikan</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{get_isu()}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Selalu cross-check dengan sumber berita resmi.</i>"
    )


def format_full(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {_h(data['error'])}"

    if buat_sinyal_pintar is not None:
        try:
            sinyal_text = buat_sinyal_pintar(data)
        except Exception as e:
            sinyal_text = f"Sinyal error: {_h(str(e))}"
    else:
        sinyal_text = "Sinyal: engine belum aktif"

    ch = data.get("change")
    cp = data.get("change_pct")
    try:
        ch_str = f"{_n(ch)}" if ch is not None else "-"
        if cp is not None:
            ch_str += f" ({float(cp):+.3f}%)"
    except Exception:
        ch_str = str(ch)

    return (
        f"📋 <b>Ringkasan Lengkap Gold (XAUUSD)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Harga  : <b>{_n(data.get('price'))}</b>\n"
        f"   Open   : {_n(data.get('open'))}\n"
        f"   High   : {_n(data.get('high'))}\n"
        f"   Low    : {_n(data.get('low'))}\n"
        f"   Change : {ch_str}\n\n"
        f"📈 Arus   : <b>{_h(data.get('arus'))}</b>\n"
        f"   {_h(data.get('arus_desc'))}\n\n"
        f"📊 S/R\n"
        f"   Puncak : {_n(data.get('puncak'))}\n"
        f"   Lembah : {_n(data.get('lembah'))}\n\n"
        f"{sinyal_text}\n\n"
        f"🕐 {_h(data.get('time'))}\n"
        f"⚠️ Bukan saran finansial."
    )


# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    nama = user.first_name or "Pemburu"
    text = (
        f"Halo <b>{_h(nama)}</b>! 👋\n\n"
        f"Saya <b>TanyaHargaBot</b> — alat untuk pantau harga <b>Gold (XAUUSD)</b>.\n\n"
        f"Pilih menu di bawah:\n"
        f"• 💰 Harga Aktual\n"
        f"• 📐 GT (data faktual dari EA)\n"
        f"• 📈 Arus\n"
        f"• 🎯 Sinyal\n"
        f"• 📊 Puncak & Lembah\n"
        f"• 📰 Isu & Rumor\n"
        f"• 📚 Sistem & Strategi\n"
        f"• 📋 Ringkasan Lengkap\n\n"
        f"Semoga pemburuan saldo-mu menyenangkan 🙏"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=menu_utama())


async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "❓ <b>Bantuan TanyaHargaBot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Menu yang tersedia:</b>\n"
        "💰 <b>Harga Aktual</b> — Harga live + data GT\n"
        "📐 <b>GT</b> — Data faktual dari EA Genesis\n"
        "📈 <b>Arus</b> — Arah pasar (naik/turun/datar)\n"
        "🎯 <b>Sinyal</b> — Sinyal pintar berbasis GT (A–E) + skor + SL/TP ide\n"
        "📊 <b>Puncak & Lembah</b> — Level penting\n"
        "📰 <b>Isu & Rumor</b> — Faktor yang sering gerakkan harga\n"
        "📚 <b>Sistem & Strategi</b> — Panduan sistem pemburuan + rekomendasi dinamis\n"
        "📋 <b>Ringkasan Lengkap</b> — Semua info sekaligus\n\n"
        "<b>Perintah teks:</b>\n"
        "<code>/start /harga /arus /sinyal /pl /isu /strategi /full /help</code>\n\n"
        "Data dari Yahoo Finance / MT5 Genesis.\n"
        "⚠️ Bukan saran finansial. Selalu pakai risk management."
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=menu_utama())


async def kirim_harga(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Mengambil harga gold...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_harga(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {_h(str(e))}", reply_markup=tombol_aksi())


async def kirim_arus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menganalisis arus...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_tren(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {_h(str(e))}", reply_markup=tombol_aksi())


async def kirim_sinyal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menyusun sinyal pintar...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_sinyal(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {_h(str(e))}", reply_markup=tombol_aksi())


async def kirim_pl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menghitung Puncak & Lembah...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_sr(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {_h(str(e))}", reply_markup=tombol_aksi())


async def kirim_isu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(format_isu(), parse_mode="HTML", reply_markup=tombol_aksi())


async def kirim_strategi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menyusun sistem & strategi...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_strategi(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {_h(str(e))}", reply_markup=tombol_aksi())


async def kirim_full(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menyusun ringkasan lengkap...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_full(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {_h(str(e))}", reply_markup=tombol_aksi())


async def kirim_mt5(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Mengambil data GT...")
    try:
        data = await _fetch_data(8)
        await msg.edit_text(format_mt5_genesis(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {_h(str(e))}", reply_markup=tombol_aksi())


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data_key = query.data

    try:
        await query.edit_message_text("⏳ Memproses...")
    except Exception:
        pass

    try:
        if data_key == "isu":
            text = format_isu()
        else:
            data = await _fetch_data(12)
            if data_key == "harga":
                text = format_harga(data)
            elif data_key == "mt5":
                text = format_mt5_genesis(data)
            elif data_key == "arus":
                text = format_tren(data)
            elif data_key == "sinyal":
                text = format_sinyal(data)
            elif data_key == "pl":
                text = format_sr(data)
            elif data_key == "strategi":
                text = format_strategi(data)
            elif data_key == "full":
                text = format_full(data)
            else:
                text = "Perintah tidak dikenali."

        await query.edit_message_text(text, parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        try:
            await query.edit_message_text(f"❌ Gagal memproses: {_h(str(e))}", reply_markup=tombol_aksi())
        except Exception:
            pass


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    text_lower = text.lower()

    if text == "💰 Harga Aktual" or any(k in text_lower for k in ["harga", "price", "berapa"]):
        await kirim_harga(update, context)
    elif text == "📐 GT" or any(k in text_lower for k in ["mt5", "genesis", "broker", "faktual", "gt"]):
        await kirim_mt5(update, context)
    elif text == "📈 Arus" or "arus" in text_lower:
        await kirim_arus(update, context)
    elif text == "🎯 Sinyal" or "sinyal" in text_lower or "signal" in text_lower:
        await kirim_sinyal(update, context)
    elif text == "📊 Puncak & Lembah" or text_lower in ["pl", "s/r"] or "lembah" in text_lower or "puncak" in text_lower:
        await kirim_pl(update, context)
    elif text == "📰 Isu & Rumor" or any(k in text_lower for k in ["isu", "rumor", "berita", "news"]):
        await kirim_isu(update, context)
    elif text == "📚 Sistem & Strategi" or any(k in text_lower for k in ["strategi", "sistem", "strategy", "system"]):
        await kirim_strategi(update, context)
    elif text == "📋 Ringkasan Lengkap" or any(k in text_lower for k in ["full", "lengkap", "ringkas"]):
        await kirim_full(update, context)
    elif text == "❓ Bantuan" or "bantuan" in text_lower or "help" in text_lower:
        await bantuan(update, context)
    else:
        await update.message.reply_text(
            "Pilih menu di bawah atau ketik:\n"
            "💰 Harga · 📐 GT · 📈 Arus · 🎯 Sinyal · 📊 P/L · 📰 Isu · 📚 Strategi · 📋 Lengkap",
            reply_markup=menu_utama(),
        )


async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Mulai bot & tampilkan menu"),
        BotCommand("harga", "Harga aktual gold"),
        BotCommand("mt5", "Data faktual GT"),
        BotCommand("gt", "Data faktual GT"),
        BotCommand("arus", "Analisis arus"),
        BotCommand("sinyal", "Sinyal pintar GT (A-E)"),
        BotCommand("pl", "Puncak & Lembah"),
        BotCommand("isu", "Isu & rumor pasar"),
        BotCommand("strategi", "Sistem & strategi transaksi"),
        BotCommand("full", "Ringkasan lengkap"),
        BotCommand("help", "Bantuan"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
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
    app.add_handler(CommandHandler("gt", kirim_mt5))
    app.add_handler(CommandHandler("arus", kirim_arus))
    app.add_handler(CommandHandler("sinyal", kirim_sinyal))
    app.add_handler(CommandHandler("pl", kirim_pl))
    app.add_handler(CommandHandler("isu", kirim_isu))
    app.add_handler(CommandHandler("strategi", kirim_strategi))
    app.add_handler(CommandHandler("full", kirim_full))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    logger.info("TanyaHargaBot mulai berjalan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
