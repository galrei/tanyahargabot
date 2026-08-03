"""
Helper untuk mengambil data dari MetaTrader 5 + file Genesis EA.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Path default tempat EA Genesis menulis data
# Sesuaikan jika folder Data MT5 kamu berbeda
GENESIS_FILE_CANDIDATES = [
    # Common Terminal paths (Windows)
    Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Terminal",
    Path("C:/Users") / os.environ.get("USERNAME", "") / "AppData" / "Roaming" / "MetaQuotes" / "Terminal",
    # Relative / custom
    Path("genesis_data.json"),
    Path("MQL5/Files/genesis_data.json"),
    Path("Files/genesis_data.json"),
]


def _find_genesis_file() -> Optional[Path]:
    """Cari file data Genesis di lokasi umum."""
    # 1. Cek di folder bot dulu
    local = Path("genesis_data.json")
    if local.exists():
        return local

    # 2. Cek environment variable
    env_path = os.getenv("GENESIS_DATA_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    # 3. Cari di folder Terminal MT5
    appdata = Path(os.environ.get("APPDATA", ""))
    terminal_root = appdata / "MetaQuotes" / "Terminal"
    if terminal_root.exists():
        for terminal_dir in terminal_root.iterdir():
            if not terminal_dir.is_dir():
                continue
            for candidate in [
                terminal_dir / "MQL5" / "Files" / "genesis_data.json",
                terminal_dir / "MQL5" / "Files" / "Genesis.json",
                terminal_dir / "MQL5" / "Files" / "genesis.txt",
            ]:
                if candidate.exists():
                    return candidate

    return None


def baca_genesis() -> Optional[Dict[str, Any]]:
    """
    Baca data dari file yang ditulis EA Genesis.
    Format yang diharapkan (JSON):
    {
      "symbol": "XAUUSD",
      "time": "2026-08-03 10:00:00",
      "bid": 2650.12,
      "ask": 2650.35,
      "open": 2648.00,
      "high": 2655.00,
      "low": 2645.50,
      "close": 2650.20,
      "neto": 2.20,
      "inti": 2650.00,
      "jangkauan": 9.50,
      "tinggi": 2655.00,
      "bawah": 2645.50,
      "awal": 2648.00,
      ... field lain dari EA
    }
    """
    path = _find_genesis_file()
    if not path:
        return None

    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            return None

        # Coba JSON dulu
        if text.startswith("{"):
            data = json.loads(text)
            data["_source"] = f"Genesis EA ({path.name})"
            data["_file"] = str(path)
            return data

        # Fallback: format key=value per baris
        data = {}
        for line in text.splitlines():
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip().lower()
                v = v.strip()
                try:
                    data[k] = float(v.replace(",", ""))
                except ValueError:
                    data[k] = v
        if data:
            data["_source"] = f"Genesis EA ({path.name})"
            data["_file"] = str(path)
            return data
    except Exception as e:
        logger.error(f"Gagal baca Genesis file: {e}")
    return None


def get_mt5_price(symbol: str = "XAUUSD") -> Optional[Dict[str, Any]]:
    """Ambil harga langsung dari terminal MT5 yang sedang login."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        logger.warning("MetaTrader5 belum terinstall. Jalankan: pip install MetaTrader5")
        return None

    if not mt5.initialize():
        logger.warning(f"MT5 initialize gagal: {mt5.last_error()}")
        return None

    try:
        # Coba beberapa nama simbol umum
        candidates = [symbol, "XAUUSD", "XAUUSD.", "XAUUSD.a", "GOLD", "Gold"]
        tick = None
        used_symbol = None
        for sym in candidates:
            t = mt5.symbol_info_tick(sym)
            if t is not None:
                tick = t
                used_symbol = sym
                break

        if tick is None:
            # Coba cari simbol yang mengandung XAU / GOLD
            symbols = mt5.symbols_get()
            if symbols:
                for s in symbols:
                    name = s.name.upper()
                    if "XAU" in name or name == "GOLD":
                        t = mt5.symbol_info_tick(s.name)
                        if t:
                            tick = t
                            used_symbol = s.name
                            break

        if tick is None:
            logger.warning("Tidak menemukan simbol gold di MT5")
            return None

        info = mt5.symbol_info(used_symbol)
        rates = mt5.copy_rates_from_pos(used_symbol, mt5.TIMEFRAME_H1, 0, 50)

        result = {
            "symbol": used_symbol,
            "bid": round(tick.bid, 2),
            "ask": round(tick.ask, 2),
            "price": round((tick.bid + tick.ask) / 2, 2),
            "spread": round(tick.ask - tick.bid, 2),
            "time": datetime.fromtimestamp(tick.time).strftime("%d/%m/%Y %H:%M:%S"),
            "source": "MetaTrader 5 (broker)",
        }

        if rates is not None and len(rates) > 0:
            last = rates[-1]
            result["open"] = round(float(last["open"]), 2)
            result["high"] = round(float(last["high"]), 2)
            result["low"] = round(float(last["low"]), 2)
            result["close"] = round(float(last["close"]), 2)

            # Support/Resistance sederhana dari 48 candle
            highs = [float(r["high"]) for r in rates]
            lows = [float(r["low"]) for r in rates]
            result["resistance"] = round(max(highs), 2)
            result["support"] = round(min(lows), 2)

        if info:
            result["digits"] = info.digits
            result["point"] = info.point

        return result
    except Exception as e:
        logger.error(f"Error MT5: {e}")
        return None
    finally:
        mt5.shutdown()


