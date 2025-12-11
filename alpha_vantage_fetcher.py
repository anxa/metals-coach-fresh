"""
Fetcher for precious metal prices using yfinance.

This module prefers spot tickers (Yahoo spot pairs) and falls back to the
most-liquid futures tickers if spot is not available. The fetch functions
return a (price, metadata) tuple where metadata contains the ticker used,
the data type ("spot" or "futures"), the source, and a timestamp.
"""

import requests
import yfinance as yf
from typing import Optional, Tuple, List
from datetime import datetime
from data_store import append_price

# Preferred spot tickers on Yahoo Finance
GOLD_SPOT = "XAUUSD=X"
SILVER_SPOT = "XAGUSD=X"

# Fallback: COMEX futures
GOLD_FUT = "GC=F"
SILVER_FUT = "SI=F"
COPPER_FUT = "HG=F"


def _try_tickers(tickers: List[tuple]) -> Tuple[Optional[float], Optional[dict]]:
    """
    Try a list of (ticker, type_label) pairs and return the first successful
    price along with metadata.
    """
    for ticker, type_label in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1d")

            if hist.empty:
                # Try next ticker
                continue

            price = float(hist["Close"].iloc[-1])
            metadata = {
                "ticker": ticker,
                "data_type": type_label,  # 'spot' or 'futures'
                "source": "yfinance",
                "timestamp": datetime.now().isoformat(),
                "close": price,
            }
            return price, metadata

        except Exception as e:
            # Non-fatal; try next ticker
            print(f"Warning: failed to fetch {ticker}: {e}")
            continue

    return None, None


def fetch_gold_price() -> Tuple[Optional[float], Optional[dict]]:
    """Fetch gold price: prefer Gold-API (no auth), then spot on Yahoo, then futures."""
    # Try gold-api first (no auth required)
    try:
        url = "https://api.gold-api.com/price/XAU"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        price = data.get("price")
        if price is not None:
            timestamp = data.get("updatedAt") or datetime.now().isoformat()
            meta = {
                "ticker": data.get("symbol", "XAU"),
                "data_type": "spot",
                "source": "gold-api",
                "timestamp": timestamp,
                "close": float(price),
            }
            # Persist daily snapshot to CSV (idempotent if timestamp already exists)
            try:
                append_price("XAU", timestamp, price)
            except Exception as persist_err:
                print(f"Failed to persist gold snapshot: {persist_err}")
            return float(price), meta
    except Exception as e:
        # Non-fatal; fall back
        print(f"Gold-API fetch failed or not available: {e}")

    tickers = [(GOLD_SPOT, "spot"), (GOLD_FUT, "futures")]
    return _try_tickers(tickers)


def fetch_silver_price() -> Tuple[Optional[float], Optional[dict]]:
    """Fetch silver price: prefer Gold-API (no auth), then spot on Yahoo, then futures."""
    try:
        url = "https://api.gold-api.com/price/XAG"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        price = data.get("price")
        if price is not None:
            timestamp = data.get("updatedAt") or datetime.now().isoformat()
            meta = {
                "ticker": data.get("symbol", "XAG"),
                "data_type": "spot",
                "source": "gold-api",
                "timestamp": timestamp,
                "close": float(price),
            }
            # Persist daily snapshot to CSV (idempotent if timestamp already exists)
            try:
                append_price("XAG", timestamp, price)
            except Exception as persist_err:
                print(f"Failed to persist silver snapshot: {persist_err}")
            return float(price), meta
    except Exception as e:
        print(f"Gold-API (silver) fetch failed or not available: {e}")

    tickers = [(SILVER_SPOT, "spot"), (SILVER_FUT, "futures")]
    return _try_tickers(tickers)


def fetch_copper_price() -> Tuple[Optional[float], Optional[dict]]:
    """Fetch copper price: prefer Gold-API (HG symbol), then futures on Yahoo."""
    try:
        url = "https://api.gold-api.com/price/HG"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        price = data.get("price")
        if price is not None:
            timestamp = data.get("updatedAt") or datetime.now().isoformat()
            meta = {
                "ticker": data.get("symbol", "HG"),
                "data_type": "spot",
                "source": "gold-api",
                "timestamp": timestamp,
                "close": float(price),
            }
            # Persist daily snapshot to CSV
            try:
                append_price("HG", timestamp, price)
            except Exception as persist_err:
                print(f"Failed to persist copper snapshot: {persist_err}")
            return float(price), meta
    except Exception as e:
        print(f"Gold-API (copper) fetch failed or not available: {e}")

    # Fallback to Yahoo Finance futures
    tickers = [(COPPER_FUT, "futures")]
    return _try_tickers(tickers)


if __name__ == "__main__":
    g, gm = fetch_gold_price()
    s, sm = fetch_silver_price()
    c, cm = fetch_copper_price()

    if g is not None:
        print(f"Gold: ${g:.2f}/oz — {gm['data_type']} (ticker={gm['ticker']})")
    else:
        print("Gold: Failed to fetch price")

    if s is not None:
        print(f"Silver: ${s:.4f}/oz — {sm['data_type']} (ticker={sm['ticker']})")
    else:
        print("Silver: Failed to fetch price")

    if c is not None:
        print(f"Copper: ${c:.4f}/lb — {cm['data_type']} (ticker={cm['ticker']})")
    else:
        print("Copper: Failed to fetch price")

