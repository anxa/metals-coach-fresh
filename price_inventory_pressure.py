"""
Price vs Inventory Pressure Analysis Module

Detects agreement vs disagreement between paper price and physical availability
for Gold, Silver, Copper, Platinum, and Palladium.

This module outputs pressure states and context - NOT buy/sell signals.

Key insight: "Is the physical market backing or fighting the price move — and for how long?"
"""
import pandas as pd
import yfinance as yf
from typing import Dict, Optional, Literal
from datetime import datetime, timedelta
from pathlib import Path

from cme_inventory import load_inventory, get_grand_totals

# Futures tickers for price data
TICKERS = {
    "gold": "GC=F",
    "silver": "SI=F",
    "copper": "HG=F",
    "platinum": "PL=F",
    "palladium": "PA=F",
}

# Flat/noise threshold (±0.25%)
FLAT_THRESHOLD = 0.25

# Pressure state definitions
PRESSURE_STATES = {
    ("UP", "DOWN"): {
        "state": "Confirmed strength",
        "emoji": "🟢",
        "color": "#00c853",
        "description": "Physical market confirms rally. Upside moves structurally supported.",
        "action": "Pullbacks tend to be bought. Shorts are low-probability.",
    },
    ("UP", "UP"): {
        "state": "Fragile rally",
        "emoji": "🟡",
        "color": "#ffc107",
        "description": "Price rising despite metal piling up. Often macro/spec-driven.",
        "action": "Vulnerable to fast reversals. Do not chase. Common bull-trap state.",
    },
    ("DOWN", "UP"): {
        "state": "Confirmed weakness",
        "emoji": "🔴",
        "color": "#ff5252",
        "description": "Demand weak, supply ample. Downtrend supported.",
        "action": "Avoid longs. Rallies tend to fade. Strongest bearish confirmation.",
    },
    ("DOWN", "DOWN"): {
        "state": "Pressure building",
        "emoji": "🟠",
        "color": "#ff9800",
        "description": "Physical market tightening while price falls. Selling may be exhausting supply.",
        "action": "Often precedes bases or squeezes. Requires patience; not immediate buy.",
    },
    ("UP", "FLAT"): {
        "state": "Price-led move",
        "emoji": "⚪",
        "color": "#9e9e9e",
        "description": "Price rising without physical confirmation.",
        "action": "Monitor for inventory to confirm or deny the move.",
    },
    ("FLAT", "DOWN"): {
        "state": "Tightening beneath",
        "emoji": "🟡",
        "color": "#ffc107",
        "description": "Inventory drawing down while price flat. Breakout risk building.",
        "action": "Watch for upside breakout. Physical market constructive.",
    },
    ("FLAT", "UP"): {
        "state": "Loosening beneath",
        "emoji": "🟠",
        "color": "#ff9800",
        "description": "Inventory building while price flat. Downside risk accumulating.",
        "action": "Watch for breakdown. Physical market weakening.",
    },
    ("FLAT", "FLAT"): {
        "state": "Balanced / neutral",
        "emoji": "⚪",
        "color": "#9e9e9e",
        "description": "No clear pressure from either side.",
        "action": "Wait for direction. Macro or positioning likely dominant.",
    },
    ("DOWN", "FLAT"): {
        "state": "Price weakness",
        "emoji": "🔴",
        "color": "#ff5252",
        "description": "Price falling without inventory relief.",
        "action": "Bearish until inventory confirms support.",
    },
}


def get_direction(pct_change: float) -> Literal["UP", "DOWN", "FLAT"]:
    """Classify direction based on percentage change."""
    if pct_change > FLAT_THRESHOLD:
        return "UP"
    elif pct_change < -FLAT_THRESHOLD:
        return "DOWN"
    return "FLAT"


