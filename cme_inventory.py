"""
CME Inventory Data Module

Provides functions to load, analyze, and generate signals from CME warehouse
inventory data for Gold, Silver, Copper, Platinum, and Palladium.

Implements the analytical framework from inventory_data.md:
- Inventory is a constraint, not a signal
- Track rate of change (5D, 20D)
- Combine with price trend and macro for decision matrix

Usage:
    from cme_inventory import get_latest_inventory, get_inventory_state, get_inventory_signal

    gold = get_latest_inventory("gold")
    state = get_inventory_state("gold")
    signal = get_inventory_signal("gold", price_trend="rising", macro_state="supportive")
"""
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, List, Literal
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).resolve().parent / "data"
INVENTORY_CSV = DATA_DIR / "cme_inventory.csv"

# Type definitions
InventoryState = Literal["drawdown", "flat", "build"]
PriceTrend = Literal["rising", "flat", "falling"]
MacroState = Literal["supportive", "neutral", "hostile"]
SignalStrength = Literal["strong_positive", "breakout_risk", "caution", "negative", "neutral"]


def load_inventory() -> pd.DataFrame:
    """Load inventory CSV, return empty DataFrame if not exists."""
    if not INVENTORY_CSV.exists():
        return pd.DataFrame()

    df = pd.read_csv(INVENTORY_CSV, parse_dates=["date"])
    df = df.sort_values(["metal", "date", "warehouse"])
    return df


def get_grand_totals(metal: str) -> pd.DataFrame:
    """Get total rows for a metal, sorted by date.

    Looks for GRAND_TOTAL or TOTAL warehouse entries.
    If neither exists, aggregates from individual warehouses.
    """
    df = load_inventory()
    if df.empty:
        return pd.DataFrame()

    metal_df = df[df["metal"] == metal.lower()]
    if metal_df.empty:
        return pd.DataFrame()

    # Try GRAND_TOTAL first, then TOTAL
    for warehouse_name in ["GRAND_TOTAL", "TOTAL"]:
        mask = metal_df["warehouse"] == warehouse_name
        if mask.any():
            result = metal_df[mask].copy()
            result = result.sort_values("date")
            return result

    # Fallback: aggregate by date (sum all warehouses)
    agg_df = metal_df.groupby("date").agg({
        "registered": "sum",
        "eligible": "sum",
        "total": "sum",
        "received": "sum",
        "withdrawn": "sum",
        "net_change": "sum",
    }).reset_index()
    agg_df["metal"] = metal.lower()
    agg_df["warehouse"] = "AGGREGATED"
    agg_df = agg_df.sort_values("date")
    return agg_df


def get_latest_inventory(metal: str) -> Optional[Dict]:
    """
    Get most recent inventory data for a metal.

    Args:
        metal: "gold", "silver", "copper", "platinum", or "palladium"

    Returns:
        Dict with latest inventory data including 5D/20D changes, or None if not available.
    """
    totals = get_grand_totals(metal)
    if totals.empty:
        return None

    latest = totals.iloc[-1]

    # Calculate changes
    change_5d = None
    change_5d_pct = None
    change_20d = None
    change_20d_pct = None

    current_total = latest["total"]

    if len(totals) >= 2:
        # Find record from ~5 days ago
        target_date_5d = latest["date"] - timedelta(days=5)
        older_5d = totals[totals["date"] <= target_date_5d]
        if not older_5d.empty:
            prev_5d = older_5d.iloc[-1]["total"]
            if prev_5d and current_total:
                change_5d = current_total - prev_5d
                change_5d_pct = (change_5d / prev_5d) * 100

    if len(totals) >= 5:
        # Find record from ~20 days ago
        target_date_20d = latest["date"] - timedelta(days=20)
        older_20d = totals[totals["date"] <= target_date_20d]
        if not older_20d.empty:
            prev_20d = older_20d.iloc[-1]["total"]
            if prev_20d and current_total:
                change_20d = current_total - prev_20d
                change_20d_pct = (change_20d / prev_20d) * 100

    return {
        "date": latest["date"].strftime("%Y-%m-%d") if pd.notna(latest["date"]) else None,
        "metal": metal.lower(),
        "registered": int(latest["registered"]) if pd.notna(latest["registered"]) else None,
        "eligible": int(latest["eligible"]) if pd.notna(latest["eligible"]) else None,
        "total": int(latest["total"]) if pd.notna(latest["total"]) else None,
        "received": int(latest["received"]) if pd.notna(latest["received"]) else None,
        "withdrawn": int(latest["withdrawn"]) if pd.notna(latest["withdrawn"]) else None,
        "net_change": int(latest["net_change"]) if pd.notna(latest["net_change"]) else None,
        "change_5d": int(change_5d) if change_5d is not None else None,
        "change_5d_pct": round(change_5d_pct, 2) if change_5d_pct is not None else None,
        "change_20d": int(change_20d) if change_20d is not None else None,
        "change_20d_pct": round(change_20d_pct, 2) if change_20d_pct is not None else None,
    }


