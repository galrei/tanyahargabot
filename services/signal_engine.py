# services/signal_engine.py
# Genesis GT Signal Engine - format dashboard 100% sesuai spesifikasi

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
import math


# ─────────────────────────────────────────────
# HELPER FORMAT (wajib dipakai di semua menu)
# ─────────────────────────────────────────────

def _n(v: Any, decimals: int = 2) -> str:
    """Harga: 4244.22 (tanpa koma, tanpa $)"""
    if v is None:
        return "—"
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _pts(v: Any) -> str:
    """Atas / Bawah / Julat: angka bulat positif murni (tanpa tanda)"""
    if v is None:
        return "—"
    try:
        return str(abs(int(round(float(v)))))
    except (TypeError, ValueError):
        return "—"


def _neto(v: Any) -> str:
    """
    Neto: 588 ▲  atau  147 ▼
    - Angka selalu positif
    - ▲ = naik (positif)
    - ▼ = turun (negatif)
    """
    if v is None:
        return "—"
    try:
        n = int(round(float(v)))
        if n > 0:
            return f"{n} ▲"
        if n < 0:
            return f"{abs(n)} ▼"
        return "0"
    except (TypeError, ValueError):
        return "—"


def _h(text: Any) -> str:
    """HTML escape aman untuk Telegram"""
    if text is None:
        return ""
    s = str(text)
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


