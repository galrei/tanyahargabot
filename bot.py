#!/usr/bin/env python3
"""
TanyaHargaBot - Versi Bersih + Fitur Tambahan (Stabil)
"""

import os
import sys
import logging
import asyncio
import random
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# Optional chart
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from io import BytesIO
    from telegram import InputFile
    HAS_CHART = True
except ImportError:
    HAS_CHART = False

try:
    from mt5_helper import get_harga_lengkap
except ImportError:
    get_harga_lengkap = None

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN tidak ditemukan di .env")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== DATA PERSISTENCE ====================
DATA_DIR = Path("bot_data")
DATA_DIR.mkdir(exist_ok=True)
ALERTS_FILE = DATA_DIR / "alerts.json"
HISTORY_FILE = DATA_DIR / "history.json"

def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except:
        pass
    return default

def save_json(path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(e)

alerts_db = load_json(ALERTS_FILE, {})
signal_history = load_json(HISTORY_FILE, [])

# ==================== KEYBOARD ====================
def menu_utama():
    keyboard = [
        [KeyboardButton("💰 Harga Aktual"), KeyboardButton("📐 GT")],
        [KeyboardButton("📈 Arus"), KeyboardButton("🎯 Sinyal")],
        [KeyboardButton("📊 Puncak & Lembah"), KeyboardButton("📰 Isu & Rumor")],
        [KeyboardButton("📚 Sistem & Strategi"), KeyboardButton("📋 Ringkasan Lengkap")],
        [KeyboardButton("⚡ Scalping"), KeyboardButton("⏱️ Multi-TF")],
        [KeyboardButton("📅 Kalender"), KeyboardButton("📜 History")],
        [KeyboardButton("🧮 Lot"), KeyboardButton("🔔 Alert")],
        [KeyboardButton("❓ Bantuan")],
    ]
    if HAS_CHART:
        keyboard.insert(4, [KeyboardButton("📉 Chart")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def tombol_aksi():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Harga", callback_data="harga"),
         InlineKeyboardButton("📐 GT", callback_data="mt5")],
        [InlineKeyboardButton("📈 Arus", callback_data="arus"),
         InlineKeyboardButton("🎯 Sinyal", callback_data="sinyal")],
        [InlineKeyboardButton("📊 P/L", callback_data="pl"),
         InlineKeyboardButton("📰 Isu", callback_data="isu")],
        [InlineKeyboardButton("📚 Strategi", callback_data="strategi"),
         InlineKeyboardButton("📋 Lengkap", callback_data="full")],
    ])

def _h(text):
    if text is None:
        return "-"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ==================== DATA ====================
async def _fetch_data(timeout=12.0):
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(loop.run_in_executor(None, get_gold_data), timeout=timeout)
    except asyncio.TimeoutError:
        return {"error": f"Timeout ({timeout:.0f}s)"}
    except Exception as e:
        return {"error": str(e)}

def get_gold_data():
    if get_harga_lengkap:
        try:
            mt5d = get_harga_lengkap("XAUUSD")
            if mt5d and mt5d.get("price"):
                price = mt5d["price"]
                open_p = mt5d.get("open") or mt5d.get("awal")
                high = mt5d.get("high") or mt5d.get("tinggi")
                low = mt5d.get("low") or mt5d.get("bawah")
                change = mt5d.get("neto")
                change_pct = round((change / open_p) * 100, 3) if change and open_p else None
                if change is not None:
                    arus = "NAIK 📈" if change > 0.5 else "TURUN 📉" if change < -0.5 else "DATAR ↔️"
                    arus_desc = "Neto positif" if change > 0.5 else "Neto negatif" if change < -0.5 else "Neto sempit"
                else:
                    arus, arus_desc = "N/A", "Data terbatas"
                return {
                    "price": price, "open": open_p, "high": high, "low": low,
                    "change": change, "change_pct": change_pct, "arus": arus, "arus_desc": arus_desc,
                    "lembah": mt5d.get("lembah") or low, "puncak": mt5d.get("puncak") or high,
                    "mid": mt5d.get("inti"), "neto": change, "inti": mt5d.get("inti"),
                    "julat": mt5d.get("julat"), "time": mt5d.get("time", datetime.now().strftime("%d/%m/%Y %H:%M")),
                    "source": mt5d.get("source", "MT5/Genesis"), "raw": mt5d.get("raw"), "from_mt5": True
                }
        except Exception as e:
            logger.warning(f"MT5 gagal: {e}")

    try:
        ticker = yf.Ticker("GC=F")
        hist = ticker.history(period="5d", interval="1h")
        if hist.empty:
            hist = yf.Ticker("XAUUSD=X").history(period="5d", interval="1h")
        if hist.empty:
            return {"error": "Gagal ambil data"}
        last, prev = hist.iloc[-1], hist.iloc[-2] if len(hist) > 1 else hist.iloc[-1]
        price = float(last["Close"])
        change = price - float(prev["Close"])
        change_pct = (change / float(prev["Close"])) * 100
        closes = hist["Close"].tail(48)
        ma_fast, ma_slow = closes.tail(8).mean(), closes.mean()
        if ma_fast > ma_slow * 1.0005:
            arus, arus_desc = "NAIK ✈️", "Terbang"
        elif ma_fast < ma_slow * 0.9995:
            arus, arus_desc = "TURUN ⚓", "Junam"
        else:
            arus, arus_desc = "DATAR ↔️", "Konsolidasi"
        resistance = float(hist.tail(48)["High"].max())
        support = float(hist.tail(48)["Low"].min())
        return {
            "price": round(price, 2), "open": round(float(last["Open"]), 2),
            "high": round(float(last["High"]), 2), "low": round(float(last["Low"]), 2),
            "change": round(change, 2), "change_pct": round(change_pct, 3),
            "arus": arus, "arus_desc": arus_desc,
            "lembah": round(support, 2), "puncak": round(resistance, 2),
            "mid": round((resistance + support) / 2, 2), "neto": round(change, 2),
            "time": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
            "source": "Yahoo Finance", "from_mt5": False, "hist": hist
        }
    except Exception as e:
        return {"error": str(e)}