def get_harga_lengkap(symbol: str = "XAUUSD") -> Dict[str, Any]:
    """
    Prioritas data:
    1. File Genesis EA (paling lengkap & faktual dari EA kamu)
    2. MT5 terminal (harga real broker)
    3. None (biar bot pakai Yahoo Finance)
    """
    # 1. Genesis EA
    genesis = baca_genesis()
    if genesis:
        # Normalisasi nama field
        out = {
            "source": genesis.get("_source", "Genesis EA"),
            "symbol": genesis.get("symbol", symbol),
            "price": _num(genesis, ["price", "close", "bid", "harga"]),
            "bid": _num(genesis, ["bid"]),
            "ask": _num(genesis, ["ask"]),
            "open": _num(genesis, ["open", "awal", "open_price"]),
            "high": _num(genesis, ["high", "tinggi", "max"]),
            "low": _num(genesis, ["low", "bawah", "rendah", "min"]),
            "close": _num(genesis, ["close", "price"]),
            "neto": _num(genesis, ["neto", "net", "change", "selisih"]),
            "inti": _num(genesis, ["inti", "core", "pivot", "mid"]),
            "jangkauan": _num(genesis, ["jangkauan", "range", "rng"]),
            "tinggi": _num(genesis, ["tinggi", "high"]),
            "bawah": _num(genesis, ["bawah", "low", "rendah"]),
            "awal": _num(genesis, ["awal", "open"]),
            "time": genesis.get("time") or genesis.get("waktu") or datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "raw": genesis,  # simpan semua field asli
        }
        # Hitung yang belum ada
        if out["price"] is None and out["bid"] and out["ask"]:
            out["price"] = round((out["bid"] + out["ask"]) / 2, 2)
        if out["jangkauan"] is None and out["high"] and out["low"]:
            out["jangkauan"] = round(out["high"] - out["low"], 2)
        if out["neto"] is None and out["close"] and out["open"]:
            out["neto"] = round(out["close"] - out["open"], 2)
        return out

    # 2. MT5 langsung
    mt5_data = get_mt5_price(symbol)
    if mt5_data:
        mt5_data["neto"] = None
        mt5_data["inti"] = None
        mt5_data["jangkauan"] = None
        if mt5_data.get("high") and mt5_data.get("low"):
            mt5_data["jangkauan"] = round(mt5_data["high"] - mt5_data["low"], 2)
        if mt5_data.get("close") and mt5_data.get("open"):
            mt5_data["neto"] = round(mt5_data["close"] - mt5_data["open"], 2)
        if mt5_data.get("high") and mt5_data.get("low"):
            mt5_data["inti"] = round((mt5_data["high"] + mt5_data["low"]) / 2, 2)
        mt5_data["tinggi"] = mt5_data.get("high")
        mt5_data["bawah"] = mt5_data.get("low")
        mt5_data["awal"] = mt5_data.get("open")
        return mt5_data

    return {}


def _num(d: dict, keys: list) -> Optional[float]:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return None
