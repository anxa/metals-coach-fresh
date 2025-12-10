"""
Simple CSV-based data store for daily precious metals prices.

This module persists daily snapshots from Gold-API to local CSV files,
allowing indicators to be computed from cached history without consuming
API quota on every indicator computation.
"""
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


def ensure_data_dir() -> Path:
    """Create data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def csv_path(symbol: str) -> Path:
    """Return path to CSV file for a symbol (e.g., 'XAU' or 'xau')."""
    ensure_data_dir()
    return DATA_DIR / f"{symbol.lower()}_history.csv"


def append_price(symbol: str, timestamp: str, price: float):
    """
    Append a single price row to CSV if timestamp not already present.

    Args:
        symbol: e.g., 'XAU', 'XAG'
        timestamp: ISO string e.g., '2025-12-10T14:03:03Z'
        price: float price value
    """
    p = csv_path(symbol)
    ts = pd.to_datetime(timestamp)

    # Normalize timestamp to tz-naive for consistent comparisons
    try:
        if getattr(ts, "tz", None) is not None:
            ts = ts.tz_convert(None)
    except Exception:
        try:
            ts = ts.tz_localize(None)
        except Exception:
            pass

    if p.exists():
        df = pd.read_csv(p, parse_dates=["timestamp"]).set_index("timestamp")
        # normalize existing index to tz-naive as well
        try:
            if getattr(df.index, "tz", None) is not None:
                df.index = df.index.tz_convert(None)
        except Exception:
            try:
                df.index = df.index.tz_localize(None)
            except Exception:
                pass

        if ts in df.index:
            # Already have this timestamp; skip
            return
        df.loc[ts] = [float(price)]
        df = df.sort_index()
    else:
        # Create new DataFrame with one row
        df = pd.DataFrame(
            [{"timestamp": ts.isoformat(), "close": float(price)}]
        ).set_index("timestamp")

    # Ensure timestamps are written in ISO format (tz-naive) to CSV
    df_reset = df.reset_index()
    def _to_naive_iso(t):
        tt = pd.to_datetime(t)
        try:
            if getattr(tt, "tz", None) is not None:
                tt = tt.tz_convert(None)
        except Exception:
            try:
                tt = tt.tz_localize(None)
            except Exception:
                pass
        return tt.strftime('%Y-%m-%dT%H:%M:%S')

    df_reset["timestamp"] = df_reset["timestamp"].map(_to_naive_iso)
    df_reset = df_reset.set_index("timestamp")
    df_reset.to_csv(p)


def full_history_path(symbol: str) -> Path:
    """Return path to full history CSV file (from yfinance bulk download)."""
    ensure_data_dir()
    return DATA_DIR / f"{symbol.lower()}_history_full.csv"


def load_history(symbol: str) -> pd.DataFrame:
    """
    Load local CSV history for a symbol.

    Prefers full history file (from yfinance bulk download) if available,
    falls back to daily snapshots file.

    Returns:
        DataFrame with "Close" column, or None if no file exists.
    """
    # Try full history first (yfinance format: Date index, Close column)
    full_path = full_history_path(symbol)
    if full_path.exists():
        df = pd.read_csv(full_path, parse_dates=["Date"]).set_index("Date")
        # Already has "Close" column from yfinance
        return df

    # Fall back to daily snapshots (Gold-API format: timestamp index, close column)
    p = csv_path(symbol)
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["timestamp"]).set_index("timestamp")
    # Normalize column name to "Close" for indicators module compatibility
    df = df.rename(columns={"close": "Close"})
    return df