def buat_sinyal(data):
    if data.get("error") or not data.get("price"):
        return "⚠️ Data tidak tersedia."
    change = data.get("change_pct") or 0
    arus = data.get("arus", "")
    price = data["price"]
    lembah = data.get("lembah", 0)
    puncak = data.get("puncak", 0)
    if "NAIK" in arus and change > 0.1:
        sinyal, alasan = "🟢 BUY / LONG", f"Arus naik.\n• Masuk ≈ ${price:,.2f}\n• SL di bawah ${lembah:,.2f}\n• TP dekat ${puncak:,.2f}"
    elif "TURUN" in arus and change < -0.1:
        sinyal, alasan = "🔴 SELL / SHORT", f"Arus turun.\n• Masuk ≈ ${price:,.2f}\n• SL di atas ${puncak:,.2f}\n• TP dekat ${lembah:,.2f}"
    else:
        sinyal, alasan = "🟠 TUNGGU", "Arah belum jelas."
    signal_history.insert(0, {"time": datetime.now().strftime("%d/%m %H:%M"), "sinyal": sinyal, "price": price})
    if len(signal_history) > 15:
        signal_history.pop()
    save_json(HISTORY_FILE, signal_history)
    return f"<b>Sinyal:</b> {sinyal}\n\n{alasan}"

# ==================== FORMAT ====================
def format_harga(data):
    if data.get("error"): return f"❌ {data['error']}"
    change = data.get("change")
    change_str = f"{'🟢' if change >= 0 else '🔴'} {change:+.2f}" if change is not None else "-"
    if data.get("change_pct") is not None:
        change_str += f" ({data['change_pct']:+.3f}%)"
    src = data.get("source", "-")
    if "genesis" in str(src).lower(): src = "Genesis EA"
    lines = ["💰 <b>Harga Gold (XAUUSD)</b>", "━━━━━━━━━━━━━━━━━━━━",
             "Harga sekarang", f"Inti : <b>${data['price']:,.2f}</b>"]
    if data.get("open"): lines.append(f"Awal     : ${data['open']:,.2f}")
    if data.get("high"): lines.append(f"Tinggi   : ${data['high']:,.2f}")
    if data.get("low"):  lines.append(f"Rendah   : ${data['low']:,.2f}")
    lines += [f"Perubahan: {change_str}", "━━━━━━━━━━━━━━━━━━━━",
              f"🕐 {_h(data.get('time'))}", f"📡 {_h(src)}"]
    return "\n".join(lines)

def format_mt5_genesis(data):
    if data.get("error"): return f"❌ {data['error']}"
    if not data.get("from_mt5"):
        return "📐 <b>GT</b>\n━━━━━━━━━━━━━━━━━━━━\n❌ Belum ada data EA GT."
    return (f"📐 <b>Data GT</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Harga : <b>${data.get('price',0):,.2f}</b>\n"
            f"Arus  : {data.get('arus')}\n"
            f"Neto  : {data.get('neto')}\n"
            f"Puncak: ${data.get('puncak',0):,.2f}\n"
            f"Lembah: ${data.get('lembah',0):,.2f}\n"
            f"🕐 {_h(data.get('time'))}")

