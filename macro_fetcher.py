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

# Copper-specific FRED series
COPPER_FRED_SERIES = {
    "china_pmi": "MPMICN",           # China Manufacturing PMI (NBS)
    "us_ism_pmi": "NAPMPI",          # ISM Manufacturing PMI
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
        Now includes 5d and 20d changes for tailwind analysis
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

        # 5-day change (for tailwind analysis)
        if len(hist) >= 5:
            val_5d_ago = float(hist["Close"].iloc[-5])
            change_5d = current - val_5d_ago
            pct_change_5d = ((current - val_5d_ago) / val_5d_ago * 100) if val_5d_ago != 0 else 0
        else:
            change_5d = 0.0
            pct_change_5d = 0.0

        # 20-day change (for tailwind analysis)
        if len(hist) >= 20:
            val_20d_ago = float(hist["Close"].iloc[-20])
            change_20d = current - val_20d_ago
            pct_change_20d = ((current - val_20d_ago) / val_20d_ago * 100) if val_20d_ago != 0 else 0
        else:
            change_20d = change_5d  # Use 5d if 20d not available
            pct_change_20d = pct_change_5d

        # 1-week and 1-month changes (legacy)
        week_ago_idx = max(0, len(hist) - 5)
        month_ago_idx = 0

        week_change = current - float(hist["Close"].iloc[week_ago_idx])
        month_change = current - float(hist["Close"].iloc[month_ago_idx])

        return {
            "current": current,
            "prev_close": prev,
            "change": change,
            "pct_change": pct_change,
            "change_5d": change_5d,
            "pct_change_5d": pct_change_5d,
            "change_20d": change_20d,
            "pct_change_20d": pct_change_20d,
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
    Now includes 5d and 20d changes for tailwind analysis.
    """
    # Try FRED API first
    if FRED_API_KEY:
        df = fetch_fred_series("DFII10", limit=30)
        if df is not None and not df.empty:
            current = float(df["value"].iloc[-1])
            prev = float(df["value"].iloc[-2]) if len(df) > 1 else current

            # Get 5-day ago value
            val_5d_ago = float(df["value"].iloc[-5]) if len(df) >= 5 else current
            change_5d = current - val_5d_ago

            # Get 20-day ago value
            val_20d_ago = float(df["value"].iloc[-20]) if len(df) >= 20 else val_5d_ago
            change_20d = current - val_20d_ago

            # Get 1-week ago value (legacy)
            week_ago = df["value"].iloc[-5] if len(df) >= 5 else df["value"].iloc[0]

            return {
                "source": "FRED",
                "current": current,
                "change": current - prev,
                "change_5d": change_5d,
                "change_20d": change_20d,
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
            "change_5d": dxy.get("change_5d", 0),
            "pct_change_5d": dxy.get("pct_change_5d", 0),
            "change_20d": dxy.get("change_20d", 0),
            "pct_change_20d": dxy.get("pct_change_20d", 0),
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


def analyze_macro_tailwind(macro_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze macro tailwind status for gold/silver.

    Rules (for Gold/Silver):
    - Supportive: Real yields trending down AND USD flat/down
    - Hostile: Real yields trending up AND USD up
    - Neutral: Mixed signals or both flat

    Args:
        macro_data: Output from get_macro_dashboard()

    Returns:
        Dict with tailwind status and component analysis
    """
    indicators = macro_data.get("indicators", {})

    # Get DXY data
    dxy_data = indicators.get("dxy", {})
    dxy_change_5d = dxy_data.get("change_5d", 0)
    dxy_change_20d = dxy_data.get("change_20d", 0)

    # Get real yield data
    real_yield_data = indicators.get("real_yield", {})
    ry_change_5d = real_yield_data.get("change_5d", 0)
    ry_change_20d = real_yield_data.get("change_20d", 0)

    # Determine USD trend (use 5d for short-term, 20d for confirmation)
    # DXY rising > 0.5% = strengthening, falling < -0.5% = weakening
    if dxy_change_5d is not None and dxy_change_20d is not None:
        if dxy_change_5d > 0.5 or dxy_change_20d > 1.0:
            usd_trend = "rising"
        elif dxy_change_5d < -0.5 or dxy_change_20d < -1.0:
            usd_trend = "falling"
        else:
            usd_trend = "flat"
    else:
        usd_trend = "unknown"

    # Determine real yield trend
    # Rising yields (>0.05) = bearish for gold, falling (<-0.05) = bullish
    if ry_change_5d is not None and ry_change_20d is not None:
        if ry_change_5d > 0.05 or ry_change_20d > 0.1:
            ry_trend = "rising"
        elif ry_change_5d < -0.05 or ry_change_20d < -0.1:
            ry_trend = "falling"
        else:
            ry_trend = "flat"
    else:
        ry_trend = "unknown"

    # Classify tailwind status
    if ry_trend == "falling" and usd_trend in ["falling", "flat"]:
        status = "supportive"
        description = "Real yields falling with USD flat/weak - bullish macro backdrop"
    elif ry_trend == "rising" and usd_trend == "rising":
        status = "hostile"
        description = "Real yields rising with USD strengthening - bearish macro backdrop"
    elif ry_trend == "rising" and usd_trend in ["falling", "flat"]:
        status = "mixed"
        description = "Real yields rising but USD weak - conflicting signals"
    elif ry_trend == "falling" and usd_trend == "rising":
        status = "mixed"
        description = "Real yields falling but USD strong - conflicting signals"
    else:
        status = "neutral"
        description = "Both indicators flat - no clear macro direction"

    return {
        "status": status,
        "description": description,
        "usd_trend": usd_trend,
        "real_yield_trend": ry_trend,
        "dxy_change_5d": dxy_change_5d,
        "dxy_change_20d": dxy_change_20d,
        "ry_change_5d": ry_change_5d,
        "ry_change_20d": ry_change_20d,
    }


def get_copper_macro() -> Dict[str, Any]:
    """
    Fetch copper-specific macro indicators.

    Key drivers for copper (different from gold):
    - China Manufacturing PMI (China = 50% of global copper demand)
    - US ISM Manufacturing PMI
    - USD/CNY exchange rate

    Returns:
        Dict with copper-focused macro data
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "indicators": {},
    }

    # China Manufacturing PMI - THE key indicator for copper
    if FRED_API_KEY:
        china_pmi_df = fetch_fred_series(COPPER_FRED_SERIES["china_pmi"], limit=12)
        if china_pmi_df is not None and not china_pmi_df.empty:
            current = float(china_pmi_df["value"].iloc[-1])
            prev = float(china_pmi_df["value"].iloc[-2]) if len(china_pmi_df) > 1 else current

            # PMI interpretation
            if current > 52:
                regime = "strong expansion"
                copper_impact = "strongly bullish"
            elif current > 50:
                regime = "expansion"
                copper_impact = "bullish"
            elif current > 48:
                regime = "mild contraction"
                copper_impact = "bearish"
            else:
                regime = "contraction"
                copper_impact = "strongly bearish"

            result["indicators"]["china_pmi"] = {
                "name": "China Manufacturing PMI",
                "value": current,
                "change": current - prev,
                "regime": regime,
                "copper_impact": copper_impact,
                "source": "FRED (MPMICN)",
                "note": "China consumes ~50% of global copper",
            }
        else:
            result["indicators"]["china_pmi"] = {
                "name": "China Manufacturing PMI",
                "error": "Data not available",
                "note": "Ensure FRED_API_KEY is set",
            }
    else:
        result["indicators"]["china_pmi"] = {
            "name": "China Manufacturing PMI",
            "error": "No FRED API key",
            "note": "Add FRED_API_KEY to secrets for China PMI data",
        }

    # US ISM Manufacturing PMI
    if FRED_API_KEY:
        us_pmi_df = fetch_fred_series(COPPER_FRED_SERIES["us_ism_pmi"], limit=12)
        if us_pmi_df is not None and not us_pmi_df.empty:
            current = float(us_pmi_df["value"].iloc[-1])
            prev = float(us_pmi_df["value"].iloc[-2]) if len(us_pmi_df) > 1 else current

            if current > 52:
                regime = "strong expansion"
                copper_impact = "bullish"
            elif current > 50:
                regime = "expansion"
                copper_impact = "mildly bullish"
            elif current > 48:
                regime = "mild contraction"
                copper_impact = "mildly bearish"
            else:
                regime = "contraction"
                copper_impact = "bearish"

            result["indicators"]["us_ism_pmi"] = {
                "name": "US ISM Manufacturing PMI",
                "value": current,
                "change": current - prev,
                "regime": regime,
                "copper_impact": copper_impact,
                "source": "FRED (NAPMPI)",
            }
        else:
            result["indicators"]["us_ism_pmi"] = {
                "name": "US ISM Manufacturing PMI",
                "error": "Data not available",
            }
    else:
        result["indicators"]["us_ism_pmi"] = {
            "name": "US ISM Manufacturing PMI",
            "error": "No FRED API key",
        }

    # USD/CNY exchange rate
    try:
        cny = yf.Ticker("CNY=X")
        hist = cny.history(period="1mo")
        if not hist.empty:
            current = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
            week_ago = float(hist["Close"].iloc[-5]) if len(hist) >= 5 else prev

            change = current - prev
            week_change = current - week_ago

            # Higher USD/CNY = stronger dollar vs yuan = bearish for commodities
            if week_change > 0.05:
                trend = "strengthening (USD)"
                copper_impact = "bearish"
            elif week_change < -0.05:
                trend = "weakening (USD)"
                copper_impact = "bullish"
            else:
                trend = "stable"
                copper_impact = "neutral"

            result["indicators"]["usd_cny"] = {
                "name": "USD/CNY",
                "value": current,
                "change": change,
                "week_change": week_change,
                "trend": trend,
                "copper_impact": copper_impact,
                "note": "Weaker USD (lower) = bullish for copper",
            }
        else:
            result["indicators"]["usd_cny"] = {"name": "USD/CNY", "error": "No data"}
    except Exception as e:
        result["indicators"]["usd_cny"] = {"name": "USD/CNY", "error": str(e)}

    # Overall copper macro assessment
    bullish_count = sum(
        1 for ind in result["indicators"].values()
        if ind.get("copper_impact") in ["bullish", "strongly bullish", "mildly bullish"]
    )
    bearish_count = sum(
        1 for ind in result["indicators"].values()
        if ind.get("copper_impact") in ["bearish", "strongly bearish", "mildly bearish"]
    )

    if bullish_count >= 2:
        result["macro_bias"] = "bullish"
    elif bearish_count >= 2:
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
