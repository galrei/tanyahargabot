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


def _pick(d: dict, *keys, default=None):
    """Ambil nilai pertama yang tidak None dari beberapa key."""
    for k in keys:
        if d is None:
            break
        v = d.get(k) if isinstance(d, dict) else None
        if v is not None and v != "":
            return v
    return default


def analisis_gt(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analisis mendalam data GT.
    Mengembalikan dict lengkap untuk decision making.
    """
    raw = data.get("raw") or {}
    if not isinstance(raw, dict):
        raw = {}

    gt1 = raw.get("gt1") if isinstance(raw.get("gt1"), dict) else {}
    gt2 = raw.get("gt2") if isinstance(raw.get("gt2"), dict) else {}
    gt3 = raw.get("gt3") if isinstance(raw.get("gt3"), dict) else {}

    # LIVE — prioritaskan field di data, lalu raw
    live_price = _safe_float(_pick(data, "price") or _pick(raw, "price", "close"))
    live_high = _safe_float(
        _pick(data, "tinggi", "high") or _pick(raw, "tinggi", "high")
    )
    live_low = _safe_float(
        _pick(data, "bawah", "low") or _pick(raw, "bawah", "low")
    )
    live_open = _safe_float(
        _pick(data, "awal", "open") or _pick(raw, "awal", "open")
    )
    live_inti = _safe_float(
        _pick(data, "inti", "close") or _pick(raw, "inti", "close") or live_price
    )

    live_neto = _safe_int(
        _pick(data, "neto", "change") if _pick(data, "neto", "change") is not None
        else _pick(raw, "neto", "change")
    )

    # julat bisa bernama julat / jangkauan / range
    live_julat = _safe_int(
        _pick(data, "julat", "jangkauan") if _pick(data, "julat", "jangkauan") is not None
        else _pick(raw, "julat", "jangkauan", "range")
    )
    if live_julat == 0 and live_high and live_low:
        # fallback hitung dari high-low dalam points (asumsi 0.01)
        live_julat = _safe_int((live_high - live_low) / 0.01)

    live_atas = _safe_int(_pick(raw, "ch", "atas") or data.get("atas"))
    live_bawah = _safe_int(_pick(raw, "cl", "bawah_wick") or data.get("bawah_wick"))

    # Hitung atas/bawah dari OHLC jika belum ada
    if (live_atas == 0 and live_bawah == 0) and live_open and live_high and live_low and live_inti:
        body_top = max(live_open, live_inti)
        body_bot = min(live_open, live_inti)
        live_atas = _safe_int((live_high - body_top) / 0.01)
        live_bawah = _safe_int((body_bot - live_low) / 0.01)

    def extract(g):
        if not g:
            return {"neto": 0, "julat": 0, "high": 0.0, "low": 0.0, "open": 0.0, "close": 0.0}
        neto = _safe_int(g.get("neto"))
        julat = _safe_int(g.get("julat") or g.get("jangkauan"))
        high = _safe_float(g.get("high") or g.get("tinggi"))
        low = _safe_float(g.get("low") or g.get("bawah") or g.get("rendah"))
        open_p = _safe_float(g.get("open") or g.get("awal"))
        close = _safe_float(g.get("close") or g.get("inti"))
        if julat == 0 and high and low:
            julat = _safe_int((high - low) / 0.01)
        if neto == 0 and open_p and close:
            neto = _safe_int((close - open_p) / 0.01)
        return {
            "neto": neto,
            "julat": julat,
            "high": high,
            "low": low,
            "open": open_p,
            "close": close,
        }

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
        "gt1": extract(gt1),
        "gt2": extract(gt2),
        "gt3": extract(gt3),
        "from_mt5": bool(data.get("from_mt5")),
        "has_gt_history": bool(gt1 or gt2 or gt3),
        "source": data.get("source", "-"),
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

    jarak_ke_high = live["high"] - price if live["high"] else 999
    jarak_ke_low = price - live["low"] if live["low"] else 999
    total_wick = atas + bawah if (atas + bawah) > 0 else 1
    imbalance = (atas - bawah) / total_wick  # positif = tekanan jual

    skor = 5
    sinyal = "🟠 TUNGGU"
    tipe = "Netral"
    alasan = []
    arah = None

    # ========== SINYAL A : Momentum Kuat ==========
    if abs(neto) >= 8 and abs(g1["neto"]) >= 6 and (
        g1["julat"] == 0 or julat > g1["julat"] * 1.15
    ):
        if neto > 0 and g1["neto"] > 0:
            sinyal = "🟢 SINYAL A – Momentum Kuat BUY"
            tipe = "A"
            arah = "BUY"
            skor = 8 + min(2, max(0, neto // 5))
            alasan.append(f"Neto LIVE +{neto} & GT1 +{g1['neto']} sejalan kuat")
            if g1["julat"]:
                alasan.append(f"Julat melebar ({julat} vs GT1 {g1['julat']})")
            else:
                alasan.append(f"Julat LIVE {julat} poin")
        elif neto < 0 and g1["neto"] < 0:
            sinyal = "🔴 SINYAL A – Momentum Kuat SELL"
            tipe = "A"
            arah = "SELL"
            skor = 8 + min(2, max(0, abs(neto) // 5))
            alasan.append(f"Neto LIVE {neto} & GT1 {g1['neto']} sejalan kuat")
            if g1["julat"]:
                alasan.append(f"Julat melebar ({julat} vs GT1 {g1['julat']})")
            else:
                alasan.append(f"Julat LIVE {julat} poin")

    # ========== SINYAL B : Pullback Berkualitas ==========
    elif (g2["neto"] * g3["neto"] > 0) and abs(g2["neto"]) >= 5:
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
    elif (
        (g1["julat"] > 0 and g1["julat"] < 28)
        and (g2["julat"] == 0 or g2["julat"] < 30)
        and (g3["julat"] == 0 or g3["julat"] < 32)
    ) or (julat > 0 and julat < 25 and not a["has_gt_history"]):
        if jarak_ke_low < 12:
            sinyal = "🟢 SINYAL C – Range BUY (dekat lembah)"
            tipe = "C"
            arah = "BUY"
            skor = 6
            alasan.append("Julat sempit → mean reversion")
            alasan.append(f"Harga sangat dekat low ({jarak_ke_low:.1f})")
        elif jarak_ke_high < 12:
            sinyal = "🔴 SINYAL C – Range SELL (dekat puncak)"
            tipe = "C"
            arah = "SELL"
            skor = 6
            alasan.append("Julat sempit → mean reversion")
            alasan.append(f"Harga sangat dekat high ({jarak_ke_high:.1f})")

    # ========== SINYAL D : Imbalance Tekanan ==========
    elif abs(imbalance) > 0.45 and abs(neto) >= 4:
        if imbalance > 0.45 and neto < 0:
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
    elif (g3["neto"] > 0 and g2["neto"] > 0 and g1["neto"] > 0 and neto > 0) or (
        g3["neto"] < 0 and g2["neto"] < 0 and g1["neto"] < 0 and neto < 0
    ):
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

    # Fallback sederhana jika hanya LIVE (tanpa history GT)
    if tipe == "Netral" and abs(neto) >= 10:
        if neto > 0:
            sinyal = "🟢 SINYAL DASAR – Neto kuat BUY"
            tipe = "Dasar"
            arah = "BUY"
            skor = 6
            alasan.append(f"Neto LIVE +{neto} cukup kuat (tanpa konfirmasi multi-bar)")
        else:
            sinyal = "🔴 SINYAL DASAR – Neto kuat SELL"
            tipe = "Dasar"
            arah = "SELL"
            skor = 6
            alasan.append(f"Neto LIVE {neto} cukup kuat (tanpa konfirmasi multi-bar)")

    if tipe == "Netral":
        alasan.append("Belum ada kondisi GT yang cukup kuat")
        if not a["has_gt_history"]:
            alasan.append("Data GT1/GT2/GT3 belum tersedia — pastikan EA Genesis aktif")
        else:
            alasan.append("Tunggu konfirmasi lebih jelas (Neto / Julat / Imbalance)")

    alasan_text = "\n".join([f"• {x}" for x in alasan])

    if arah == "BUY":
        sl_ide = (live["low"] - 5) if live["low"] else price - 15
        tp_ide = (live["high"] + 10) if live["high"] else price + 25
    elif arah == "SELL":
        sl_ide = (live["high"] + 5) if live["high"] else price + 15
        tp_ide = (live["low"] - 10) if live["low"] else price - 25
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

    src = a.get("source") or data.get("source") or "-"
    if "genesis" in str(src).lower() or a["from_mt5"]:
        src_label = "Genesis EA / MT5"
    else:
        src_label = str(src)

    gt_status = "✅ GT1–GT3 tersedia" if a["has_gt_history"] else "⚠️ Hanya LIVE (tanpa riwayat GT)"

    result = (
        f"🎯 <b>{sinyal}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Skor Kekuatan : <b>{skor}/10</b>\n"
        f"Harga         : <b>${price:,.2f}</b>\n"
        f"Neto LIVE     : {neto:+d}   |  Julat: {julat}\n"
        f"Atas/Bawah    : {atas} / {bawah}\n"
        f"Data          : {gt_status}\n"
        f"Sumber        : {_h_src(src_label)}\n\n"
        f"<b>Alasan berbasis GT:</b>\n{alasan_text}"
        f"{level_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Bukan saran finansial. Selalu gunakan risk management ketat."
    )
    return result


def _h_src(text) -> str:
    if text is None:
        return "-"
    s = str(text)
    return s.replace("&", "&").replace("<", "<").replace(">", ">")
