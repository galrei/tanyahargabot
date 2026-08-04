#!/usr/bin/env python3
"""
TanyaHargaBot - Teman trader gold (XAUUSD) di MT5
Menu lengkap: harga aktual, tren, sinyal, support/resistance, isu/rumor, ringkasan, sistem & strategi
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
        [KeyboardButton("💰 Harga Aktual"), KeyboardButton("📐 GT")],
        [KeyboardButton("📈 Tren"), KeyboardButton("🎯 Sinyal")],
        [KeyboardButton("📊 Support / Resistance"), KeyboardButton("📰 Isu & Rumor")],
        [KeyboardButton("📚 Sistem & Strategi"), KeyboardButton("📋 Ringkasan Lengkap")],
        [KeyboardButton("❓ Bantuan")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def tombol_aksi() -> InlineKeyboardMarkup:
    """Tombol cepat setelah melihat hasil."""
    keyboard = [
        [
            InlineKeyboardButton("💰 Harga", callback_data="harga"),
            InlineKeyboardButton("📐 GT", callback_data="mt5"),
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
            InlineKeyboardButton("📚 Strategi", callback_data="strategi"),
            InlineKeyboardButton("📋 Lengkap", callback_data="full"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _h(text) -> str:
    """Escape HTML untuk teks dinamis (aman di parse_mode HTML)."""
    if text is None:
        return "-"
    s = str(text)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _md(text: str) -> str:
    """Escape karakter yang merusak Telegram Markdown legacy."""
    if text is None:
        return "-"
    s = str(text)
    for ch in ("_", "*", "`", "["):
        s = s.replace(ch, "\\" + ch)
    return s


# ==================== DATA HARGA ====================

async def _fetch_data(timeout: float = 12.0) -> Dict[str, Any]:
    """Ambil data di thread terpisah supaya bot tidak freeze, dengan timeout."""
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

    # Fallback Yahoo Finance
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
            trend, trend_desc = "NAIK ✈️", "Terbang — harga di atas MA"
        elif ma_fast < ma_slow * 0.9995:
            trend, trend_desc = "TURUN ⚓", "Junam — harga di bawah MA"
        else:
            trend, trend_desc = "DATAR ↔️", "Konsolidasi — arah belum jelas"

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
            "julat": round(high - low, 2),
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

    return f"<b>Sinyal:</b> {sinyal}\n\n{alasan}"


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


# ==================== SISTEM & STRATEGI (FITUR BARU) ====================
def format_strategi(data: Dict[str, Any] = None) -> str:
    """Fitur baru: Sistem & Strategi Trading Gold."""
    if data is None:
        data = {}

    # Rekomendasi dinamis berdasarkan tren saat ini
    rekomendasi = ""
    if data and not data.get("error") and data.get("trend"):
        trend = data.get("trend", "")
        price = data.get("price", 0)
        support = data.get("support", 0)
        resistance = data.get("resistance", 0)

        if "NAIK" in trend:
            rekomendasi = (
                f"\n🟢 <b>Rekomendasi saat ini (Arus NAIK):</b>\n"
                f"• Utamakan <b>Ikut golongan Neto naik / Ayunan ke bawah Buy</b>\n"
                f"• Masuk transaksi ideal: Mendekati perhentian bawah / MA\n"
                f"• Hindari melawan arus dengan sell agresif\n"
                f"• Target: dekat perhentian atas (pa) ${resistance:,.2f}"
            )
        elif "TURUN" in trend:
            rekomendasi = (
                f"\n🔴 <b>Rekomendasi saat ini (Arus TURUN):</b>\n"
                f"• Utamakan <b>Ikut golongan Neto turun / Ayunan ke atas Sell</b>\n"
                f"• Masuk transaksi ideal: Mendekati perhentian atas / MA\n"
                f"• Hindari melawan arus dengan buy agresif\n"
                f"• Target: dekat perhentian bawah (pb) ${support:,.2f}"
            )
        else:
            rekomendasi = (
                f"\n🟠 <b>Rekomendasi saat ini (MENDATAR):</b>\n"
                f"• Utamakan <b>Pesaldo Julat / Gelombang Rata</b>\n"
                f"• Buy dekat perhentian bawah dan rendah, Sell dekat perhentian atas dan tinggi\n"
                f"• Atau tunggu trobosan yang jelas (konfirmasi volume/momentum)\n"
                f"• Hindari masuk secara tergesa-gesa di tengah gelombang"
            )

    text = (
        "📚 <b>Sistem & Strategi Pesaldo Gold (XAUUSD)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>1. Sistem Mengikuti Arus</b>\n"
        "• Ikuti arah arus utama (H1/H4/D1)\n"
        "• Masuk: harga saat mundur naik atau turun / perhentian bawah-atas dinamis\n"
        "• SL: di luar struktur terakhir\n"
        "• Cocok saat pasar berarus kuat\n\n"
        "<b>2. Strategi Trobosan</b>\n"
        "• Tunggu harga menembus dengan jelas perhentian bawah/atas\n"
        "• Konfirmasi: GT kuat + volume/momentum\n"
        "• Masuk setelah pengujian (lebih aman)\n"
        "• SL: di dalam level yang ditembus\n\n"
        "<b>3. Strategi Bergelombang (Julat)</b>\n"
        "• Buy di perhentian bawah, Sell di perhentian atas\n"
        "• Target: harga tengah atau sisi lawan\n"
        "• Sangat cocok saat GT menunjukkan julat sempit / mendatar\n\n"
        "<b>4. Mancing dengan Data GT</b>\n"
        "• Gunakan tabel GT (Atas/Bawah/Neto/Julat)\n"
        "• Entry cepat di M1-M5 saat neto jelas + harga di ekstrem\n"
        "• Risk sangat ketat (5-15 poin)\n\n"
        "<b>5. Risk Management (WAJIB)</b>\n"
        "• Risk per transaksi maksimal 1–2% equity\n"
        "• Risk:Reward minimal 1:1.5 atau 1:2\n"
        "• Jangan berlayer minus tanpa sistem\n"
        "• Hindari transaksi 15 menit sebelum/setelah high-impact news\n\n"
        "<b>6. Uang Waktu yang Paling Aktif Gold</b>\n"
        "• London (Buka 14:00 WIB) & New York (Buka 19:30–20:00 WIB)\n"
        "• Volatilitas tertinggi → peluang terbaik + risiko tertinggi\n"
        f"{rekomendasi}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <i>Ini hanya edukasi & ide. Bukan saran finansial. "
        "Selalu sesuaikan dengan gaya pesaldo & pengaturan risiko-mu sendiri.</i>"
    )
    return text


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

    # Sumber tampilan: ganti nama file jadi "kebun saldo"
    src_label = data.get("source", "-")
    if src_label and "genesis_data" in str(src_label).lower():
        src_label = "Genesis EA (kebun saldo)"
    elif src_label and "Genesis EA" in str(src_label):
        src_label = "Genesis EA (kebun saldo)"

    lines = [
        "💰 <b>Harga Gold (XAUUSD)</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Harga sekarang/Inti : <b>${data['price']:,.2f}</b>",
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
    """Tampilkan data faktual GT (tabel rapi seperti dashboard EA)."""
    if data.get("error"):
        return f"❌ {_h(data['error'])}"

    if not data.get("from_mt5") and not data.get("raw"):
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

    raw = data.get("raw") or {}

    def num(v, digits=2):
        if v is None:
            return "-"
        try:
            return f"{float(v):,.{digits}f}"
        except Exception:
            return str(v)

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
        """
        Atas  = poin kolom atas (high - max(open,close))
                neto+ : inti→tinggi | neto- : awal→tinggi
        Bawah = poin kolom bawah (min(open,close) - low)
                neto+ : awal→rendah | neto- : inti→rendah
        """
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

    live_open = data.get("awal") or data.get("open") or raw.get("open")
    live_high = data.get("tinggi") or data.get("high") or raw.get("high")
    live_low = data.get("bawah") or data.get("low") or raw.get("low")
    live_close = data.get("inti") or data.get("close") or raw.get("close")
    live_neto = data.get("neto") if data.get("neto") is not None else raw.get("neto")
    live_range = data.get("julat") if data.get("julat") is not None else raw.get("julat")

    # Atas/Bawah LIVE: pakai ch/cl dari EA jika ada, else hitung
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
        # hitung dari OHLC bar
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
    rows.append("           GT3      GT2      GT1     LIVE")
    rows.append("──────── ──────── ──────── ──────── ────────")
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
    # PERIOD_M1 → M1
    tf_raw = str(raw.get("timeframe") or "-")
    if tf_raw.startswith("PERIOD_"):
        tf_raw = tf_raw.replace("PERIOD_", "", 1)
    tf = _h(tf_raw)
    waktu = _h(data.get("time") or raw.get("time") or "-")
    sumber_raw = data.get("source") or "Genesis EA (kebun saldo)"
    if "genesis_data" in str(sumber_raw).lower() or "Genesis EA" in str(sumber_raw):
        sumber_raw = "Genesis EA (kebun saldo)"
    sumber = _h(sumber_raw)

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

    # Format Symbol P/L
    if symbol_pl is not None:
        try:
            pl_v = float(symbol_pl)
            pl_pts = int(symbol_pl_pts) if symbol_pl_pts is not None else 0
            if pl_v > 0.005:
                pl_str = f"+{pl_v:,.2f} (+{pl_pts} pts)"
            elif pl_v < -0.005:
                pl_str = f"{pl_v:,.2f} ({pl_pts} pts)"
            else:
                pl_str = f"{pl_v:,.2f} (0 pts)"
        except Exception:
            pl_str = str(symbol_pl)
    else:
        pl_str = "-"

    text = (
        f"📐 <b>Data Faktual GT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Simbol  : <b>{simbol}</b>  |  TF: {tf}\n"
        f"Harga   : <b>${harga}</b>\n"
        f"Bid/Ask : ${bid} / ${ask}\n"
        f"Spread  : {spread if spread is not None else '-'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Genesis Riwayat Angka Faktual Informasi Keuangan</b>\n"
        f"<i>Tinggi · Atas · Bawah · Rendah · Awal · Neto · Inti · Julat</i>\n"
        f"<pre>{table}</pre>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Posisi &amp; Akun</b>\n"
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
        return f"❌ {data['error']}"
    return (
        f"📈 <b>Analisis Tren Gold</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga   : <b>${data['price']:,.2f}</b>\n"
        f"Tren    : <b>{data['trend']}</b>\n"
        f"Keterangan : {data['trend_desc']}\n"
        f"Perubahan  : {data['change']:+.2f} ({data['change_pct']:+.3f}%)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Berdasarkan Moving Average periode pendek vs panjang.</i>"
    )


def format_sinyal(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    sinyal_text = buat_sinyal(data)
    return (
        f"🎯 <b>Sinyal Trading Gold</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga : <b>${data['price']:,.2f}</b>\n"
        f"Tren  : {data['trend']}\n\n"
        f"{sinyal_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Bukan saran finansial. Gunakan risk management.</i>"
    )


def format_sr(data: Dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    price = data["price"]
    sup = data["support"]
    res = data["resistance"]
    mid = data["mid"]
    return (
        f"📊 <b>Support & Resistance</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Harga sekarang : <b>${price:,.2f}</b>\n\n"
        f"🔴 Resistance  : <b>${res:,.2f}</b>\n"
        f"   Jarak       : {((res - price) / price * 100):+.2f}%\n\n"
        f"⚪ Midpoint    : ${mid:,.2f}\n\n"
        f"🟢 Support     : <b>${sup:,.2f}</b>\n"
        f"   Jarak       : {((price - sup) / price * 100):+.2f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Dihitung dari high/low 48 GT terakhir.</i>"
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
    sinyal_text = buat_sinyal(data)
    def n(v, fmt="{:,.2f}"):
        if v is None:
            return "-"
        try:
            return fmt.format(float(v))
        except Exception:
            return str(v)
    ch = data.get("change")
    cp = data.get("change_pct")
    ch_str = f"{ch:+.2f}" if ch is not None else "-"
    if cp is not None:
        ch_str += f" ({cp:+.3f}%)"
    return (
        f"📋 <b>Ringkasan Lengkap Gold (XAUUSD)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Harga  : <b>${n(data.get('price'))}</b>\n"
        f"   Open   : ${n(data.get('open'))}\n"
        f"   High   : ${n(data.get('high'))}\n"
        f"   Low    : ${n(data.get('low'))}\n"
        f"   Change : {ch_str}\n\n"
        f"📈 Tren   : <b>{_h(data.get('trend'))}</b>\n"
        f"   {_h(data.get('trend_desc'))}\n\n"
        f"📊 S/R\n"
        f"   Resistance : ${n(data.get('resistance'))}\n"
        f"   Support    : ${n(data.get('support'))}\n\n"
        f"{sinyal_text}\n\n"
        f"🕐 {_h(data.get('time'))}\n"
        f"⚠️ Bukan saran finansial."
    )


# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    nama = user.first_name or "Trader"
    text = (
        f"Halo <b>{nama}</b>! 👋\n\n"
        f"Saya <b>TanyaHargaBot</b> — temanmu untuk pantau harga <b>Gold (XAUUSD)</b>.\n\n"
        f"Pilih menu di bawah:\n"
        f"• 💰 Harga Aktual\n"
        f"• 📐 GT (data faktual dari EA)\n"
        f"• 📈 Tren\n"
        f"• 🎯 Sinyal\n"
        f"• 📊 Support / Resistance\n"
        f"• 📰 Isu & Rumor\n"
        f"• 📚 Sistem & Strategi\n"
        f"• 📋 Ringkasan Lengkap\n\n"
        f"Semoga trading-mu cuan 🙏"
    )
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=menu_utama(),
    )


async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "❓ <b>Bantuan TanyaHargaBot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Menu yang tersedia:</b>\n"
        "💰 <b>Harga Aktual</b> — Harga live + TABRANIJ\n"
        "📐 <b>GT</b> — Data faktual dari EA Genesis\n"
        "📈 <b>Tren</b> — Arah pasar (bullish/bearish/sideways)\n"
        "🎯 <b>Sinyal</b> — Ide entry sederhana + SL/TP\n"
        "📊 <b>Support / Resistance</b> — Level penting\n"
        "📰 <b>Isu & Rumor</b> — Faktor yang sering gerakkan harga\n"
        "📚 <b>Sistem & Strategi</b> — Panduan sistem trading + rekomendasi dinamis\n"
        "📋 <b>Ringkasan Lengkap</b> — Semua info sekaligus\n\n"
        "<b>Perintah teks:</b>\n"
        "<code>/start /harga /tren /sinyal /sr /isu /strategi /full /help</code>\n\n"
        "Data dari Yahoo Finance / MT5 Genesis.\n"
        "⚠️ Bukan saran finansial. Selalu pakai risk management."
    )
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=menu_utama(),
    )


async def kirim_harga(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Mengambil harga gold...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_harga(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {e}", reply_markup=tombol_aksi())


async def kirim_tren(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menganalisis tren...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_tren(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {e}", reply_markup=tombol_aksi())


async def kirim_sinyal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menyusun sinyal...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_sinyal(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {e}", reply_markup=tombol_aksi())


async def kirim_sr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menghitung Support & Resistance...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_sr(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {e}", reply_markup=tombol_aksi())


async def kirim_isu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        format_isu(),
        parse_mode="HTML",
        reply_markup=tombol_aksi(),
    )


async def kirim_strategi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler fitur baru Sistem & Strategi."""
    msg = await update.message.reply_text("⏳ Menyusun sistem & strategi...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_strategi(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {e}", reply_markup=tombol_aksi())