def get_price_history(metal: str, days: int = 60) -> Optional[pd.DataFrame]:
    """Fetch price history for a metal."""
    ticker = TICKERS.get(metal.lower())
    if not ticker:
        return None

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=f"{days}d")
        if hist.empty:
            return None

        df = pd.DataFrame({
            "date": hist.index.date,
            "close_price": hist["Close"].values
        })
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date")

    except Exception as e:
        print(f"Error fetching price history for {metal}: {e}")
        return None


def get_inventory_history(metal: str) -> Optional[pd.DataFrame]:
    """Get inventory history for a metal from CME data."""
    totals = get_grand_totals(metal)
    if totals.empty:
        return None

    df = totals[["date", "total"]].copy()
    df.columns = ["date", "inventory_level"]
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    return df


def compute_pressure_table(metal: str, lookback_days: int = 60) -> Optional[pd.DataFrame]:
    """
    Compute the full pressure analysis table for a metal.

    Args:
        metal: "gold", "silver", "copper", "platinum", or "palladium"
        lookback_days: Number of days of history to analyze

    Returns:
        DataFrame with all pressure metrics, or None if insufficient data.
    """
    # Get price data
    price_df = get_price_history(metal, lookback_days)
    if price_df is None or price_df.empty:
        return None

    # Get inventory data
    inv_df = get_inventory_history(metal)
    if inv_df is None or inv_df.empty:
        return None

    # Merge price and inventory data
    df = price_df.join(inv_df, how="left")

    # Forward-fill inventory for non-reporting days
    df["inventory_level"] = df["inventory_level"].ffill()

    # Drop rows where we don't have inventory data
    df = df.dropna(subset=["inventory_level"])

    if len(df) < 11:  # Need at least 11 days for 10D calculations
        return None

    # 1️⃣ Daily % change
    df["price_pct_1d"] = df["close_price"].pct_change() * 100
    df["inv_pct_1d"] = df["inventory_level"].pct_change() * 100

    # 2️⃣ Rolling aggregates (5D and 10D)
    df["price_pct_5d"] = (df["close_price"] / df["close_price"].shift(5) - 1) * 100
    df["price_pct_10d"] = (df["close_price"] / df["close_price"].shift(10) - 1) * 100

    df["inv_pct_5d"] = (df["inventory_level"] / df["inventory_level"].shift(5) - 1) * 100
    df["inv_pct_10d"] = (df["inventory_level"] / df["inventory_level"].shift(10) - 1) * 100

    # 3️⃣ Moving averages of daily changes
    df["MA_price_5"] = df["price_pct_1d"].rolling(5).mean()
    df["MA_price_10"] = df["price_pct_1d"].rolling(10).mean()

    df["MA_inv_5"] = df["inv_pct_1d"].rolling(5).mean()
    df["MA_inv_10"] = df["inv_pct_1d"].rolling(10).mean()

    # 4️⃣ State classification (based on 5D data)
    df["price_dir"] = df["price_pct_5d"].apply(get_direction)
    df["inv_dir"] = df["inv_pct_5d"].apply(
        lambda x: "DOWN" if x < -FLAT_THRESHOLD else ("UP" if x > FLAT_THRESHOLD else "FLAT")
    )

    # Determine pressure state
    def get_pressure_state(row):
        key = (row["price_dir"], row["inv_dir"])
        state_info = PRESSURE_STATES.get(key, PRESSURE_STATES[("FLAT", "FLAT")])
        return state_info["state"]

    df["pressure_state"] = df.apply(get_pressure_state, axis=1)

    # 5️⃣ State persistence (streak days)
    df["state_streak_days"] = 1
    for i in range(1, len(df)):
        if df.iloc[i]["pressure_state"] == df.iloc[i-1]["pressure_state"]:
            df.iloc[i, df.columns.get_loc("state_streak_days")] = (
                df.iloc[i-1]["state_streak_days"] + 1
            )

    # Round numeric columns
    numeric_cols = [
        "price_pct_1d", "inv_pct_1d", "price_pct_5d", "inv_pct_5d",
        "price_pct_10d", "inv_pct_10d", "MA_price_5", "MA_price_10",
        "MA_inv_5", "MA_inv_10"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].round(2)

    # Reset index to have date as column
    df = df.reset_index()

    return df


