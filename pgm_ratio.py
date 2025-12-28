"""
Platinum/Palladium Ratio Analysis Module

Calculates and analyzes the Pt/Pd price ratio to identify relative value
opportunities between platinum and palladium.

Historical context:
- Platinum was traditionally more expensive than palladium (ratio > 1)
- Since 2017, palladium often traded at a premium (ratio < 1)
- Extreme ratio readings can signal mean reversion opportunities
"""
import yfinance as yf
import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta


def get_ptpd_ratio_data(years: int = 5) -> Optional[pd.DataFrame]:
    """
    Fetch historical Pt/Pd ratio data.

    Args:
        years: Number of years of history to fetch

    Returns:
        DataFrame with platinum, palladium prices and ratio, or None if error.
    """
    try:
        pt = yf.Ticker("PL=F")
        pd_metal = yf.Ticker("PA=F")

        pt_hist = pt.history(period=f"{years}y")
        pd_hist = pd_metal.history(period=f"{years}y")

        if pt_hist.empty or pd_hist.empty:
            return None

        # Merge on date index
        merged = pd.DataFrame({
            "platinum": pt_hist["Close"],
            "palladium": pd_hist["Close"]
        }).dropna()

        if merged.empty:
            return None

        merged["ratio"] = merged["platinum"] / merged["palladium"]

        return merged

    except Exception as e:
        print(f"Error fetching Pt/Pd ratio data: {e}")
        return None


def analyze_ptpd_ratio(pt_price: float = None, pd_price: float = None) -> Dict:
    """
    Analyze the current Pt/Pd ratio against historical levels.

    Args:
        pt_price: Current platinum price (optional, will fetch if not provided)
        pd_price: Current palladium price (optional, will fetch if not provided)

    Returns:
        Dict with ratio analysis including:
        - current_ratio
        - percentile (where current ratio sits in 5-year history)
        - mean, min, max
        - signal for each metal
        - trend data for charting
    """
    df = get_ptpd_ratio_data(years=5)

    if df is None or df.empty:
        return {"error": "Could not fetch ratio data"}

    # Use provided prices or latest from data
    if pt_price and pd_price:
        current_ratio = pt_price / pd_price
    else:
        current_ratio = df["ratio"].iloc[-1]
        pt_price = df["platinum"].iloc[-1]
        pd_price = df["palladium"].iloc[-1]

    # Calculate statistics
    mean_ratio = df["ratio"].mean()
    std_ratio = df["ratio"].std()
    min_ratio = df["ratio"].min()
    max_ratio = df["ratio"].max()

    # Percentile of current ratio
    percentile = (df["ratio"] < current_ratio).mean() * 100

    # Z-score (how many std devs from mean)
    z_score = (current_ratio - mean_ratio) / std_ratio if std_ratio > 0 else 0

    # Determine signal for each metal
    # High ratio = platinum expensive relative to palladium
    # Low ratio = palladium expensive relative to platinum

    if percentile >= 80:
        pt_signal = "expensive"
        pd_signal = "cheap"
        pt_color = "#ff5252"  # red
        pd_color = "#00c853"  # green
        interpretation = "Platinum historically expensive vs Palladium - potential mean reversion to Pd"
    elif percentile <= 20:
        pt_signal = "cheap"
        pd_signal = "expensive"
        pt_color = "#00c853"
        pd_color = "#ff5252"
        interpretation = "Platinum historically cheap vs Palladium - potential mean reversion to Pt"
    else:
        pt_signal = "fair"
        pd_signal = "fair"
        pt_color = "#ffc107"  # yellow
        pd_color = "#ffc107"
        interpretation = "Ratio near historical average - no strong relative value signal"

    # Calculate recent trend (20-day change in ratio)
    if len(df) >= 20:
        ratio_20d_ago = df["ratio"].iloc[-20]
        ratio_change_20d = current_ratio - ratio_20d_ago
        ratio_change_20d_pct = (ratio_change_20d / ratio_20d_ago) * 100

        if ratio_change_20d_pct > 5:
            trend = "rising"
            trend_desc = "Platinum strengthening vs Palladium"
        elif ratio_change_20d_pct < -5:
            trend = "falling"
            trend_desc = "Palladium strengthening vs Platinum"
        else:
            trend = "stable"
            trend_desc = "Ratio stable over past 20 days"
    else:
        ratio_change_20d = None
        ratio_change_20d_pct = None
        trend = "unknown"
        trend_desc = "Insufficient data for trend"

    # Prepare chart data (last 2 years for cleaner visualization)
    chart_df = df.tail(504)  # ~2 years of trading days

    return {
        "current_ratio": round(current_ratio, 3),
        "percentile": round(percentile, 1),
        "z_score": round(z_score, 2),
        "mean": round(mean_ratio, 3),
        "std": round(std_ratio, 3),
        "min": round(min_ratio, 3),
        "max": round(max_ratio, 3),
        "platinum_price": round(pt_price, 2),
        "palladium_price": round(pd_price, 2),
        "platinum_signal": pt_signal,
        "palladium_signal": pd_signal,
        "platinum_color": pt_color,
        "palladium_color": pd_color,
        "interpretation": interpretation,
        "trend": trend,
        "trend_description": trend_desc,
        "ratio_change_20d": round(ratio_change_20d, 3) if ratio_change_20d else None,
        "ratio_change_20d_pct": round(ratio_change_20d_pct, 1) if ratio_change_20d_pct else None,
        "chart_data": chart_df[["ratio"]].rename(columns={"ratio": "Pt/Pd Ratio"}),
        "mean_line": mean_ratio,
        "upper_band": mean_ratio + std_ratio,
        "lower_band": mean_ratio - std_ratio,
    }


def get_ratio_signal_text(metal: str, analysis: Dict) -> Tuple[str, str, str]:
    """
    Get signal text for a specific metal based on ratio analysis.

    Args:
        metal: "platinum" or "palladium"
        analysis: Result from analyze_ptpd_ratio()

    Returns:
        Tuple of (signal_text, color, emoji)
    """
    if "error" in analysis:
        return ("N/A", "#888888", "⚪")

    if metal.lower() == "platinum":
        signal = analysis["platinum_signal"]
        color = analysis["platinum_color"]
    else:
        signal = analysis["palladium_signal"]
        color = analysis["palladium_color"]

    emoji_map = {
        "expensive": "🔴",
        "cheap": "🟢",
        "fair": "🟡"
    }

    return (signal.upper(), color, emoji_map.get(signal, "⚪"))


if __name__ == "__main__":
    print("=== Pt/Pd Ratio Analysis ===\n")

    analysis = analyze_ptpd_ratio()

    if "error" in analysis:
        print(f"Error: {analysis['error']}")
    else:
        print(f"Current Pt/Pd Ratio: {analysis['current_ratio']}")
        print(f"5-Year Percentile: {analysis['percentile']}%")
        print(f"Z-Score: {analysis['z_score']}")
        print(f"5-Year Mean: {analysis['mean']}")
        print(f"5-Year Range: {analysis['min']} - {analysis['max']}")
        print()
        print(f"Platinum: ${analysis['platinum_price']} - {analysis['platinum_signal'].upper()}")
        print(f"Palladium: ${analysis['palladium_price']} - {analysis['palladium_signal'].upper()}")
        print()
        print(f"Interpretation: {analysis['interpretation']}")
        print(f"Trend: {analysis['trend_description']}")