async def kirim_full(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Menyusun ringkasan lengkap...")
    try:
        data = await _fetch_data(12)
        await msg.edit_text(format_full(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {e}", reply_markup=tombol_aksi())


async def kirim_mt5(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Mengambil data GT...")
    try:
        data = await _fetch_data(8)
        await msg.edit_text(format_mt5_genesis(data), parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await msg.edit_text(f"❌ Gagal: {e}", reply_markup=tombol_aksi())


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
            elif data_key == "tren":
                text = format_tren(data)
            elif data_key == "sinyal":
                text = format_sinyal(data)
            elif data_key == "sr":
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
            await query.edit_message_text(f"❌ Gagal memproses: {e}", reply_markup=tombol_aksi())
        except Exception:
            pass


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tangani tombol keyboard + kata kunci bebas."""
    text = (update.message.text or "").strip()
    text_lower = text.lower()

    # Tombol keyboard
    if text == "💰 Harga Aktual" or any(k in text_lower for k in ["harga", "price", "berapa"]):
        await kirim_harga(update, context)
    elif text == "📐 GT" or any(k in text_lower for k in ["mt5", "genesis", "broker", "faktual", "gt"]):
        await kirim_mt5(update, context)
    elif text == "📈 Tren" or "tren" in text_lower or "trend" in text_lower:
        await kirim_tren(update, context)
    elif text == "🎯 Sinyal" or "sinyal" in text_lower or "signal" in text_lower:
        await kirim_sinyal(update, context)
    elif text == "📊 Support / Resistance" or text_lower in ["sr", "s/r"] or "support" in text_lower or "resistance" in text_lower:
        await kirim_sr(update, context)
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
            "💰 Harga · 📐 GT · 📈 Tren · 🎯 Sinyal · 📊 S/R · 📰 Isu · 📚 Strategi · 📋 Lengkap",
            reply_markup=menu_utama(),
        )


async def post_init(application: Application) -> None:
    """Set command list di menu Telegram."""
    commands = [
        BotCommand("start", "Mulai bot & tampilkan menu"),
        BotCommand("harga", "Harga aktual gold"),
        BotCommand("mt5", "Data faktual GT"),
        BotCommand("gt", "Data faktual GT"),
        BotCommand("tren", "Analisis tren"),
        BotCommand("sinyal", "Sinyal trading"),
        BotCommand("sr", "Support & Resistance"),
        BotCommand("isu", "Isu & rumor pasar"),
        BotCommand("strategi", "Sistem & strategi trading"),
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
    app.add_handler(CommandHandler("gt", kirim_mt5))
    app.add_handler(CommandHandler("tren", kirim_tren))
    app.add_handler(CommandHandler("sinyal", kirim_sinyal))
    app.add_handler(CommandHandler("sr", kirim_sr))
    app.add_handler(CommandHandler("isu", kirim_isu))
    app.add_handler(CommandHandler("strategi", kirim_strategi))
    app.add_handler(CommandHandler("full", kirim_full))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    logger.info("TanyaHargaBot mulai berjalan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
