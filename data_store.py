"""
Simple CSV-based data store for daily precious metals prices.

This module persists daily snapshots from Gold-API to local CSV files,
allowing indicators to be computed from cached history without consuming
API quota on every indicator computation.
"""
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional

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


def get_yesterday_spot_close(symbol: str) -> float:
    """
    Get yesterday's closing spot price from Gold-API history.

    Looks at the spot price CSV and finds the last price from a date
    prior to today. This allows proper spot-to-spot daily change calculation.

    Args:
        symbol: e.g., 'XAU', 'XAG', 'HG', 'XPT', 'XPD'

    Returns:
        Yesterday's closing spot price, or None if not available
    """
    p = csv_path(symbol)
    if not p.exists():
        return None

    df = pd.read_csv(p, parse_dates=["timestamp"])
    if df.empty:
        return None

    # Extract date from timestamp
    df["date"] = df["timestamp"].dt.date
    today = pd.Timestamp.now().date()

    # Filter to dates before today
    yesterday_data = df[df["date"] < today]

    if yesterday_data.empty:
        return None

    # Get the last price from the most recent past date
    # (This is effectively yesterday's closing spot price)
    yesterday_data = yesterday_data.sort_values("timestamp")
    return yesterday_data["close"].iloc[-1]


def get_spot_high_and_days(symbol: str) -> Tuple[Optional[float], int]:
    """
    Get the highest spot price and number of days of data available.

    Used to calculate "% from X-day high" when we don't have 52 weeks
    of spot data yet.

    Args:
        symbol: e.g., 'XAU', 'XAG', 'HG', 'XPT', 'XPD'

    Returns:
        (high_price, num_days) or (None, 0) if no data
    """
    p = csv_path(symbol)
    if not p.exists():
        return None, 0

    df = pd.read_csv(p, parse_dates=["timestamp"])
    if df.empty:
        return None, 0

    # Get unique dates
    df["date"] = df["timestamp"].dt.date
    unique_dates = df["date"].nunique()

    # Get high from all data
    high = df["close"].max()

    return high, unique_dates


def load_spot_history(symbol: str, min_days: int = 200) -> Optional[pd.DataFrame]:
    """
    Load spot price history from Gold-API snapshots.

    This provides actual spot prices (not futures) for indicator calculations.
    Only returns data if we have at least min_days of history.

    Args:
        symbol: e.g., 'XAU', 'XAG'
        min_days: Minimum days of data required (default 200 for SMA200)

    Returns:
        DataFrame with "Close" column and DatetimeIndex, or None if insufficient data
    """
    p = csv_path(symbol)
    if not p.exists():
        return None

    df = pd.read_csv(p, parse_dates=["timestamp"])
    if df.empty:
        return None

    # Get unique trading days
    df["date"] = df["timestamp"].dt.date
    unique_days = df["date"].nunique()

    if unique_days < min_days:
        return None

    # Deduplicate to one price per day (use last price of the day)
    df = df.sort_values("timestamp")
    df_daily = df.groupby("date").last().reset_index()
    df_daily["date"] = pd.to_datetime(df_daily["date"])
    df_daily = df_daily.set_index("date")

    # Normalize column name for compatibility
    df_daily = df_daily.rename(columns={"close": "Close"})

    return df_daily[["Close"]]


def load_history(symbol: str) -> pd.DataFrame:
    """
    Load local CSV history for a symbol.

    For gold (XAU) and silver (XAG), prefers spot price history from Gold-API
    if we have sufficient data (200+ days). Otherwise falls back to futures.

    For other metals, uses yfinance futures data.

    Returns:
        DataFrame with "Close" column, or None if no file exists.
    """
    # For gold and silver, prefer spot history if we have enough data
    if symbol.upper() in ["XAU", "XAG"]:
        spot_df = load_spot_history(symbol, min_days=200)
        if spot_df is not None:
            return spot_df

    # Fall back to full history file (yfinance futures format)
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