def get_simplified_pressure(metal: str) -> Dict:
    """
    Get simplified pressure analysis when full history isn't available.

    Uses current inventory level and recent price action to provide
    basic context while full data accumulates.
    """
    # Get current price data
    price_df = get_price_history(metal, 30)
    if price_df is None or price_df.empty:
        return {"error": f"No price data for {metal}"}

    # Get inventory data
    inv_df = get_inventory_history(metal)

    latest_price = price_df["close_price"].iloc[-1]

    # Calculate price changes from available data
    price_pct_5d = None
    price_pct_10d = None
    if len(price_df) >= 6:
        price_pct_5d = (latest_price / price_df["close_price"].iloc[-6] - 1) * 100
    if len(price_df) >= 11:
        price_pct_10d = (latest_price / price_df["close_price"].iloc[-11] - 1) * 100

    # Get inventory info if available
    inventory_level = None
    inv_date = None
    if inv_df is not None and not inv_df.empty:
        inventory_level = inv_df["inventory_level"].iloc[-1]
        inv_date = inv_df.index[-1].strftime("%Y-%m-%d")

    # Determine price direction
    if price_pct_5d is not None:
        price_dir = get_direction(price_pct_5d)
    else:
        price_dir = "UNKNOWN"

    # Can't determine inventory direction with only 1 data point
    inv_dir = "UNKNOWN"

    return {
        "metal": metal,
        "date": price_df.index[-1].strftime("%Y-%m-%d"),
        "close_price": round(latest_price, 2),
        "inventory_level": inventory_level,
        "inventory_date": inv_date,

        # Current state - limited data
        "pressure_state": "Awaiting data",
        "state_emoji": "⏳",
        "state_color": "#9e9e9e",
        "state_description": "Inventory history building. Full pressure analysis requires 10+ days of CME data.",
        "state_action": "Monitor as daily inventory updates accumulate via GitHub Actions.",
        "state_streak_days": None,

        # Direction
        "price_direction": price_dir,
        "inventory_direction": inv_dir,

        # Available metrics
        "price_pct_5d": round(price_pct_5d, 2) if price_pct_5d else None,
        "price_pct_10d": round(price_pct_10d, 2) if price_pct_10d else None,

        # Not available yet
        "price_pct_1d": None,
        "inv_pct_1d": None,
        "inv_pct_5d": None,
        "inv_pct_10d": None,
        "MA_price_5": None,
        "MA_price_10": None,
        "MA_inv_5": None,
        "MA_inv_10": None,
        "price_momentum": None,
        "inv_momentum": None,

        "data_status": "limited",
        "days_of_inventory_data": len(inv_df) if inv_df is not None else 0,
    }