def get_inventory_state(metal: str) -> Optional[Dict]:
    """
    Determine inventory state based on rate of change.

    States (from inventory_data.md):
    - drawdown: Inventories falling consistently (5D < -1% AND 20D < -3%)
    - build: Inventories rising steadily (5D > +1% AND 20D > +3%)
    - flat: Oscillating, no clear trend

    Returns:
        Dict with state and description, or None if insufficient data.
    """
    inv = get_latest_inventory(metal)
    if inv is None:
        return None

    change_5d_pct = inv.get("change_5d_pct")
    change_20d_pct = inv.get("change_20d_pct")

    # Need both metrics for state determination
    if change_5d_pct is None or change_20d_pct is None:
        return {
            "state": "unknown",
            "description": "Insufficient data for state determination",
            "emoji": "⚪",
            "color": "#888888",
        }

    # Determine state based on thresholds
    if change_5d_pct < -1 and change_20d_pct < -3:
        return {
            "state": "drawdown",
            "description": "Inventories falling consistently - bullish pressure building",
            "emoji": "🟢",
            "color": "#00c853",
            "interpretation": "Physical metal being absorbed faster than replenished. Constructive even if price hasn't moved.",
        }
    elif change_5d_pct > 1 and change_20d_pct > 3:
        return {
            "state": "build",
            "description": "Inventories rising steadily - bearish pressure",
            "emoji": "🔴",
            "color": "#ff5252",
            "interpretation": "Supply exceeding demand. Rallies vulnerable.",
        }
    else:
        return {
            "state": "flat",
            "description": "Inventories oscillating - no clear trend",
            "emoji": "🟡",
            "color": "#ffc107",
            "interpretation": "Physical market balanced. Price driven by macro/specs.",
        }


