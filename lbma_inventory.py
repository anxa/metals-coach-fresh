"""
LBMA London Vault Holdings Data Module

Fetches and analyzes gold and silver vault holdings data from the
London Bullion Market Association (LBMA).

Data characteristics:
- Published monthly on the 5th business day
- One month in arrears (e.g., November data published in December)
- Covers all London vaults within M25 area
- Historical data available from July 2016

Usage:
    from lbma_inventory import get_latest_lbma, get_lbma_history

    latest = get_latest_lbma()
    history = get_lbma_history()
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path

# LBMA API endpoint
LBMA_API_URL = "https://www.lbma.org.uk/vault-holdings-data/data.json"

# Conversion factor: 1 tonne = 32,150.7466 troy ounces
TONNES_TO_TROY_OZ = 32150.7466

# Cache for API data (1 hour TTL since data updates monthly)
_lbma_cache = {"data": None, "timestamp": None}
CACHE_TTL_SECONDS = 3600  # 1 hour

# Local data directory for fallback
DATA_DIR = Path(__file__).resolve().parent / "data"
LBMA_CSV = DATA_DIR / "lbma_inventory.csv"

# GitHub raw URL for fallback on Streamlit Cloud
GITHUB_LBMA_CSV_URL = "https://raw.githubusercontent.com/anxa/metals-coach-fresh/main/data/lbma_inventory.csv"


def fetch_lbma_data() -> Optional[pd.DataFrame]:
    """
    Fetch LBMA vault holdings data from API.

    Returns DataFrame with columns: date, gold_tonnes, silver_tonnes
    Uses in-memory cache with 1-hour TTL.
    """
    global _lbma_cache

    # Check cache validity
    now = datetime.now()
    if (_lbma_cache["data"] is not None and
        _lbma_cache["timestamp"] is not None and
        (now - _lbma_cache["timestamp"]).total_seconds() < CACHE_TTL_SECONDS):
        return _lbma_cache["data"].copy()

    try:
        resp = requests.get(LBMA_API_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Parse JSON array: [timestamp_ms, gold_thousand_oz, silver_thousand_oz]
        # Values are in THOUSANDS of troy ounces
        records = []
        for row in data:
            timestamp_ms, gold_koz, silver_koz = row
            date = datetime.fromtimestamp(timestamp_ms / 1000)

            # Convert from thousands of troy oz to tonnes
            gold_oz = gold_koz * 1000
            silver_oz = silver_koz * 1000
            gold_tonnes = gold_oz / TONNES_TO_TROY_OZ
            silver_tonnes = silver_oz / TONNES_TO_TROY_OZ

            records.append({
                "date": date,
                "gold_tonnes": gold_tonnes,
                "silver_tonnes": silver_tonnes,
                "gold_oz": gold_oz,
                "silver_oz": silver_oz
            })

        df = pd.DataFrame(records)
        df = df.sort_values("date").reset_index(drop=True)

        # Calculate month-over-month changes
        df["gold_change"] = df["gold_tonnes"].diff()
        df["gold_change_pct"] = df["gold_tonnes"].pct_change() * 100
        df["silver_change"] = df["silver_tonnes"].diff()
        df["silver_change_pct"] = df["silver_tonnes"].pct_change() * 100

        # Update cache
        _lbma_cache["data"] = df
        _lbma_cache["timestamp"] = now

        return df.copy()

    except Exception as e:
        print(f"Error fetching LBMA API: {e}")

    # Try loading from local CSV fallback
    if LBMA_CSV.exists():
        try:
            df = pd.read_csv(LBMA_CSV, parse_dates=["date"])
            # Recalculate changes if missing
            if "gold_change" not in df.columns:
                df["gold_change"] = df["gold_tonnes"].diff()
                df["gold_change_pct"] = df["gold_tonnes"].pct_change() * 100
                df["silver_change"] = df["silver_tonnes"].diff()
                df["silver_change_pct"] = df["silver_tonnes"].pct_change() * 100
            return df
        except Exception as e2:
            print(f"Error loading local CSV: {e2}")

    # Try loading from GitHub as last resort (for Streamlit Cloud)
    try:
        resp = requests.get(GITHUB_LBMA_CSV_URL, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), parse_dates=["date"])
        # Recalculate changes if missing
        if "gold_change" not in df.columns:
            df["gold_change"] = df["gold_tonnes"].diff()
            df["gold_change_pct"] = df["gold_tonnes"].pct_change() * 100
            df["silver_change"] = df["silver_tonnes"].diff()
            df["silver_change_pct"] = df["silver_tonnes"].pct_change() * 100
        return df
    except Exception as e3:
        print(f"Error fetching from GitHub: {e3}")

    return None


def get_lbma_history() -> Optional[pd.DataFrame]:
    """
    Get full LBMA history for charting.

    Returns DataFrame with date, gold_tonnes, silver_tonnes, and derived columns.
    """
    return fetch_lbma_data()


def get_latest_lbma() -> Optional[Dict]:
    """
    Get the most recent LBMA vault holdings.

    Returns:
        Dict with:
        - gold_tonnes, gold_oz, gold_change_pct
        - silver_tonnes, silver_oz, silver_change_pct
        - data_date: The date the data represents
        - as_of: Human readable "As of November 2025"
    """
    df = fetch_lbma_data()
    if df is None or df.empty:
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None

    data_date = latest["date"]

    return {
        # Gold
        "gold_tonnes": float(latest["gold_tonnes"]),
        "gold_oz": float(latest["gold_oz"]),
        "gold_change_tonnes": float(latest["gold_change"]) if pd.notna(latest["gold_change"]) else 0,
        "gold_change_pct": float(latest["gold_change_pct"]) if pd.notna(latest["gold_change_pct"]) else 0,

        # Silver
        "silver_tonnes": float(latest["silver_tonnes"]),
        "silver_oz": float(latest["silver_oz"]),
        "silver_change_tonnes": float(latest["silver_change"]) if pd.notna(latest["silver_change"]) else 0,
        "silver_change_pct": float(latest["silver_change_pct"]) if pd.notna(latest["silver_change_pct"]) else 0,

        # Metadata
        "data_date": data_date,
        "as_of": data_date.strftime("As of %B %Y"),
        "data_delay_note": "Data published monthly, 1 month in arrears"
    }


def get_lbma_comparison() -> Optional[Dict]:
    """
    Get LBMA data formatted for comparison with COMEX.

    Returns holdings in both tonnes and troy oz for easy comparison.
    """
    latest = get_latest_lbma()
    if latest is None:
        return None

    return {
        "gold": {
            "location": "London (LBMA)",
            "tonnes": latest["gold_tonnes"],
            "troy_oz": latest["gold_oz"],
            "troy_oz_millions": latest["gold_oz"] / 1_000_000,
            "change_pct": latest["gold_change_pct"]
        },
        "silver": {
            "location": "London (LBMA)",
            "tonnes": latest["silver_tonnes"],
            "troy_oz": latest["silver_oz"],
            "troy_oz_millions": latest["silver_oz"] / 1_000_000,
            "change_pct": latest["silver_change_pct"]
        },
        "as_of": latest["as_of"]
    }


def format_tonnes(tonnes: float) -> str:
    """Format tonnes with comma separator."""
    return f"{tonnes:,.0f}"


def format_oz_millions(oz: float) -> str:
    """Format troy oz in millions."""
    return f"{oz / 1_000_000:.1f}M oz"


def save_to_csv(df: pd.DataFrame) -> bool:
    """
    Save LBMA data to CSV for persistence.

    Used by GitHub Actions to backup data.
    """
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(LBMA_CSV, index=False)
        return True
    except Exception as e:
        print(f"Error saving LBMA CSV: {e}")
        return False


if __name__ == "__main__":
    # Test the module
    print("=" * 50)
    print("LBMA London Vault Holdings")
    print("=" * 50)

    latest = get_latest_lbma()
    if latest:
        print(f"\n{latest['as_of']}")
        print(f"\nGold:")
        print(f"  {format_tonnes(latest['gold_tonnes'])} tonnes ({format_oz_millions(latest['gold_oz'])})")
        print(f"  MoM change: {latest['gold_change_pct']:+.2f}%")

        print(f"\nSilver:")
        print(f"  {format_tonnes(latest['silver_tonnes'])} tonnes ({format_oz_millions(latest['silver_oz'])})")
        print(f"  MoM change: {latest['silver_change_pct']:+.2f}%")

        print(f"\nNote: {latest['data_delay_note']}")

        # Show history summary
        history = get_lbma_history()
        if history is not None:
            print(f"\nHistory: {len(history)} months of data")
            print(f"  From: {history['date'].min().strftime('%B %Y')}")
            print(f"  To: {history['date'].max().strftime('%B %Y')}")
    else:
        print("Failed to fetch LBMA data")