def get_current_pressure(metal: str) -> Dict:
    """
    Get the current pressure state and context for a metal.

    Returns a dict with:
    - current state info
    - key metrics
    - interpretation

    Note: Works with limited data by providing what's available.
    Full analysis requires 10+ days of inventory data.
    """
    df = compute_pressure_table(metal)

    # If we don't have enough data for full analysis, try simplified version
    if df is None or df.empty:
        return get_simplified_pressure(metal)

    # Get the latest row
    latest = df.iloc[-1]

    # Get state info
    price_dir = latest["price_dir"]
    inv_dir = latest["inv_dir"]
    key = (price_dir, inv_dir)
    state_info = PRESSURE_STATES.get(key, PRESSURE_STATES[("FLAT", "FLAT")])

    # Momentum context
    price_momentum = "strengthening" if latest["MA_price_5"] > latest["MA_price_10"] else "weakening"
    inv_momentum = "accelerating drawdown" if latest["MA_inv_5"] < latest["MA_inv_10"] else "slowing drawdown"

    return {
        "metal": metal,
        "date": latest["date"].strftime("%Y-%m-%d") if pd.notna(latest["date"]) else None,
        "close_price": latest["close_price"],
        "inventory_level": latest["inventory_level"],

        # Current state
        "pressure_state": state_info["state"],
        "state_emoji": state_info["emoji"],
        "state_color": state_info["color"],
        "state_description": state_info["description"],
        "state_action": state_info["action"],
        "state_streak_days": int(latest["state_streak_days"]),

        # Direction
        "price_direction": price_dir,
        "inventory_direction": inv_dir,

        # Key metrics
        "price_pct_1d": latest["price_pct_1d"],
        "price_pct_5d": latest["price_pct_5d"],
        "price_pct_10d": latest["price_pct_10d"],

        "inv_pct_1d": latest["inv_pct_1d"],
        "inv_pct_5d": latest["inv_pct_5d"],
        "inv_pct_10d": latest["inv_pct_10d"],

        # Momentum
        "MA_price_5": latest["MA_price_5"],
        "MA_price_10": latest["MA_price_10"],
        "MA_inv_5": latest["MA_inv_5"],
        "MA_inv_10": latest["MA_inv_10"],

        "price_momentum": price_momentum,
        "inv_momentum": inv_momentum,
    }


def get_pressure_table_display(metal: str, rows: int = 20) -> Optional[pd.DataFrame]:
    """
    Get a display-ready pressure table for the last N days.

    Returns DataFrame formatted for Streamlit display.
    """
    df = compute_pressure_table(metal)

    if df is None or df.empty:
        return None

    # Select and rename columns for display
    display_cols = [
        "date", "close_price", "inventory_level",
        "price_pct_5d", "inv_pct_5d",
        "pressure_state", "state_streak_days"
    ]

    display_df = df[display_cols].tail(rows).copy()

    # Format date
    display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")

    # Rename columns for display
    display_df.columns = [
        "Date", "Price", "Inventory",
        "Price 5D%", "Inv 5D%",
        "Pressure State", "Streak"
    ]

    return display_df


if __name__ == "__main__":
    print("=== Price vs Inventory Pressure Analysis ===\n")

    for metal in ["gold", "silver", "copper", "platinum", "palladium"]:
        print(f"\n--- {metal.upper()} ---")

        pressure = get_current_pressure(metal)

        if "error" in pressure:
            print(f"  Error: {pressure['error']}")
            continue

        print(f"  Date: {pressure['date']}")
        print(f"  Price: ${pressure['close_price']:.2f}")
        inv = pressure.get('inventory_level')
        print(f"  Inventory: {inv:,.0f}" if inv else "  Inventory: N/A")
        print()
        print(f"  State: {pressure['state_emoji']} {pressure['pressure_state']}")
        streak = pressure.get('state_streak_days')
        print(f"  Streak: {streak} days" if streak else "  Streak: N/A")
        print()

        price_5d = pressure.get('price_pct_5d')
        inv_5d = pressure.get('inv_pct_5d')
        print(f"  Price 5D: {price_5d:+.2f}% ({pressure['price_direction']})" if price_5d else f"  Price 5D: N/A ({pressure['price_direction']})")
        print(f"  Inv 5D: {inv_5d:+.2f}% ({pressure['inventory_direction']})" if inv_5d else f"  Inv 5D: N/A ({pressure['inventory_direction']})")
        print()
        print(f"  {pressure['state_description']}")
        print(f"  Action: {pressure['state_action']}")

        # Show data status if limited
        if pressure.get('data_status') == 'limited':
            days = pressure.get('days_of_inventory_data', 0)
            print(f"\n  [Data Status: {days} day(s) of inventory data - need 10+ for full analysis]")

    print("\n=== Test Complete ===")
