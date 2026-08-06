# services/signal_engine.py
"""
Engine sinyal pintar berbasis data GT (Genesis Riwayat) penuh.
Sinyal A–E: Momentum Kuat, Pullback, Range, Imbalance, Konvergensi Multi-bar.
"""

from typing import Dict, Any


def _safe_float(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=0):
    try:
        return int(round(float(v))) if v is not None else default
    except (TypeError, ValueError):
        return default


def analisis_gt(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analisis mendalam data GT.
    Mengembalikan dict lengkap untuk decision making.
    """
    raw = data.get("raw") or {}
    gt1 = raw.get("gt1") or {}
    gt2 = raw.get("gt2") or {}
    gt3 = raw.get("gt3") or {}

    # LIVE
    live_neto = _safe_int(data.get("neto") if data.get("neto") is not None else raw.get("neto"))
    live_julat = _safe_int(data.get("julat") if data.get("julat") is not None else raw.get("julat"))
    live_atas = _safe_int(raw.get("ch") if raw.get("ch") is not None else data.get("atas"))
    live_bawah = _safe_int(raw.get("cl") if raw.get("cl") is not None else data.get("bawah"))
    live_price = _safe_float(data.get("price"))
    live_high = _safe_float(data.get("tinggi") or data.get("high") or raw.get("high"))
    live_low = _safe_float(data.get("bawah") or data.get("low") or raw.get("low"))
    live_open = _safe_float(data.get("awal") or data.get("open") or raw.get("open"))
    live_inti = _safe_float(
        data.get("inti") or data.get("close") or raw.get("close") or live_price
    )

    def extract(g):
        return {
            "neto": _safe_int(g.get("neto")),
            "julat": _safe_int(g.get("julat")),
            "high": _safe_float(g.get("high")),
            "low": _safe_float(g.get("low")),
            "open": _safe_float(g.get("open")),
            "close": _safe_float(g.get("close")),
        }

    g1 = extract(gt1)
    g2 = extract(gt2)
    g3 = extract(gt3)

    return {
        "live": {
            "neto": live_neto,
            "julat": live_julat,
            "atas": live_atas,
            "bawah": live_bawah,
            "price": live_price,
            "high": live_high,
            "low": live_low,
            "open": live_open,
            "inti": live_inti,
        },
        "gt1": g1,
        "gt2": g2,
        "gt3": g3,
        "from_mt5": data.get("from_mt5", False),
    }


def buat_sinyal_pintar(data: Dict[str, Any]) -> str:
    """
    Engine sinyal baru berbasis GT penuh.
    Menghasilkan Sinyal A / B / C / D / E + skor + alasan.
    """
    if data.get("error") or not data.get("price"):
        return "⚠️ Data tidak tersedia untuk analisis sinyal."

    a = analisis_gt(data)
    live = a["live"]
    g1 = a["gt1"]
    g2 = a["gt2"]
    g3 = a["gt3"]

    price = live["price"]
    neto = live["neto"]
    julat = live["julat"]
    atas = live["atas"]
    bawah = live["bawah"]

    # Hitung beberapa metrik
    jarak_ke_high = live["high"] - price if live["high"] else 999
    jarak_ke_low = price - live["low"] if live["low"] else 999
    total_wick = atas + bawah if (atas + bawah) > 0 else 1
    imbalance = (atas - bawah) / total_wick  # positif = tekanan jual

    # Skor dasar
    skor = 5
    sinyal = "🟠 TUNGGU"
    tipe = "Netral"
    alasan = []
    arah = None  # "BUY" atau "SELL"

    # ========== SINYAL A : Momentum Kuat ==========
    if abs(neto) >= 8 and abs(g1["neto"]) >= 6 and julat > g1["julat"] * 1.15:
        if neto > 0 and g1["neto"] > 0:
            sinyal = "🟢 SINYAL A – Momentum Kuat BUY"
            tipe = "A"
            arah = "BUY"
            skor = 8 + min(2, (neto // 5))
            alasan.append(f"Neto LIVE +{neto} & GT1 +{g1['neto']} sejalan kuat")
            alasan.append(f"Julat melebar ({julat} vs GT1 {g1['julat']})")
        elif neto < 0 and g1["neto"] < 0:
            sinyal = "🔴 SINYAL A – Momentum Kuat SELL"
            tipe = "A"
            arah = "SELL"
            skor = 8 + min(2, (abs(neto) // 5))
            alasan.append(f"Neto LIVE {neto} & GT1 {g1['neto']} sejalan kuat")
            alasan.append(f"Julat melebar ({julat} vs GT1 {g1['julat']})")

    # ========== SINYAL B : Pullback Berkualitas ==========
    elif (g2["neto"] * g3["neto"] > 0) and abs(g2["neto"]) >= 5:  # trend utama ada
        if g2["neto"] > 0 and neto <= 3 and jarak_ke_low < 15:
            sinyal = "🟢 SINYAL B – Pullback BUY"
            tipe = "B"
            arah = "BUY"
            skor = 7
            alasan.append("Trend utama naik (GT2 & GT3 positif)")
            alasan.append(f"Harga pullback dekat low (jarak {jarak_ke_low:.1f})")
        elif g2["neto"] < 0 and neto >= -3 and jarak_ke_high < 15:
            sinyal = "🔴 SINYAL B – Pullback SELL"
            tipe = "B"
            arah = "SELL"
            skor = 7
            alasan.append("Trend utama turun (GT2 & GT3 negatif)")
            alasan.append(f"Harga pullback dekat high (jarak {jarak_ke_high:.1f})")

    # ========== SINYAL C : Range / Julat Sempit ==========
    elif g1["julat"] < 28 and g2["julat"] < 30 and g3["julat"] < 32:
        if jarak_ke_low < 12:
            sinyal = "🟢 SINYAL C – Range BUY (dekat lembah)"
            tipe = "C"
            arah = "BUY"
            skor = 6
            alasan.append("Julat sempit di 3 bar terakhir → mean reversion")
            alasan.append(f"Harga sangat dekat low ({jarak_ke_low:.1f})")
        elif jarak_ke_high < 12:
            sinyal = "🔴 SINYAL C – Range SELL (dekat puncak)"
            tipe = "C"
            arah = "SELL"
            skor = 6
            alasan.append("Julat sempit di 3 bar terakhir → mean reversion")
            alasan.append(f"Harga sangat dekat high ({jarak_ke_high:.1f})")

    # ========== SINYAL D : Imbalance Tekanan ==========
    elif abs(imbalance) > 0.45 and abs(neto) >= 4:
        if imbalance > 0.45 and neto < 0:  # Atas dominan + neto negatif
            sinyal = "🔴 SINYAL D – Tekanan Jual Kuat"
            tipe = "D"
            arah = "SELL"
            skor = 7
            alasan.append(f"Imbalance Atas dominan ({atas} vs {bawah})")
            alasan.append(f"Neto LIVE {neto} mendukung tekanan jual")
        elif imbalance < -0.45 and neto > 0:
            sinyal = "🟢 SINYAL D – Tekanan Beli Kuat"
            tipe = "D"
            arah = "BUY"
            skor = 7
            alasan.append(f"Imbalance Bawah dominan ({bawah} vs {atas})")
            alasan.append(f"Neto LIVE +{neto} mendukung tekanan beli")

    # ========== SINYAL E : Konvergensi Multi-Bar ==========
    elif (g3["neto"] > 0 and g2["neto"] > 0 and g1["neto"] > 0 and neto > 0) or \
         (g3["neto"] < 0 and g2["neto"] < 0 and g1["neto"] < 0 and neto < 0):
        if neto > 0:
            sinyal = "🟢 SINYAL E – Konvergensi BUY (4 bar sejalan)"
            tipe = "E"
            arah = "BUY"
            skor = 9
        else:
            sinyal = "🔴 SINYAL E – Konvergensi SELL (4 bar sejalan)"
            tipe = "E"
            arah = "SELL"
            skor = 9
        alasan.append("GT3 → GT2 → GT1 → LIVE semuanya searah")
        alasan.append("Konfirmasi momentum multi-bar sangat kuat")

    # Jika tidak ada yang match
    if tipe == "Netral":
        alasan.append("Belum ada kondisi GT yang cukup kuat")
        alasan.append("Tunggu konfirmasi lebih jelas (Neto / Julat / Imbalance)")

    # Susun output
    alasan_text = "\n".join([f"• {a}" for a in alasan])

    # Suggested level sederhana
    if arah == "BUY":
        sl_ide = live["low"] - 5 if live["low"] else price - 15
        tp_ide = live["high"] + 10 if live["high"] else price + 25
    elif arah == "SELL":
        sl_ide = live["high"] + 5 if live["high"] else price + 15
        tp_ide = live["low"] - 10 if live["low"] else price - 25
    else:
        sl_ide = tp_ide = None

    level_text = ""
    if arah:
        level_text = (
            f"\n\n📍 <b>Ide Level:</b>\n"
            f"• Entry  : sekitar ${price:,.2f}\n"
            f"• SL ide : ${sl_ide:,.2f}\n"
            f"• TP ide : ${tp_ide:,.2f}"
        )

    result = (
        f"🎯 <b>{sinyal}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Skor Kekuatan : <b>{skor}/10</b>\n"
        f"Harga         : <b>${price:,.2f}</b>\n"
        f"Neto LIVE     : {neto:+d}   |  Julat: {julat}\n"
        f"Atas/Bawah    : {atas} / {bawah}\n\n"
        f"<b>Alasan berbasis GT:</b>\n{alasan_text}"
        f"{level_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Bukan saran finansial. Selalu gunakan risk management ketat."
    )
    return result
