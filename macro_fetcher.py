"""
Macro data fetcher for precious metals analysis.

Fetches key macro drivers that influence gold and silver prices:
- US Dollar Index (DXY)
- 10Y Nominal Yield
- 10Y Real Yield (TIPS) - gold's #1 driver
- VIX (equity volatility / risk sentiment)
- MOVE Index (bond volatility)

Data sources:
- Yahoo Finance: DXY, yields, VIX, MOVE
- FRED API: Real yields (10Y TIPS yield)
"""
import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


def get_fred_api_key():
    """Get FRED API key from Streamlit secrets or environment."""
    # Try Streamlit secrets first (for cloud deployment)
    try:
        import streamlit as st
        key = st.secrets.get("api_keys", {}).get("FRED_API_KEY")
        if key:
            return key
    except Exception:
        pass

    # Fall back to environment variable (for local development)
    return os.getenv("FRED_API_KEY")


# FRED API for real yields
FRED_API_KEY = get_fred_api_key()
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Yahoo Finance tickers
MACRO_TICKERS = {
    "dxy": "DX-Y.NYB",           # US Dollar Index
    "us10y": "^TNX",             # 10-Year Treasury Yield
    "us2y": "^IRX",              # 2-Year (actually 13-week T-bill, proxy)
    "vix": "^VIX",               # CBOE Volatility Index
    "move": "^MOVE",             # ICE BofA MOVE Index (bond volatility)
}

# FRED series for real yields
FRED_SERIES = {
    "real_yield_10y": "DFII10",      # 10-Year Treasury Inflation-Indexed Security
    "real_yield_5y": "DFII5",        # 5-Year TIPS
    "breakeven_10y": "T10YIE",       # 10-Year Breakeven Inflation Rate
    "breakeven_5y": "T5YIE",         # 5-Year Breakeven Inflation Rate
}