def get_inventory_signal(
    metal: str,
    price_trend: PriceTrend,
    macro_state: MacroState
) -> Optional[Dict]:
    """
    Generate combined signal based on inventory + price + macro.

    Implements the decision matrix from inventory_data.md.

    Args:
        metal: "gold", "silver", "copper", "platinum", or "palladium"
        price_trend: "rising", "flat", or "falling"
        macro_state: "supportive", "neutral", or "hostile"

    Returns:
        Dict with signal, strength, and action guidance.
    """
    inv_state = get_inventory_state(metal)
    if inv_state is None or inv_state["state"] == "unknown":
        return None

    state = inv_state["state"]

    # Decision matrix from inventory_data.md
    # Scenario A: Inventories falling + price rising = Best case
    if state == "drawdown" and price_trend == "rising":
        return {
            "signal": "strong_positive",
            "strength": "high",
            "emoji": "🟢",
            "color": "#00c853",
            "title": "Strong Positive",
            "description": f"Falling inventory + rising price{' + supportive macro' if macro_state == 'supportive' else ''}",
            "action": "Hold / add on pullbacks. Do NOT fade strength.",
            "confidence": "high" if macro_state == "supportive" else "medium",
        }

    # Scenario B: Inventories falling + price flat = Pressure cooker
    if state == "drawdown" and price_trend == "flat":
        return {
            "signal": "breakout_risk",
            "strength": "medium",
            "emoji": "🟡",
            "color": "#ffc107",
            "title": "Breakout Risk",
            "description": "Falling inventory + flat price = pressure building",
            "action": "Prepare for breakout. Do not short. Watch for participation expansion.",
            "confidence": "medium",
        }

    # Scenario C: Inventories rising + price rising = Warning
    if state == "build" and price_trend == "rising":
        return {
            "signal": "caution",
            "strength": "medium",
            "emoji": "🟠",
            "color": "#ff9800",
            "title": "Caution",
            "description": "Rising inventory + rising price = rally not physically supported",
            "action": "Reduce size. Tighten invalidation. Look for reversal signs.",
            "confidence": "medium",
        }

    # Scenario D: Inventories rising + price falling = Confirmed weakness
    if state == "build" and price_trend == "falling":
        return {
            "signal": "negative",
            "strength": "high",
            "emoji": "🔴",
            "color": "#ff5252",
            "title": "Negative",
            "description": f"Rising inventory + falling price{' + hostile macro' if macro_state == 'hostile' else ''}",
            "action": "Avoid longs. Short rallies if you trade short.",
            "confidence": "high" if macro_state == "hostile" else "medium",
        }

    # Drawdown + falling = potentially bottoming
    if state == "drawdown" and price_trend == "falling":
        return {
            "signal": "divergence_bullish",
            "strength": "medium",
            "emoji": "🟡",
            "color": "#ffc107",
            "title": "Bullish Divergence",
            "description": "Falling inventory despite falling price = physical demand absorbing weakness",
            "action": "Watch for price stabilization. Potential bottoming setup.",
            "confidence": "medium",
        }

    # Build + flat = overhead supply
    if state == "build" and price_trend == "flat":
        return {
            "signal": "overhead_supply",
            "strength": "low",
            "emoji": "🟠",
            "color": "#ff9800",
            "title": "Overhead Supply",
            "description": "Rising inventory + flat price = supply accumulating",
            "action": "Breakouts likely to fail. Range-bound expected.",
            "confidence": "low",
        }

    # Default neutral
    return {
        "signal": "neutral",
        "strength": "low",
        "emoji": "⚪",
        "color": "#888888",
        "title": "Neutral",
        "description": f"Inventory {state}, price {price_trend}",
        "action": "No clear edge. Wait for clearer setup.",
        "confidence": "low",
    }


def get_inventory_trend(metal: str, days: int = 30) -> pd.DataFrame:
    """
    Get inventory trend for charting.

    Args:
        metal: "gold", "silver", "copper", "platinum", or "palladium"
        days: Number of days to include

    Returns:
        DataFrame with date index and inventory columns.
    """
    totals = get_grand_totals(metal)
    if totals.empty:
        return pd.DataFrame()

    # Filter to recent days
    cutoff = datetime.now() - timedelta(days=days)
    totals = totals[totals["date"] >= cutoff]

    if totals.empty:
        return pd.DataFrame()

    # Prepare for charting
    result = totals.set_index("date")[["total", "registered", "eligible"]]
    result.columns = ["Total", "Registered", "Eligible"]

    return result