def format_tren(data):
    if data.get("error"): return f"❌ {data['error']}"
    return (f"📈 <b>Arus Gold</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Harga : <b>${data['price']:,.2f}</b>\n"
            f"Arus  : <b>{data['arus']}</b>\n"
            f"{data['arus_desc']}\n"
            f"Perubahan: {data['change']:+.2f} ({data['change_pct']:+.3f}%)")

def format_sinyal(data):
    if data.get("error"): return f"❌ {data['error']}"
    return (f"🎯 <b>Sinyal</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Harga : <b>${data['price']:,.2f}</b>\n"
            f"Arus  : {data['arus']}\n\n{buat_sinyal(data)}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n⚠️ Bukan saran finansial.")

def format_sr(data):
    if data.get("error"): return f"❌ {data['error']}"
    p, lem, pun = data["price"], data["lembah"], data["puncak"]
    return (f"📊 <b>Puncak & Lembah</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Harga : <b>${p:,.2f}</b>\n\n"
            f"🔴 Puncak : ${pun:,.2f} ({((pun-p)/p*100):+.2f}%)\n"
            f"🟢 Lembah : ${lem:,.2f} ({((p-lem)/p*100):+.2f}%)")

def format_isu():
    daftar = [
        "📌 Fed Rate Decision sangat impact ke gold",
        "📌 CPI & NFP AS rutin digarap trader",
        "📌 DXY kuat biasanya tekan harga gold",
        "📌 Geopolitik sering picu safe-haven",
        "📌 Hindari trading saat high-impact news",
    ]
    return "📰 <b>Isu & Rumor</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(random.sample(daftar, 4))

def format_strategi(data=None):
    return ("📚 <b>Sistem & Strategi</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "1. Ikuti arus H1/H4\n2. Tunggu breakout + konfirmasi\n"
            "3. Range: Buy support / Sell resistance\n"
            "4. Risk max 1-2% per trade\n5. Hindari news high-impact\n"
            "━━━━━━━━━━━━━━━━━━━━\n⚠️ Edukasi saja.")

def format_full(data):
    if data.get("error"): return f"❌ {data['error']}"
    return (f"📋 <b>Ringkasan</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Harga : <b>${data.get('price',0):,.2f}</b>\n"
            f"Arus  : {data.get('arus')}\n"
            f"Puncak: ${data.get('puncak',0):,.2f}\n"
            f"Lembah: ${data.get('lembah',0):,.2f}\n\n{buat_sinyal(data)}")

def format_scalping(data):
    if data.get("error"): return f"❌ {data['error']}"
    return (f"⚡ <b>Mode Scalping</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Harga : <b>${data['price']:,.2f}</b>\n"
            f"Arus  : {data.get('arus')}\n"
            f"Neto  : {data.get('neto')}\n\n"
            f"• Target 10-30 poin\n• SL ketat 5-15 poin\n• Fokus M1-M5")

def format_mtf(data):
    if data.get("error"): return f"❌ {data['error']}"
    return (f"⏱️ <b>Multi-Timeframe</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Harga : <b>${data['price']:,.2f}</b>\n"
            f"Arus  : {data.get('arus')}\n"
            f"Puncak: ${data.get('puncak',0):,.2f}\n"
            f"Lembah: ${data.get('lembah',0):,.2f}")

def format_calendar():
    return ("📅 <b>Kalender High-Impact</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            "• CPI (Inflasi AS)\n• Non-Farm Payroll (NFP)\n"
            "• FOMC / The Fed\n• Retail Sales\n• China PMI")

def format_history():
    if not signal_history:
        return "📜 Belum ada history."
    lines = ["📜 <b>History Sinyal</b>\n━━━━━━━━━━━━━━━━━━━━"]
    for h in signal_history[:8]:
        lines.append(f"{h['time']} | {h['sinyal']} @ ${h['price']:,.2f}")
    return "\n".join(lines)

def format_lot(balance, risk_pct, sl):
    risk = balance * risk_pct / 100
    lot = max(0.01, round(risk / (sl * 1), 2))
    return (f"🧮 <b>Kalkulator Lot</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Saldo  : ${balance:,.2f}\nRisiko : {risk_pct}% (${risk:,.2f})\n"
            f"SL     : {sl} poin\n\n<b>Lot disarankan: {lot}</b>")

# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nama = update.effective_user.first_name or "Pemburu"
    await update.message.reply_text(
        f"Halo <b>{nama}</b>!\nSaya TanyaHargaBot (versi stabil + fitur tambahan).\nPilih menu di bawah.",
        parse_mode="HTML", reply_markup=menu_utama()
    )

async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ("❓ <b>Bantuan</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            "<code>/lot 1000 1 30</code> → hitung lot\n"
            "<code>/alert 2650 up</code> → set alert\n"
            "Tombol lain langsung dari keyboard.")
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=menu_utama())