def fetch_fred_series(series_id: str, limit: int = 30) -> Optional[pd.DataFrame]:
    """
    Fetch data from FRED API.

    Args:
        series_id: FRED series ID (e.g., 'DFII10' for 10Y real yield)
        limit: Number of observations to fetch

    Returns:
        DataFrame with date index and 'value' column, or None if failed
    """
    if not FRED_API_KEY:
        return None

    try:
        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        resp = requests.get(FRED_BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        observations = data.get("observations", [])
        if not observations:
            return None

        df = pd.DataFrame(observations)
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.set_index("date").sort_index()
        return df[["value"]]

    except Exception as e:
        print(f"FRED API error for {series_id}: {e}")
        return None


def fetch_yahoo_macro(ticker: str, period: str = "1mo") -> Dict[str, Any]:
    """
    Fetch macro data from Yahoo Finance.

    Returns:
        Dict with current value, change, pct_change, and history
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)

        if hist.empty:
            return {"error": f"No data for {ticker}"}

        current = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
        change = current - prev
        pct_change = (change / prev * 100) if prev != 0 else 0

        # 1-week and 1-month changes
        week_ago_idx = max(0, len(hist) - 5)
        month_ago_idx = 0

        week_change = current - float(hist["Close"].iloc[week_ago_idx])
        month_change = current - float(hist["Close"].iloc[month_ago_idx])

        return {
            "current": current,
            "prev_close": prev,
            "change": change,
            "pct_change": pct_change,
            "week_change": week_change,
            "month_change": month_change,
            "high_1m": float(hist["High"].max()),
            "low_1m": float(hist["Low"].min()),
            "history": hist,
        }

    except Exception as e:
        return {"error": str(e)}


def get_real_yield() -> Dict[str, Any]:
    """
    Get 10Y real yield (TIPS yield) - gold's #1 driver.

    Tries FRED first (most accurate), falls back to calculation.
    """
    # Try FRED API first
    if FRED_API_KEY:
        df = fetch_fred_series("DFII10", limit=30)
        if df is not None and not df.empty:
            current = float(df["value"].iloc[-1])
            prev = float(df["value"].iloc[-2]) if len(df) > 1 else current

            # Get 1-week ago value
            week_ago = df["value"].iloc[-5] if len(df) >= 5 else df["value"].iloc[0]

            return {
                "source": "FRED",
                "current": current,
                "change": current - prev,
                "week_change": current - float(week_ago),
                "series_id": "DFII10",
            }

    # Fallback: estimate from nominal yield minus breakeven
    # This is less accurate but better than nothing
    nominal = fetch_yahoo_macro("^TNX")
    if "error" not in nominal:
        # Try to get breakeven from FRED
        if FRED_API_KEY:
            bei = fetch_fred_series("T10YIE", limit=5)
            if bei is not None and not bei.empty:
                breakeven = float(bei["value"].iloc[-1])
                real_yield = nominal["current"] - breakeven
                return {
                    "source": "calculated",
                    "current": real_yield,
                    "nominal": nominal["current"],
                    "breakeven": breakeven,
                    "change": None,
                    "week_change": None,
                }

        # Very rough estimate: assume ~2.3% breakeven
        estimated_real = nominal["current"] - 2.3
        return {
            "source": "estimated",
            "current": estimated_real,
            "nominal": nominal["current"],
            "breakeven_est": 2.3,
            "change": None,
            "week_change": None,
            "note": "Add FRED_API_KEY to .env for accurate real yields",
        }

    return {"error": "Could not fetch real yield data"}


def get_macro_dashboard() -> Dict[str, Any]:
    """
    Fetch all macro indicators for the dashboard.

    Returns:
        Dict with all macro data organized by category
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "indicators": {},
    }

    # US Dollar Index
    dxy = fetch_yahoo_macro(MACRO_TICKERS["dxy"])
    if "error" not in dxy:
        result["indicators"]["dxy"] = {
            "name": "US Dollar Index (DXY)",
            "value": dxy["current"],
            "change": dxy["change"],
            "pct_change": dxy["pct_change"],
            "week_change": dxy["week_change"],
            "interpretation": "stronger" if dxy["change"] > 0 else "weaker",
            "gold_impact": "bearish" if dxy["change"] > 0 else "bullish",
        }
    else:
        result["indicators"]["dxy"] = {"error": dxy["error"]}

    # 10Y Nominal Yield
    us10y = fetch_yahoo_macro(MACRO_TICKERS["us10y"])
    if "error" not in us10y:
        result["indicators"]["us10y"] = {
            "name": "10Y Treasury Yield",
            "value": us10y["current"],
            "change": us10y["change"],
            "pct_change": us10y["pct_change"],
            "week_change": us10y["week_change"],
            "interpretation": "rising" if us10y["change"] > 0 else "falling",
        }
    else:
        result["indicators"]["us10y"] = {"error": us10y["error"]}

    # 10Y Real Yield (TIPS) - gold's #1 driver
    real_yield = get_real_yield()
    result["indicators"]["real_yield"] = {
        "name": "10Y Real Yield (TIPS)",
        "is_primary_driver": True,
        **real_yield,
    }
    if "current" in real_yield:
        # Real yield interpretation for gold
        if real_yield["current"] < 0:
            result["indicators"]["real_yield"]["interpretation"] = "negative (bullish for gold)"
            result["indicators"]["real_yield"]["gold_impact"] = "strongly bullish"
        elif real_yield["current"] < 1.0:
            result["indicators"]["real_yield"]["interpretation"] = "low positive"
            result["indicators"]["real_yield"]["gold_impact"] = "neutral to bullish"
        elif real_yield["current"] < 2.0:
            result["indicators"]["real_yield"]["interpretation"] = "moderate"
            result["indicators"]["real_yield"]["gold_impact"] = "neutral"
        else:
            result["indicators"]["real_yield"]["interpretation"] = "high (bearish for gold)"
            result["indicators"]["real_yield"]["gold_impact"] = "bearish"

    # VIX (equity volatility)
    vix = fetch_yahoo_macro(MACRO_TICKERS["vix"])
    if "error" not in vix:
        vix_level = vix["current"]
        if vix_level < 15:
            vix_regime = "low volatility (complacency)"
        elif vix_level < 20:
            vix_regime = "normal"
        elif vix_level < 30:
            vix_regime = "elevated (risk-off)"
        else:
            vix_regime = "high (fear)"

        result["indicators"]["vix"] = {
            "name": "VIX (Fear Index)",
            "value": vix["current"],
            "change": vix["change"],
            "pct_change": vix["pct_change"],
            "week_change": vix["week_change"],
            "regime": vix_regime,
            "gold_impact": "bullish" if vix_level > 25 else "neutral",
        }
    else:
        result["indicators"]["vix"] = {"error": vix["error"]}

    # MOVE Index (bond volatility)
    move = fetch_yahoo_macro(MACRO_TICKERS["move"])
    if "error" not in move:
        move_level = move["current"]
        if move_level < 80:
            move_regime = "low (calm bond market)"
        elif move_level < 100:
            move_regime = "normal"
        elif move_level < 120:
            move_regime = "elevated"
        else:
            move_regime = "high (bond stress)"

        result["indicators"]["move"] = {
            "name": "MOVE Index (Bond Vol)",
            "value": move["current"],
            "change": move["change"],
            "pct_change": move["pct_change"],
            "week_change": move["week_change"],
            "regime": move_regime,
            "gold_impact": "bullish" if move_level > 100 else "neutral",
        }
    else:
        result["indicators"]["move"] = {"error": move["error"]}

    # Overall macro assessment for gold
    bullish_count = sum(
        1 for ind in result["indicators"].values()
        if ind.get("gold_impact") in ["bullish", "strongly bullish"]
    )
    bearish_count = sum(
        1 for ind in result["indicators"].values()
        if ind.get("gold_impact") == "bearish"
    )

    if bullish_count >= 3:
        result["macro_bias"] = "bullish"
    elif bearish_count >= 3:
        result["macro_bias"] = "bearish"
    else:
        result["macro_bias"] = "neutral"

    result["bullish_factors"] = bullish_count
    result["bearish_factors"] = bearish_count

    return result


if __name__ == "__main__":
    print("=== Macro Dashboard ===\n")

    macro = get_macro_dashboard()

    for key, ind in macro["indicators"].items():
        if "error" in ind:
            print(f"{ind.get('name', key)}: ERROR - {ind['error']}")
            continue

        name = ind.get("name", key)
        value = ind.get("value")
        change = ind.get("change")
        impact = ind.get("gold_impact", "N/A")

        if value is not None:
            change_str = f"{change:+.2f}" if change else "N/A"
            print(f"{name:30}: {value:>8.2f}  (chg: {change_str})  Gold: {impact}")

        # Extra info
        if ind.get("regime"):
            print(f"  {'Regime':28}: {ind['regime']}")
        if ind.get("source"):
            print(f"  {'Source':28}: {ind['source']}")
        if ind.get("note"):
            print(f"  {'Note':28}: {ind['note']}")
        print()

    print(f"Overall Macro Bias for Gold: {macro['macro_bias'].upper()}")
    print(f"  Bullish factors: {macro['bullish_factors']}")
    print(f"  Bearish factors: {macro['bearish_factors']}")
