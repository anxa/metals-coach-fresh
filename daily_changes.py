"""
Daily Changes Detection Module

Identifies meaningful state changes across all metals to help returning users
quickly understand what's different from yesterday.

Change types detected:
- Price moves: >1% daily change
- Signal flips: Verdict changed
- Indicator crossovers: RSI crosses 50/70/30, MACD crosses signal
- Inventory changes: >1% daily change
- Pressure state changes: State changed
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime

from data_store import get_yesterday_spot_close

# Symbol mapping for spot price history lookup
METAL_SYMBOLS = {
    "gold": "XAU",
    "silver": "XAG",
    "copper": "HG",
    "platinum": "XPT",
    "palladium": "XPD",
}

# Emoji mappings for metals
METAL_EMOJIS = {
    "gold": "🥇",
    "silver": "🥈",
    "copper": "🔶",
    "platinum": "⚪",
    "palladium": "⬜",
}


def detect_price_change(metal: str, spot_price: float = None, ind: dict = None, threshold: float = 1.0) -> Optional[str]:
    """
    Detect significant daily price changes using spot-to-spot comparison.

    Compares today's live spot price against yesterday's spot close from
    Gold-API history, ensuring an apples-to-apples comparison.

    Falls back to futures data if spot history isn't available (e.g., platinum).

    Args:
        metal: Metal name (gold, silver, copper, platinum, palladium)
        spot_price: Current live spot price from Gold-API
        ind: Indicator dict with futures history (fallback for metals like platinum)
        threshold: Minimum % change to report (default 1.0%)

    Returns:
        Change description string, or None if no significant change
    """
    if spot_price is None:
        return None

    # Get yesterday's spot close from our Gold-API history
    symbol = METAL_SYMBOLS.get(metal)
    if not symbol:
        return None

    yesterday_close = get_yesterday_spot_close(symbol)

    # Fallback to futures data for metals without spot history (e.g., platinum)
    if yesterday_close is None and ind is not None and "error" not in ind:
        hist = ind.get("history")
        if hist is not None and len(hist) >= 2:
            yesterday_close = hist["Close"].iloc[-2]

    if yesterday_close is None:
        return None

    # Calculate change
    pct_change = ((spot_price / yesterday_close) - 1) * 100

    if abs(pct_change) >= threshold:
        direction = "up" if pct_change > 0 else "down"
        return f"Price {direction} {abs(pct_change):.1f}%"

    return None


def detect_rsi_crossover(ind: dict) -> Optional[str]:
    """Detect RSI crossing key levels (30, 50, 70)."""
    if "error" in ind:
        return None

    rsi_momentum = ind.get("rsi_momentum", {})
    if "error" in rsi_momentum:
        return None

    rsi = ind.get("rsi14")
    prev_rsi = rsi_momentum.get("prev_rsi")

    if rsi is None or prev_rsi is None:
        return None

    # Check for crossovers
    if prev_rsi < 50 and rsi >= 50:
        return "RSI crossed above 50 (bullish)"
    elif prev_rsi > 50 and rsi <= 50:
        return "RSI crossed below 50 (bearish)"
    elif prev_rsi < 70 and rsi >= 70:
        return "RSI entered overbought (>70)"
    elif prev_rsi > 70 and rsi <= 70:
        return "RSI exited overbought"
    elif prev_rsi > 30 and rsi <= 30:
        return "RSI entered oversold (<30)"
    elif prev_rsi < 30 and rsi >= 30:
        return "RSI exited oversold"

    return None


def detect_macd_crossover(ind: dict) -> Optional[str]:
    """Detect MACD signal line crossovers."""
    if "error" in ind:
        return None

    macd_momentum = ind.get("macd_momentum", {})
    if "error" in macd_momentum:
        return None

    crossover = macd_momentum.get("crossover_detected", False)
    bars_since = macd_momentum.get("bars_since_crossover", 0)

    # Only report if crossover happened very recently (within 1-2 bars)
    if crossover and bars_since <= 2:
        direction = macd_momentum.get("crossover_direction", "")
        if direction == "bullish":
            return "MACD bullish crossover"
        elif direction == "bearish":
            return "MACD bearish crossover"

    return None


def detect_obv_divergence(ind: dict) -> Optional[str]:
    """Detect OBV divergences."""
    if "error" in ind:
        return None

    obv_momentum = ind.get("obv_momentum", {})
    divergence = obv_momentum.get("divergence")

    if divergence:
        return f"OBV {divergence} divergence detected"

    return None


def detect_inventory_change(pressure: dict, threshold: float = 1.0) -> Optional[str]:
    """Detect significant inventory changes."""
    if "error" in pressure or pressure.get("data_status") == "limited":
        return None

    inv_pct_1d = pressure.get("inv_pct_1d")
    if inv_pct_1d is None:
        return None

    if abs(inv_pct_1d) >= threshold:
        direction = "down" if inv_pct_1d < 0 else "up"
        # Inventory down = bullish for price
        signal = "(bullish)" if inv_pct_1d < 0 else "(bearish)"
        return f"Inventory {direction} {abs(inv_pct_1d):.1f}% {signal}"

    return None


def detect_pressure_state_persistence(pressure: dict) -> Optional[str]:
    """Highlight long-running pressure states."""
    if "error" in pressure or pressure.get("data_status") == "limited":
        return None

    streak = pressure.get("state_streak_days")
    state = pressure.get("pressure_state")

    # Highlight if streak hits 5 or 10 days
    if streak in [5, 10]:
        return f"{state} state for {streak} consecutive days"

    return None


def get_all_changes(
    gold_ind: dict, silver_ind: dict, copper_ind: dict,
    platinum_ind: dict, palladium_ind: dict,
    copper_pressure: dict = None, platinum_pressure: dict = None,
    palladium_pressure: dict = None,
    gold_price: float = None, silver_price: float = None,
    copper_price: float = None, platinum_price: float = None,
    palladium_price: float = None
) -> Dict[str, List[str]]:
    """
    Get all significant changes across all metals.

    Args:
        *_ind: Indicator data for each metal
        *_pressure: Pressure/inventory data for copper, platinum, palladium
        *_price: Live spot prices for accurate daily change calculation

    Returns dict mapping metal name to list of change descriptions.
    """
    changes = {
        "gold": [],
        "silver": [],
        "copper": [],
        "platinum": [],
        "palladium": [],
    }

    # Check each metal (name, indicators, pressure, spot_price)
    metals_data = [
        ("gold", gold_ind, None, gold_price),
        ("silver", silver_ind, None, silver_price),
        ("copper", copper_ind, copper_pressure, copper_price),
        ("platinum", platinum_ind, platinum_pressure, platinum_price),
        ("palladium", palladium_ind, palladium_pressure, palladium_price),
    ]

    for metal, ind, pressure, spot_price in metals_data:
        # Price changes - use spot-to-spot comparison, with futures fallback for platinum
        price_change = detect_price_change(metal, spot_price, ind)
        if price_change:
            changes[metal].append(price_change)

        # RSI crossovers
        rsi_cross = detect_rsi_crossover(ind)
        if rsi_cross:
            changes[metal].append(rsi_cross)

        # MACD crossovers
        macd_cross = detect_macd_crossover(ind)
        if macd_cross:
            changes[metal].append(macd_cross)

        # OBV divergence
        obv_div = detect_obv_divergence(ind)
        if obv_div:
            changes[metal].append(obv_div)

        # Inventory changes (for metals with pressure data)
        if pressure:
            inv_change = detect_inventory_change(pressure)
            if inv_change:
                changes[metal].append(inv_change)

            # Pressure state persistence
            state_persist = detect_pressure_state_persistence(pressure)
            if state_persist:
                changes[metal].append(state_persist)

    return changes


def format_changes_html(changes: Dict[str, List[str]], date_str: str = None) -> str:
    """
    Format changes as HTML for Streamlit display.

    Returns an HTML string with the changes formatted nicely.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%b %d")

    # Check if there are any changes
    has_changes = any(len(c) > 0 for c in changes.values())

    if not has_changes:
        html_parts = [
            '<div style="background: linear-gradient(145deg, #1a2332 0%, #1e2940 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #666; margin-bottom: 16px;">',
            f'<div style="color: #888; font-size: 0.9rem; margin-bottom: 8px;">📊 What Changed Today ({date_str})</div>',
            '<div style="color: #aaa; font-size: 0.95rem;">No significant changes detected. Markets are quiet.</div>',
            '</div>'
        ]
        return ''.join(html_parts)

    # Build the change items
    items_html_parts = []
    no_changes_metals = []

    for metal, metal_changes in changes.items():
        emoji = METAL_EMOJIS.get(metal, "•")
        if metal_changes:
            change_text = ", ".join(metal_changes)
            items_html_parts.append(
                f'<div style="color: #fff; font-size: 0.95rem; margin: 8px 0; padding-left: 8px;">'
                f'{emoji} <strong>{metal.title()}:</strong> {change_text}</div>'
            )
        else:
            no_changes_metals.append(metal.title())

    # Add "no changes" line if some metals had no changes
    if no_changes_metals:
        items_html_parts.append(
            f'<div style="color: #666; font-size: 0.85rem; margin-top: 12px; padding-left: 8px;">'
            f'No significant changes: {", ".join(no_changes_metals)}</div>'
        )

    items_html = ''.join(items_html_parts)

    html_parts = [
        '<div style="background: linear-gradient(145deg, #1a2332 0%, #1e2940 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #00c853; margin-bottom: 16px;">',
        f'<div style="color: #888; font-size: 0.9rem; margin-bottom: 12px;">📊 What Changed Today ({date_str})</div>',
        items_html,
        '</div>'
    ]
    return ''.join(html_parts)


if __name__ == "__main__":
    # Test with sample data
    print("Daily Changes Module - Test")
    print("=" * 40)

    # Simulate some changes
    sample_changes = {
        "gold": ["Price up 1.2%", "RSI crossed above 50 (bullish)"],
        "silver": [],
        "copper": ["Inventory down 2.1% (bullish)"],
        "platinum": ["MACD bearish crossover"],
        "palladium": [],
    }

    html = format_changes_html(sample_changes)
    print("Generated HTML:")
    print(html)
