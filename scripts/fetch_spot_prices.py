#!/usr/bin/env python3
"""
Fetch Daily Spot Prices from Gold-API

This script is designed to run via GitHub Actions to fetch the current
spot prices for gold (XAU) and silver (XAG) and append them to the
history CSV files.

Usage:
    python scripts/fetch_spot_prices.py

The Gold-API /price endpoint does not require authentication.
"""
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

# Configuration
BASE_URL = "https://api.gold-api.com/price"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Symbols to fetch
SYMBOLS = ["XAU", "XAG"]


def fetch_current_price(symbol: str) -> dict:
    """
    Fetch current spot price from Gold-API.

    Args:
        symbol: XAU (gold) or XAG (silver)

    Returns:
        Dict with price data or None if failed
    """
    url = f"{BASE_URL}/{symbol}"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        return {
            "symbol": data.get("symbol", symbol),
            "price": data.get("price"),
            "timestamp": data.get("updatedAt"),
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None


def append_to_csv(symbol: str, price: float, timestamp: str):
    """
    Append price to CSV file with deduplication.

    Args:
        symbol: XAU or XAG
        price: Current spot price
        timestamp: ISO timestamp from API
    """
    csv_path = DATA_DIR / f"{symbol.lower()}_history.csv"

    # Parse and normalize timestamp to date-only for deduplication
    ts = pd.to_datetime(timestamp)
    if hasattr(ts, 'tz') and ts.tz is not None:
        ts = ts.tz_convert(None)

    # Format as ISO without timezone
    ts_str = ts.strftime('%Y-%m-%dT%H:%M:%S')
    date_only = ts.strftime('%Y-%m-%d')

    if csv_path.exists():
        df = pd.read_csv(csv_path)

        # Check if we already have data for today
        df['date'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d')

        if date_only in df['date'].values:
            print(f"  {symbol}: Already have data for {date_only}, skipping")
            return False

        # Remove the helper column before saving
        df = df.drop(columns=['date'])

        # Append new row
        new_row = pd.DataFrame([{"timestamp": ts_str, "close": float(price)}])
        df = pd.concat([df, new_row], ignore_index=True)
    else:
        # Create new file
        df = pd.DataFrame([{"timestamp": ts_str, "close": float(price)}])

    # Sort by timestamp and save
    df['_sort'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('_sort').drop(columns=['_sort'])
    df.to_csv(csv_path, index=False)

    print(f"  {symbol}: Added price ${price:.2f} for {date_only}")
    return True


def main():
    """Main entry point."""
    print("=" * 50)
    print("Gold-API Spot Price Fetch")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 50)

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    updated = False

    for symbol in SYMBOLS:
        print(f"\nFetching {symbol}...")
        data = fetch_current_price(symbol)

        if data and data.get("price"):
            result = append_to_csv(
                symbol,
                data["price"],
                data["timestamp"]
            )
            if result:
                updated = True
        else:
            print(f"  {symbol}: Failed to fetch price")

    print("\n" + "=" * 50)
    if updated:
        print("Prices updated successfully!")
    else:
        print("No updates needed (data already exists for today)")
    print("=" * 50)

    # Show current state
    for symbol in SYMBOLS:
        csv_path = DATA_DIR / f"{symbol.lower()}_history.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            print(f"\n{symbol}: {len(df)} records")
            print(f"  Latest: {df['timestamp'].iloc[-1]} - ${df['close'].iloc[-1]:.2f}")


if __name__ == "__main__":
    main()
