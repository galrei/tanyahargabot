# mt5_helper.py
# Pengambilan data XAUUSD dari MT5 + Genesis EA (genesis_data.json)
# Fallback ke yfinance jika MT5 / file tidak tersedia

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

# Path file yang ditulis oleh EA Genesis
GENESIS_JSON_CANDIDATES = [
    Path("/home/workdir/artifacts/genesis_data.json"),
    Path("genesis_data.json"),
    Path("MQL5/Files/genesis_data.json"),
    Path(os.path.expanduser("~/genesis_data.json")),
]


def _read_genesis_json() -> Optional[Dict[str, Any]]:
    for p in GENESIS_JSON_CANDIDATES:
        try:
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
        except Exception:
            continue
    return None


def _try_mt5() -> Optional[Dict[str, Any]]:
    """Coba ambil data langsung dari MetaTrader5 (jika library + terminal tersedia)"""
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return None

        symbol = "XAUUSD"
        tick = mt5.symbol_info_tick(symbol)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)

        mt5.shutdown()

        if tick is None:
            return None

        out = {
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "time": datetime.fromtimestamp(tick.time).strftime("%H:%M"),
            "source": "MT5",
        }
        if rates is not None and len(rates) > 0:
            r = rates[0]
            out.update({
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
            })
        return out
    except Exception:
        return None


def _try_yfinance() -> Optional[Dict[str, Any]]:
    """Fallback Yahoo Finance"""
    try:
        import yfinance as yf
        t = yf.Ticker("GC=F")  # Gold futures
        hist = t.history(period="1d", interval="1m")
        if hist.empty:
            return None
        last = hist.iloc[-1]
        info = t.info or {}
        return {
            "bid": float(last["Close"]),
            "ask": float(last["Close"]),
            "open": float(last["Open"]),
            "high": float(last["High"]),
            "low": float(last["Low"]),
            "close": float(last["Close"]),
            "time": last.name.strftime("%H:%M") if hasattr(last.name, "strftime") else "—",
            "source": "Yahoo",
        }
    except Exception:
        return None


def get_gold_data() -> Dict[str, Any]:
    """
    Prioritas:
    1. genesis_data.json (dari EA Genesis)
    2. MetaTrader5 live
    3. yfinance
    """
    # 1. Genesis EA
    genesis = _read_genesis_json()
    if genesis:
        # pastikan ada key yang dibutuhkan signal_engine
        if "waktu" not in genesis and "time" in genesis:
            genesis["waktu"] = genesis["time"]
        genesis["source"] = "Genesis EA"
        return genesis

    # 2. MT5
    mt5_data = _try_mt5()
    if mt5_data:
        return mt5_data

    # 3. Yahoo
    yf_data = _try_yfinance()
    if yf_data:
        return yf_data

    # Fallback kosong
    return {
        "bid": None,
        "ask": None,
        "source": "none",
        "waktu": "—",
    }


def get_account_info() -> Dict[str, Any]:
    """Info akun MT5 (balance, equity, margin) – untuk risk management nanti"""
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return {}
        info = mt5.account_info()
        mt5.shutdown()
        if info is None:
            return {}
        return {
            "balance": float(info.balance),
            "equity": float(info.equity),
            "margin": float(info.margin),
            "free_margin": float(info.margin_free),
            "leverage": int(info.leverage),
            "currency": info.currency,
        }
    except Exception:
        return {}