def get_warehouse_breakdown(metal: str, date: str = None) -> pd.DataFrame:
    """
    Get per-warehouse breakdown for a specific date.

    Args:
        metal: "gold", "silver", "copper", "platinum", or "palladium"
        date: Specific date (YYYY-MM-DD) or None for latest

    Returns:
        DataFrame with warehouse breakdown.
    """
    df = load_inventory()
    if df.empty:
        return pd.DataFrame()

    metal_df = df[df["metal"] == metal.lower()]
    if metal_df.empty:
        return pd.DataFrame()

    if date:
        metal_df = metal_df[metal_df["date"] == date]
    else:
        # Get latest date
        latest_date = metal_df["date"].max()
        metal_df = metal_df[metal_df["date"] == latest_date]

    # Exclude GRAND_TOTAL for breakdown view
    result = metal_df[metal_df["warehouse"] != "GRAND_TOTAL"].copy()
    result = result[["warehouse", "registered", "eligible", "total", "net_change"]]
    result = result.sort_values("total", ascending=False)

    return result


def get_all_metals_summary() -> List[Dict]:
    """
    Get summary for all metals (for dashboard display).

    Returns:
        List of dicts with latest inventory + state for each metal.
    """
    summaries = []

    for metal in ["gold", "silver", "copper", "platinum", "palladium"]:
        inv = get_latest_inventory(metal)
        state = get_inventory_state(metal)

        if inv:
            summaries.append({
                "metal": metal,
                "inventory": inv,
                "state": state,
            })

    return summaries


def get_inventory_history_table(days: int = 10) -> pd.DataFrame:
    """
    Get inventory history for all metals as a table for display.

    Returns a DataFrame with dates as rows and metals as columns,
    showing total inventory with day-over-day % change in brackets.

    Args:
        days: Number of days to include (default 10)

    Returns:
        DataFrame formatted for display with dates descending.
    """
    metals = ["gold", "silver", "copper", "platinum", "palladium"]
    all_data = {}

    for metal in metals:
        totals = get_grand_totals(metal)
        if totals.empty:
            continue

        # Get last N days of data
        totals = totals.sort_values("date", ascending=False).head(days)

        # Calculate day-over-day % change
        totals = totals.sort_values("date", ascending=True)
        totals["pct_change"] = totals["total"].pct_change() * 100

        # Format as "value (change%)"
        formatted = []
        for _, row in totals.iterrows():
            total = row["total"]
            pct = row["pct_change"]

            if pd.isna(total):
                formatted.append("N/A")
            elif pd.isna(pct):
                # First row has no previous day
                formatted.append(f"{total:,.0f}")
            else:
                sign = "+" if pct >= 0 else ""
                formatted.append(f"{total:,.0f} ({sign}{pct:.2f}%)")

        # Store with date index
        totals = totals.sort_values("date", ascending=False)
        dates = totals["date"].dt.strftime("%Y-%m-%d").tolist()
        formatted.reverse()  # Match descending date order

        all_data[metal.capitalize()] = dict(zip(dates, formatted))

    if not all_data:
        return pd.DataFrame()

    # Build DataFrame from all metals
    df = pd.DataFrame(all_data)

    # Sort index (dates) descending
    df = df.sort_index(ascending=False)

    return df


if __name__ == "__main__":
    # Test functions
    print("=== CME Inventory Module Test ===\n")

    for metal in ["gold", "silver", "copper", "platinum", "palladium"]:
        print(f"\n--- {metal.upper()} ---")

        inv = get_latest_inventory(metal)
        if inv:
            print(f"Latest: {inv['date']}")
            print(f"  Total: {inv['total']:,}" if inv['total'] else "  Total: N/A")
            print(f"  5D change: {inv['change_5d_pct']}%" if inv['change_5d_pct'] else "  5D change: N/A")
            print(f"  20D change: {inv['change_20d_pct']}%" if inv['change_20d_pct'] else "  20D change: N/A")

            state = get_inventory_state(metal)
            if state:
                print(f"  State: {state['emoji']} {state['state'].upper()}")

            # Test signal generation
            signal = get_inventory_signal(metal, "rising", "supportive")
            if signal:
                print(f"  Signal (rising/supportive): {signal['emoji']} {signal['title']}")
        else:
            print("  No data available")

    print("\n=== Test Complete ===")