async def kirim(update, context, formatter, loading="⏳ Memproses..."):
    msg = await update.message.reply_text(loading)
    data = await _fetch_data()
    await msg.edit_text(formatter(data), parse_mode="HTML", reply_markup=tombol_aksi())

async def kirim_harga(update, context): await kirim(update, context, format_harga, "⏳ Ambil harga...")
async def kirim_arus(update, context): await kirim(update, context, format_tren, "⏳ Analisis arus...")
async def kirim_sinyal(update, context): await kirim(update, context, format_sinyal, "⏳ Susun sinyal...")
async def kirim_pl(update, context): await kirim(update, context, format_sr, "⏳ Hitung level...")
async def kirim_isu(update, context): await update.message.reply_text(format_isu(), parse_mode="HTML", reply_markup=tombol_aksi())
async def kirim_strategi(update, context): await kirim(update, context, format_strategi)
async def kirim_full(update, context): await kirim(update, context, format_full)
async def kirim_mt5(update, context): await kirim(update, context, format_mt5_genesis, "⏳ Ambil GT...")
async def kirim_scalp(update, context): await kirim(update, context, format_scalping)
async def kirim_mtf(update, context): await kirim(update, context, format_mtf)
async def kirim_calendar(update, context): await update.message.reply_text(format_calendar(), parse_mode="HTML", reply_markup=tombol_aksi())
async def kirim_history(update, context): await update.message.reply_text(format_history(), parse_mode="HTML", reply_markup=tombol_aksi())

async def cmd_lot(update, context):
    try:
        b, r, s = map(float, context.args[:3])
        await update.message.reply_text(format_lot(b, r, s), parse_mode="HTML")
    except:
        await update.message.reply_text("Format: /lot 1000 1 30")

async def cmd_alert(update, context):
    try:
        price = float(context.args[0])
        direction = context.args[1].lower()
        if direction not in ("up", "down"):
            raise ValueError
        cid = str(update.effective_chat.id)
        alerts_db.setdefault(cid, []).append({"price": price, "direction": direction, "active": True})
        save_json(ALERTS_FILE, alerts_db)
        await update.message.reply_text(f"✅ Alert: {direction.upper()} ${price:,.2f}")
    except:
        await update.message.reply_text("Format: /alert 2650 up")

async def button_handler(update, context):
    q = update.callback_query
    await q.answer()
    key = q.data
    try:
        await q.edit_message_text("⏳ ...")
        if key == "isu":
            text = format_isu()
        else:
            data = await _fetch_data()
            func = {
                "harga": format_harga, "mt5": format_mt5_genesis, "arus": format_tren,
                "sinyal": format_sinyal, "pl": format_sr, "strategi": format_strategi, "full": format_full
            }.get(key)
            text = func(data) if func else "Tidak dikenali"
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=tombol_aksi())
    except Exception as e:
        await q.edit_message_text(f"❌ {e}")

async def text_router(update, context):
    t = (update.message.text or "").lower()
    if "harga" in t: await kirim_harga(update, context)
    elif any(x in t for x in ["gt", "mt5", "genesis"]): await kirim_mt5(update, context)
    elif "arus" in t: await kirim_arus(update, context)
    elif "sinyal" in t: await kirim_sinyal(update, context)
    elif any(x in t for x in ["puncak", "lembah", "pl"]): await kirim_pl(update, context)
    elif any(x in t for x in ["isu", "rumor"]): await kirim_isu(update, context)
    elif "strategi" in t: await kirim_strategi(update, context)
    elif any(x in t for x in ["lengkap", "full"]): await kirim_full(update, context)
    elif "scalp" in t: await kirim_scalp(update, context)
    elif any(x in t for x in ["multi", "mtf"]): await kirim_mtf(update, context)
    elif "kalender" in t or "calendar" in t: await kirim_calendar(update, context)
    elif "history" in t: await kirim_history(update, context)
    elif "lot" in t: await update.message.reply_text("Gunakan: /lot 1000 1 30")
    elif "alert" in t: await update.message.reply_text("Gunakan: /alert 2650 up")
    elif "bantuan" in t or "help" in t: await bantuan(update, context)
    else: await update.message.reply_text("Pilih menu.", reply_markup=menu_utama())

async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Mulai"), BotCommand("harga", "Harga"),
        BotCommand("arus", "Arus"), BotCommand("sinyal", "Sinyal"),
        BotCommand("pl", "Puncak/Lembah"), BotCommand("lot", "Kalkulator Lot"),
        BotCommand("alert", "Set Alert"), BotCommand("help", "Bantuan"),
    ])

def main():
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except: pass
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed(): raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

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
    app.add_handler(CommandHandler("lot", cmd_lot))
    app.add_handler(CommandHandler("alert", cmd_alert))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    logger.info("TanyaHargaBot stabil siap...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
