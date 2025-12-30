#!/usr/bin/env python3
"""
Backfill Spot Price History from Gold-API

Fetches historical daily spot prices for gold (XAU) and silver (XAG) from
the Gold-API /history endpoint and stores them in CSV format for use by
the indicators module.

Usage:
    # Set your API key first
    export GOLD_API_KEY=your_key_here

    # Run the script
    python scripts/backfill_spot_history.py

The script will fetch maximum available history and save to:
    - data/xau_history.csv (gold)
    - data/xag_history.csv (silver)
"""
import os
import sys
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GOLD_API_KEY = os.getenv("GOLD_API_KEY")
BASE_URL = "https://api.gold-api.com/history"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Symbols to fetch
SYMBOLS = ["XAU", "XAG"]


def fetch_history(symbol: str, start_ts: int, end_ts: int) -> list:
    """
    Fetch daily spot prices from Gold-API.

    Args:
        symbol: XAU (gold) or XAG (silver)
        start_ts: Start Unix timestamp
        end_ts: End Unix timestamp

    Returns:
        List of price records from API
    """
    params = {
        "symbol": symbol,
        "startTimestamp": start_ts,
        "endTimestamp": end_ts,
        "groupBy": "day",
        "aggregation": "max",  # Daily high price (default, more representative)
        "orderBy": "asc"
    }

    headers = {
        "x-api-key": GOLD_API_KEY
    }

    print(f"  Fetching {symbol} from {datetime.fromtimestamp(start_ts).date()} to {datetime.fromtimestamp(end_ts).date()}...")

    resp = requests.get(BASE_URL, params=params, headers=headers, timeout=60)
    resp.raise_for_status()

    data = resp.json()

    # Handle different response formats
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and "data" in data:
        return data["data"]
    elif isinstance(data, dict) and "array" in data:
        return data["array"]
    else:
        print(f"  Unexpected response format: {type(data)}")
        print(f"  Response keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
        return []


def save_to_csv(symbol: str, records: list):
    """
    Save price records to CSV file in the expected format.

    Format: timestamp,close
    """
    if not records:
        print(f"  No records to save for {symbol}")
        return

    csv_path = DATA_DIR / f"{symbol.lower()}_history.csv"

    # Parse records into DataFrame
    rows = []
    for rec in records:
        # Handle different field names from API
        # Gold-API returns: {"day": "2024-01-01 00:00:00", "max_price": "2034.0400"} or similar
        if "day" in rec:
            date_str = rec.get("day")
            # Try different price field names based on aggregation param
            price = rec.get("max_price") or rec.get("avg_price") or rec.get("min_price") or rec.get("price")
        elif "date" in rec:
            date_str = rec.get("date")
            price = rec.get("max_price") or rec.get("avg_price") or rec.get("price") or rec.get("close")
        elif "timestamp" in rec:
            # Unix timestamp format
            ts = rec.get("timestamp")
            date_str = datetime.fromtimestamp(ts).isoformat() if isinstance(ts, (int, float)) else ts
            price = rec.get("max_price") or rec.get("avg_price") or rec.get("price") or rec.get("close")
        else:
            print(f"  Unknown record format: {rec}")
            continue

        if date_str and price:
            # Normalize date to ISO format
            if isinstance(date_str, str) and "T" not in date_str:
                date_str = f"{date_str}T00:00:00"
            rows.append({
                "timestamp": date_str,
                "close": float(price)
            })

    if not rows:
        print(f"  Could not parse any records for {symbol}")
        return

    df = pd.DataFrame(rows)
    df = df.sort_values("timestamp")
    df = df.drop_duplicates(subset=["timestamp"], keep="last")

    # If file exists, merge with existing data
    if csv_path.exists():
        existing = pd.read_csv(csv_path)
        df = pd.concat([existing, df], ignore_index=True)
        df = df.drop_duplicates(subset=["timestamp"], keep="last")
        df = df.sort_values("timestamp")

    df.to_csv(csv_path, index=False)
    print(f"  Saved {len(df)} records to {csv_path}")


def backfill_symbol(symbol: str, years_back: int = 5):
    """
    Backfill historical data for a single symbol.

    Args:
        symbol: XAU or XAG
        years_back: How many years of history to fetch (default 5)
    """
    print(f"\n=== Backfilling {symbol} ===")

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years_back * 365)

    start_ts = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())

    try:
        records = fetch_history(symbol, start_ts, end_ts)
        print(f"  Received {len(records)} records")

        if records:
            # Debug: print first record to see format
            print(f"  Sample record: {records[0]}")
            save_to_csv(symbol, records)
        else:
            print(f"  No data returned for {symbol}")

    except requests.exceptions.HTTPError as e:
        print(f"  HTTP Error: {e}")
        print(f"  Response: {e.response.text if e.response else 'N/A'}")
    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Gold-API Spot Price History Backfill")
    print("=" * 60)

    # Check for API key
    if not GOLD_API_KEY:
        print("\nERROR: GOLD_API_KEY environment variable not set!")
        print("Please set it with: export GOLD_API_KEY=your_key_here")
        print("Or add it to your .env file")
        sys.exit(1)

    print(f"\nAPI Key: {GOLD_API_KEY[:8]}...{GOLD_API_KEY[-4:]}")
    print(f"Data directory: {DATA_DIR}")

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Backfill each symbol
    for symbol in SYMBOLS:
        backfill_symbol(symbol, years_back=5)

    print("\n" + "=" * 60)
    print("Backfill complete!")
    print("=" * 60)

    # Show summary
    for symbol in SYMBOLS:
        csv_path = DATA_DIR / f"{symbol.lower()}_history.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            print(f"\n{symbol}: {len(df)} records")
            print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        else:
            print(f"\n{symbol}: No data file created")


if __name__ == "__main__":
    main()
