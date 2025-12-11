"""
Term Structure (Futures Curve) Analysis for Precious Metals.

Analyzes the relationship between spot and futures prices to determine:
- Contango vs Backwardation
- Spot-to-futures spread
- Annualized roll yield/cost
- Market structure signal

Contango: Futures > Spot (normal for gold/silver due to storage/carry costs)
Backwardation: Spot > Futures (indicates physical tightness/strong demand)
"""
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Futures tickers
GOLD_FUTURES = "GC=F"
SILVER_FUTURES = "SI=F"
COPPER_FUTURES = "HG=F"


def get_futures_price(ticker: str) -> Optional[float]:
    """Fetch current futures price from Yahoo Finance."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def calculate_annualized_basis(spot: float, futures: float, days_to_expiry: int = 30) -> float:
    """
    Calculate annualized basis (roll yield).

    Positive = contango (cost to roll)
    Negative = backwardation (yield from rolling)
    """
    if spot == 0 or days_to_expiry == 0:
        return 0.0

    # Simple annualization
    basis_pct = ((futures - spot) / spot) * 100
    annualized = basis_pct * (365 / days_to_expiry)
    return annualized


def classify_structure(spot: float, futures: float) -> Dict[str, str]:
    """
    Classify the term structure.

    Returns dict with structure type and market interpretation.
    """
    if spot is None or futures is None:
        return {
            "structure": "unknown",
            "interpretation": "insufficient data",
            "signal": "neutral",
        }

    spread = futures - spot
    spread_pct = (spread / spot) * 100 if spot > 0 else 0

    if spread_pct > 0.5:
        # Contango - futures premium
        if spread_pct > 3:
            return {
                "structure": "steep contango",
                "interpretation": "high carry costs, weak physical demand",
                "signal": "bearish",
            }
        elif spread_pct > 1:
            return {
                "structure": "contango",
                "interpretation": "normal carry market",
                "signal": "neutral",
            }
        else:
            return {
                "structure": "mild contango",
                "interpretation": "near flat, balanced market",
                "signal": "neutral",
            }
    elif spread_pct < -0.5:
        # Backwardation - spot premium
        if spread_pct < -3:
            return {
                "structure": "steep backwardation",
                "interpretation": "severe physical tightness, strong demand",
                "signal": "strongly bullish",
            }
        elif spread_pct < -1:
            return {
                "structure": "backwardation",
                "interpretation": "physical tightness, demand > supply",
                "signal": "bullish",
            }
        else:
            return {
                "structure": "mild backwardation",
                "interpretation": "slight physical tightness",
                "signal": "mildly bullish",
            }
    else:
        return {
            "structure": "flat",
            "interpretation": "balanced spot/futures",
            "signal": "neutral",
        }


def analyze_term_structure(
    metal: str = "gold",
    spot_price: float = None,
    days_to_expiry: int = 30
) -> Dict[str, Any]:
    """
    Analyze term structure for a metal.

    Args:
        metal: "gold" or "silver"
        spot_price: Current spot price (from Gold-API). If None, uses futures as proxy.
        days_to_expiry: Approximate days until front-month expiry (default 30)

    Returns:
        Dict with term structure analysis
    """
    # Get futures price
    metal_lower = metal.lower()
    if metal_lower == "gold":
        futures_ticker = GOLD_FUTURES
    elif metal_lower == "silver":
        futures_ticker = SILVER_FUTURES
    elif metal_lower == "copper":
        futures_ticker = COPPER_FUTURES
    else:
        return {"error": f"Unknown metal: {metal}"}
    futures_price = get_futures_price(futures_ticker)

    if futures_price is None:
        return {"error": f"Could not fetch {metal} futures price"}

    # Use spot_price if provided, otherwise estimate from futures
    # (In contango, spot is typically ~0.5-2% below futures for gold)
    if spot_price is None:
        # Rough estimate: assume 1% contango
        spot_price = futures_price * 0.99
        spot_source = "estimated"
    else:
        spot_source = "gold-api"

    # Calculate spread
    spread = futures_price - spot_price
    spread_pct = (spread / spot_price) * 100 if spot_price > 0 else 0

    # Classify structure
    structure = classify_structure(spot_price, futures_price)

    # Calculate annualized basis
    annualized_basis = calculate_annualized_basis(spot_price, futures_price, days_to_expiry)

    # Roll yield interpretation
    if annualized_basis > 0:
        roll_impact = "negative carry (cost to hold futures)"
    elif annualized_basis < 0:
        roll_impact = "positive carry (yield from rolling)"
    else:
        roll_impact = "flat"

    return {
        "metal": metal,
        "spot_price": spot_price,
        "spot_source": spot_source,
        "futures_price": futures_price,
        "futures_ticker": futures_ticker,
        "spread": spread,
        "spread_pct": spread_pct,
        "structure": structure["structure"],
        "interpretation": structure["interpretation"],
        "signal": structure["signal"],
        "annualized_basis_pct": annualized_basis,
        "roll_impact": roll_impact,
        "days_to_expiry": days_to_expiry,
    }


def get_term_structure_summary() -> Dict[str, Any]:
    """
    Get term structure analysis for gold, silver, and copper.
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "gold": analyze_term_structure("gold"),
        "silver": analyze_term_structure("silver"),
        "copper": analyze_term_structure("copper"),
    }


if __name__ == "__main__":
    print("=== Term Structure Analysis ===\n")

    # Test with sample spot prices (would come from Gold-API in real use)
    gold = analyze_term_structure("gold", spot_price=4193.0)
    silver = analyze_term_structure("silver", spot_price=60.5)

    for metal, data in [("GOLD", gold), ("SILVER", silver)]:
        if "error" in data:
            print(f"{metal}: {data['error']}")
            continue

        print(f"=== {metal} ===")
        print(f"  Spot:     ${data['spot_price']:,.2f} ({data['spot_source']})")
        print(f"  Futures:  ${data['futures_price']:,.2f} ({data['futures_ticker']})")
        print(f"  Spread:   ${data['spread']:+,.2f} ({data['spread_pct']:+.2f}%)")
        print(f"  Structure: {data['structure'].upper()}")
        print(f"  Interpretation: {data['interpretation']}")
        print(f"  Signal: {data['signal']}")
        print(f"  Annualized Basis: {data['annualized_basis_pct']:+.2f}%")
        print(f"  Roll Impact: {data['roll_impact']}")
        print()