# ─────────────────────────────────────────────
# ANALISIS GT (dari genesis_data.json / raw dict)
# ─────────────────────────────────────────────

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def analisis_gt(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Menerima dict full dari genesis_data.json atau hasil get_gold_data().
    Menghasilkan struktur siap pakai untuk semua format_*.
    """
    if not raw:
        return {}

    # Ambil data GT3 / GT2 / GT1 / LIVE
    def pick(prefix: str) -> Dict[str, float]:
        # support beberapa gaya key dari EA
        mapping = {
            "tinggi":  [f"{prefix}_tinggi", f"{prefix}_high", f"{prefix}_ch", "tinggi", "high"],
            "atas":    [f"{prefix}_atas", f"{prefix}_up", "atas"],
            "bawah":   [f"{prefix}_bawah", f"{prefix}_down", "bawah"],
            "rendah":  [f"{prefix}_rendah", f"{prefix}_low", f"{prefix}_cl", "rendah", "low"],
            "awal":    [f"{prefix}_awal", f"{prefix}_open", "awal", "open"],
            "neto":    [f"{prefix}_neto", f"{prefix}_net", "neto"],
            "inti":    [f"{prefix}_inti", f"{prefix}_mid", "inti"],
            "julat":   [f"{prefix}_julat", f"{prefix}_range", f"{prefix}_jangkauan", "julat", "range"],
        }
        out = {}
        for key, candidates in mapping.items():
            val = None
            for c in candidates:
                if c in raw and raw[c] is not None:
                    val = raw[c]
                    break
            out[key] = _safe_float(val)
        return out

    gt3 = pick("gt3")
    gt2 = pick("gt2")
    gt1 = pick("gt1")
    live = pick("live") or pick("gt_live") or pick("")

    # fallback live dari harga realtime
    if not any(live.values()):
        bid = _safe_float(raw.get("bid") or raw.get("price") or raw.get("close"))
        high = _safe_float(raw.get("high") or raw.get("h"))
        low = _safe_float(raw.get("low") or raw.get("l"))
        open_ = _safe_float(raw.get("open") or raw.get("o"))
        live = {
            "tinggi": high or bid,
            "atas":   max(0, (high - open_) * 100) if high and open_ else 0,  # poin kasar
            "bawah":  max(0, (open_ - low) * 100) if open_ and low else 0,
            "rendah": low or bid,
            "awal":   open_ or bid,
            "neto":   (bid - open_) * 100 if bid and open_ else 0,
            "inti":   (high + low) / 2 if high and low else bid,
            "julat":  abs(high - low) * 100 if high and low else 0,
        }

    # waktu live
    waktu = raw.get("waktu") or raw.get("time") or raw.get("live_time") or "—"

    return {
        "gt3": gt3,
        "gt2": gt2,
        "gt1": gt1,
        "live": live,
        "waktu": str(waktu),
        "bid": _safe_float(raw.get("bid") or raw.get("price")),
        "ask": _safe_float(raw.get("ask")),
        "raw": raw,
    }


# ─────────────────────────────────────────────
# SINYAL PINTAR A–E
# ─────────────────────────────────────────────

def buat_sinyal_pintar(analisis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Menghasilkan sinyal A–E berdasarkan GT1/GT2/GT3/LIVE.
    Return dict siap ditampilkan.
    """
    if not analisis:
        return {"kode": "—", "arah": "NETRAL", "alasan": "Data GT kosong", "score": 0}

    gt3 = analisis.get("gt3", {})
    gt2 = analisis.get("gt2", {})
    gt1 = analisis.get("gt1", {})
    live = analisis.get("live", {})

    score = 0
    alasan = []

    # 1. Neto LIVE vs GT1
    neto_live = live.get("neto", 0)
    neto_gt1 = gt1.get("neto", 0)
    if neto_live > 0 and neto_gt1 > 0:
        score += 2
        alasan.append("Neto LIVE & GT1 positif")
    elif neto_live < 0 and neto_gt1 < 0:
        score -= 2
        alasan.append("Neto LIVE & GT1 negatif")

    # 2. Inti vs Awal
    if live.get("inti", 0) > live.get("awal", 0):
        score += 1
        alasan.append("Inti di atas Awal")
    elif live.get("inti", 0) < live.get("awal", 0):
        score -= 1
        alasan.append("Inti di bawah Awal")

    # 3. Julat (volatilitas)
    julat = live.get("julat", 0)
    if julat > 600:
        score += 1 if score >= 0 else -1
        alasan.append(f"Julat tinggi ({_pts(julat)})")

    # 4. Atas vs Bawah LIVE
    atas = live.get("atas", 0)
    bawah = live.get("bawah", 0)
    if atas > bawah * 1.3:
        score += 1
        alasan.append("Atas dominan")
    elif bawah > atas * 1.3:
        score -= 1
        alasan.append("Bawah dominan")

    # Tentukan kode sinyal
    if score >= 4:
        kode, arah = "A", "BUY KUAT"
    elif score >= 2:
        kode, arah = "B", "BUY"
    elif score <= -4:
        kode, arah = "E", "SELL KUAT"
    elif score <= -2:
        kode, arah = "D", "SELL"
    else:
        kode, arah = "C", "NETRAL / TUNGGU"

    return {
        "kode": kode,
        "arah": arah,
        "score": score,
        "alasan": " · ".join(alasan) if alasan else "Kondisi seimbang",
        "neto_live": neto_live,
        "julat": julat,
        "atas": atas,
        "bawah": bawah,
    }


# ─────────────────────────────────────────────
# FORMAT TABEL GT (persis gambar)
# ─────────────────────────────────────────────

def format_gt_table(analisis: Dict[str, Any]) -> str:
    """
    Output HTML Telegram yang 100% mirip dashboard Genesis.
    """
    gt3 = analisis.get("gt3", {})
    gt2 = analisis.get("gt2", {})
    gt1 = analisis.get("gt1", {})
    live = analisis.get("live", {})
    waktu = analisis.get("waktu", "—")

    def row(label: str, key: str, formatter=_n) -> str:
        return (
            f"<b>{_h(label)}</b>  "
            f"{formatter(gt3.get(key))}  "
            f"{formatter(gt2.get(key))}  "
            f"{formatter(gt1.get(key))}  "
            f"<b>{formatter(live.get(key))}</b>"
        )

    lines = [
        "<b>Genesis Riwayat Angka Faktual Informasi Keuangan</b>",
        "",
        "<code>[ GT3 ]   [ GT2 ]   [ GT1 ]   [ GT LIVE ]</code>",
        f"⏰  {_h(waktu)}",
        "",
        row("Tinggi", "tinggi", _n),
        row("Atas",   "atas",   _pts),
        row("Bawah",  "bawah",  _pts),
        row("Rendah", "rendah", _n),
        row("Awal",   "awal",   _n),
        row("Neto",   "neto",   _neto),
        row("Inti",   "inti",   _n),
        row("Julat",  "julat",  _pts),
        "",
        "<i>Sumber: Genesis EA · Kebun Saldo</i>",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# FORMAT LAIN (Harga, Sinyal, Arus, Puncak, Full)
# ─────────────────────────────────────────────

def format_harga(analisis: Dict[str, Any], extra: Optional[Dict] = None) -> str:
    """Menu 💰 Harga – Harga Live M1 + GT"""
    bid = analisis.get("bid") or analisis.get("live", {}).get("inti")
    live = analisis.get("live", {})

    lines = [
        "<b>Harga Live M1</b>",
        f"Bid   {_n(bid)}",
        f"High  {_n(live.get('tinggi'))}",
        f"Low   {_n(live.get('rendah'))}",
        f"Open  {_n(live.get('awal'))}",
        "",
        format_gt_table(analisis),
    ]
    return "\n".join(lines)


def format_sinyal(analisis: Dict[str, Any]) -> str:
    """Menu sinyal pintar A–E"""
    sinyal = buat_sinyal_pintar(analisis)
    live = analisis.get("live", {})

    emoji = {
        "A": "🟢",
        "B": "🟢",
        "C": "⚪",
        "D": "🔴",
        "E": "🔴",
    }.get(sinyal["kode"], "⚪")

    lines = [
        f"<b>Sinyal {sinyal['kode']} {emoji} {sinyal['arah']}</b>",
        f"Score   : {sinyal['score']}",
        f"Alasan  : {_h(sinyal['alasan'])}",
        "",
        f"Neto LIVE : {_neto(live.get('neto'))}",
        f"Atas      : {_pts(live.get('atas'))}",
        f"Bawah     : {_pts(live.get('bawah'))}",
        f"Julat     : {_pts(live.get('julat'))}",
        "",
        format_gt_table(analisis),
    ]
    return "\n".join(lines)


def format_arus(analisis: Dict[str, Any]) -> str:
    """Menu Arus (arah dominan)"""
    live = analisis.get("live", {})
    atas = live.get("atas", 0)
    bawah = live.get("bawah", 0)

    if atas > bawah:
        arah = f"ARUS ATAS  {_pts(atas)} ▲"
    elif bawah > atas:
        arah = f"ARUS BAWAH {_pts(bawah)} ▼"
    else:
        arah = "ARUS SEIMBANG"

    lines = [
        f"<b>Arus LIVE</b>",
        f"{arah}",
        f"Neto  {_neto(live.get('neto'))}",
        f"Julat {_pts(live.get('julat'))}",
        "",
        format_gt_table(analisis),
    ]
    return "\n".join(lines)


def format_puncak_lembah(analisis: Dict[str, Any]) -> str:
    """Menu Puncak / Lembah"""
    live = analisis.get("live", {})
    lines = [
        "<b>Puncak &amp; Lembah LIVE</b>",
        f"Puncak (Tinggi) : {_n(live.get('tinggi'))}",
        f"Lembah (Rendah) : {_n(live.get('rendah'))}",
        f"Atas            : {_pts(live.get('atas'))}",
        f"Bawah           : {_pts(live.get('bawah'))}",
        f"Neto            : {_neto(live.get('neto'))}",
        "",
        format_gt_table(analisis),
    ]
    return "\n".join(lines)


def format_full(analisis: Dict[str, Any]) -> str:
    """Menu Full report"""
    sinyal = buat_sinyal_pintar(analisis)
    live = analisis.get("live", {})

    lines = [
        "<b>FULL REPORT · Genesis</b>",
        "",
        f"Sinyal : <b>{sinyal['kode']}</b> {sinyal['arah']} (score {sinyal['score']})",
        f"Alasan : {_h(sinyal['alasan'])}",
        "",
        f"Bid    {_n(analisis.get('bid'))}",
        f"Neto   {_neto(live.get('neto'))}",
        f"Julat  {_pts(live.get('julat'))}",
        "",
        format_gt_table(analisis),
    ]
    return "\n".join(lines)


def format_tren(analisis: Dict[str, Any]) -> str:
    """Menu Tren singkat"""
    sinyal = buat_sinyal_pintar(analisis)
    return (
        f"<b>Tren Saat Ini</b>\n"
        f"Sinyal {sinyal['kode']} · {sinyal['arah']}\n"
        f"{_h(sinyal['alasan'])}"
    )
