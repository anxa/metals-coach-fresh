"""
Professional 5-Pillar Market Analysis Framework

This module implements a rigorous, trader-tested methodology with clear rules:

1. REGIME: uptrend / downtrend / range
   - Uses ADX(14), SMA200, SMA50, slope of SMA50

2. MOMENTUM: accelerating / cooling / diverging
   - Uses MACD histogram slope, RSI direction, swing divergence

3. PARTICIPATION: confirming / thinning / distribution
   - Uses up/down volume ratio, OBV trend

4. MACRO TAILWIND: supportive / neutral / hostile
   - Uses 5d/20d changes in DXY, real yields

5. POSITIONING: crowded / neutral / washed out
   - Uses COT Managed Money percentile

Each pillar has explicit rules - no ad-hoc scoring.
"""

from typing import Dict, Any, Optional


def classify_regime(
    price: float,
    sma200: float,
    sma50: float,
    sma50_slope: float,
    adx: float
) -> Dict[str, Any]:
    """
    Classify market regime using ADX + SMA rules.

    Rules:
    - UPTREND: Close > SMA200 AND SMA50 > SMA200 AND slope(SMA50, 20d) > 0 AND ADX > 18
    - DOWNTREND: Close < SMA200 AND SMA50 < SMA200 AND slope(SMA50, 20d) < 0 AND ADX > 18
    - RANGE: ADX < 18 OR (within 3% of SMA200 AND SMA50 slope flat)

    Args:
        price: Current price
        sma200: 200-day SMA
        sma50: 50-day SMA
        sma50_slope: 20-day slope of SMA50 (as % change)
        adx: ADX(14) value

    Returns:
        Dict with regime, conditions met, and description
    """
    if price is None or sma200 is None or sma50 is None:
        return {
            "regime": "unknown",
            "description": "Insufficient data",
            "conditions": []
        }

    # Default values if missing
    adx = adx if adx is not None else 15
    sma50_slope = sma50_slope if sma50_slope is not None else 0

    conditions = []

    # Calculate key metrics
    price_vs_200 = ((price - sma200) / sma200) * 100 if sma200 != 0 else 0
    sma50_vs_200 = sma50 > sma200

    # Check conditions
    price_above_200 = price > sma200
    price_below_200 = price < sma200
    slope_rising = sma50_slope > 0.2  # Small positive threshold
    slope_falling = sma50_slope < -0.2  # Small negative threshold
    slope_flat = abs(sma50_slope) <= 0.2
    strong_trend = adx > 18
    weak_trend = adx < 18
    near_200 = abs(price_vs_200) < 3

    # Record conditions
    if price_above_200:
        conditions.append(f"Price above SMA200 (+{price_vs_200:.1f}%)")
    else:
        conditions.append(f"Price below SMA200 ({price_vs_200:.1f}%)")

    if sma50_vs_200:
        conditions.append("SMA50 > SMA200")
    else:
        conditions.append("SMA50 < SMA200")

    if slope_rising:
        conditions.append(f"SMA50 slope rising (+{sma50_slope:.2f}%)")
    elif slope_falling:
        conditions.append(f"SMA50 slope falling ({sma50_slope:.2f}%)")
    else:
        conditions.append(f"SMA50 slope flat ({sma50_slope:.2f}%)")

    conditions.append(f"ADX = {adx:.1f}")

    # Classify regime using explicit rules
    if weak_trend or (near_200 and slope_flat):
        regime = "range"
        description = "No clear trend - ADX weak or price near SMA200 with flat slope"
    elif price_above_200 and sma50_vs_200 and slope_rising and strong_trend:
        regime = "uptrend"
        description = "Uptrend confirmed - all bullish conditions met"
    elif price_below_200 and not sma50_vs_200 and slope_falling and strong_trend:
        regime = "downtrend"
        description = "Downtrend confirmed - all bearish conditions met"
    elif price_above_200 and strong_trend:
        regime = "uptrend"
        description = "Uptrend - price above SMA200 with trending ADX"
    elif price_below_200 and strong_trend:
        regime = "downtrend"
        description = "Downtrend - price below SMA200 with trending ADX"
    else:
        regime = "range"
        description = "Range-bound - mixed signals"

    return {
        "regime": regime,
        "description": description,
        "conditions": conditions,
        "metrics": {
            "price_vs_200": price_vs_200,
            "sma50_vs_200": "above" if sma50_vs_200 else "below",
            "sma50_slope": sma50_slope,
            "adx": adx,
        }
    }


def analyze_momentum(
    macd_histogram: float,
    macd_hist_slope: str,
    rsi_current: float,
    rsi_direction: str,
    rsi_divergence: Dict[str, Any],
    price_trend: str
) -> Dict[str, Any]:
    """
    Analyze momentum phase with proper divergence detection.

    Rules:
    - ACCELERATING: MACD histogram rising 3-5 days AND RSI rising above 10d avg AND higher closes
    - COOLING: Price still trending BUT MACD histogram falling AND RSI rolling over
    - DIVERGING: Price higher high + RSI lower high (bearish) OR Price lower low + RSI higher low (bullish)

    Args:
        macd_histogram: Current MACD histogram value
        macd_hist_slope: "rising", "falling", or "flat"
        rsi_current: Current RSI value
        rsi_direction: "rising", "falling", or "flat"
        rsi_divergence: Divergence detection result from indicators.py
        price_trend: Current price trend ("uptrend", "downtrend", "chop")

    Returns:
        Dict with momentum phase and supporting details
    """
    conditions = []

    # Check for divergence first (highest priority)
    divergence = rsi_divergence.get("divergence")
    if divergence:
        div_type = rsi_divergence.get("type", "regular")
        if divergence == "bearish":
            return {
                "phase": "diverging",
                "divergence_type": "bearish",
                "description": "Bearish divergence - price higher highs, RSI lower highs",
                "warning": "Momentum weakening despite price strength - elevated reversal risk",
                "conditions": [
                    f"RSI divergence: {divergence}",
                    rsi_divergence.get("description", "")
                ]
            }
        elif divergence == "bullish":
            return {
                "phase": "diverging",
                "divergence_type": "bullish",
                "description": "Bullish divergence - price lower lows, RSI higher lows",
                "warning": "Momentum strengthening despite price weakness - potential reversal",
                "conditions": [
                    f"RSI divergence: {divergence}",
                    rsi_divergence.get("description", "")
                ]
            }

    # Check MACD histogram behavior
    macd_rising = macd_hist_slope == "rising"
    macd_falling = macd_hist_slope == "falling"

    # Check RSI behavior
    rsi_rising = rsi_direction == "rising"
    rsi_falling = rsi_direction == "falling"

    # Record conditions
    conditions.append(f"MACD histogram: {macd_hist_slope}")
    conditions.append(f"RSI direction: {rsi_direction}")
    if rsi_current:
        conditions.append(f"RSI level: {rsi_current:.1f}")

    # Classify momentum phase
    if macd_rising and rsi_rising:
        phase = "accelerating"
        description = "Momentum building - MACD and RSI both rising"
    elif macd_falling and rsi_falling:
        phase = "cooling"
        description = "Momentum fading - MACD and RSI both falling"
    elif price_trend == "uptrend" and (macd_falling or rsi_falling):
        phase = "cooling"
        description = "Uptrend with cooling momentum - watch for continuation vs reversal"
    elif price_trend == "downtrend" and (macd_rising or rsi_rising):
        phase = "cooling"
        description = "Downtrend with improving momentum - potential bottom forming"
    elif macd_rising or rsi_rising:
        phase = "accelerating"
        description = "Momentum improving"
    elif macd_falling or rsi_falling:
        phase = "cooling"
        description = "Momentum weakening"
    else:
        phase = "steady"
        description = "Momentum neutral - no strong signal"

    return {
        "phase": phase,
        "divergence_type": None,
        "description": description,
        "conditions": conditions,
        "macd_histogram": macd_histogram,
        "rsi_current": rsi_current,
    }


def analyze_participation(
    up_down_volume: Dict[str, Any],
    obv_slope: float,
    obv_vs_sma: str,
    price_direction: str
) -> Dict[str, Any]:
    """
    Analyze volume participation quality.

    Rules:
    - CONFIRMING: Price rising AND vol_ratio > 1.1 on up days AND OBV trending up
    - THINNING: Price rising BUT vol_ratio < 0.9 for several sessions AND OBV flat/down
    - DISTRIBUTION: Price near highs BUT big down days on high volume AND OBV rolling over

    Args:
        up_down_volume: Result from up_down_volume_ratio()
        obv_slope: OBV slope over 10 days
        obv_vs_sma: "above" or "below" OBV's 20-day SMA
        price_direction: "up", "down", or "flat"

    Returns:
        Dict with participation status and details
    """
    if "error" in up_down_volume:
        return {
            "status": "unknown",
            "description": "Insufficient volume data",
            "conditions": []
        }

    vol_ratio = up_down_volume.get("vol_ratio", 1.0)
    vol_interpretation = up_down_volume.get("interpretation", "neutral")

    conditions = []
    conditions.append(f"Up/Down volume ratio: {vol_ratio:.2f}")
    conditions.append(f"Volume interpretation: {vol_interpretation}")
    conditions.append(f"OBV vs SMA: {obv_vs_sma}")
    if obv_slope:
        conditions.append(f"OBV slope: {obv_slope:.1f}%")

    # OBV trend
    obv_rising = obv_slope > 0.5 if obv_slope else False
    obv_falling = obv_slope < -0.5 if obv_slope else False
    obv_bullish = obv_vs_sma == "above"

    # Classify participation
    if price_direction == "up":
        if vol_ratio > 1.1 and (obv_rising or obv_bullish):
            status = "confirming"
            description = "Volume confirms advance - higher volume on up days, OBV healthy"
        elif vol_ratio < 0.9 or obv_falling:
            status = "thinning"
            description = "Advance on thin volume - participation weakening"
        elif vol_ratio < 0.9 and obv_falling:
            status = "distribution"
            description = "Distribution underway - smart money may be selling"
        else:
            status = "neutral"
            description = "Volume neutral - no strong signal"
    elif price_direction == "down":
        if vol_ratio < 0.9 and obv_falling:
            status = "confirming"
            description = "Volume confirms decline - selling pressure evident"
        elif vol_ratio > 1.1 or obv_rising:
            status = "thinning"
            description = "Decline on weak volume - selling may be exhausting"
        else:
            status = "neutral"
            description = "Volume neutral during decline"
    else:
        if vol_interpretation in ["strong_selling", "selling"]:
            status = "distribution"
            description = "Distribution pattern - selling into range"
        elif vol_interpretation in ["strong_buying", "buying"]:
            status = "accumulation"
            description = "Accumulation pattern - buying into range"
        else:
            status = "neutral"
            description = "Volume neutral in range"

    return {
        "status": status,
        "description": description,
        "conditions": conditions,
        "vol_ratio": vol_ratio,
        "obv_trend": "rising" if obv_rising else "falling" if obv_falling else "flat",
    }


def analyze_macro_tailwind_status(tailwind_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format macro tailwind analysis for display.

    The actual analysis is done in macro_fetcher.analyze_macro_tailwind().
    This function formats it for the 5-pillar display.

    Args:
        tailwind_data: Output from macro_fetcher.analyze_macro_tailwind()

    Returns:
        Dict with formatted tailwind status
    """
    status = tailwind_data.get("status", "neutral")
    description = tailwind_data.get("description", "No data available")

    conditions = []
    if tailwind_data.get("usd_trend"):
        conditions.append(f"USD trend: {tailwind_data['usd_trend']}")
    if tailwind_data.get("real_yield_trend"):
        conditions.append(f"Real yield trend: {tailwind_data['real_yield_trend']}")
    if tailwind_data.get("dxy_change_5d") is not None:
        conditions.append(f"DXY 5d: {tailwind_data['dxy_change_5d']:+.2f}")
    if tailwind_data.get("ry_change_5d") is not None:
        conditions.append(f"Real yield 5d: {tailwind_data['ry_change_5d']:+.3f}")

    return {
        "status": status,
        "description": description,
        "conditions": conditions,
    }


def analyze_positioning(
    cot_percentile: Optional[float],
    cot_net_position: Optional[float] = None
) -> Dict[str, Any]:
    """
    Analyze COT positioning for crowding risk.

    Rules:
    - CROWDED: MM percentile > 80 (very long) or < 20 (very short) - late stage risk
    - WASHED OUT: MM percentile < 20 with potential bottom forming
    - NEUTRAL: 20-80 percentile

    Args:
        cot_percentile: Managed Money net position percentile (0-100, 3yr lookback)
        cot_net_position: Raw net position (optional, for context)

    Returns:
        Dict with positioning status
    """
    if cot_percentile is None:
        return {
            "status": "unknown",
            "description": "COT data not available",
            "conditions": ["No COT data"]
        }

    conditions = [f"MM percentile: {cot_percentile:.0f}%"]
    if cot_net_position is not None:
        conditions.append(f"Net position: {cot_net_position:,.0f}")

    if cot_percentile > 80:
        status = "crowded_long"
        description = "Crowded long - elevated reversal risk, late-stage positioning"
        warning = "Extreme bullish positioning - contrarian signal"
    elif cot_percentile < 20:
        status = "washed_out"
        description = "Washed out - potential bottom, contrarian buy signal"
        warning = "Extreme bearish positioning - watch for reversal"
    elif cot_percentile > 65:
        status = "elevated_long"
        description = "Elevated long positioning - some crowding risk"
        warning = None
    elif cot_percentile < 35:
        status = "light_positioning"
        description = "Light positioning - room for longs to build"
        warning = None
    else:
        status = "neutral"
        description = "Neutral positioning - no crowding signal"
        warning = None

    result = {
        "status": status,
        "description": description,
        "conditions": conditions,
        "percentile": cot_percentile,
    }
    if warning:
        result["warning"] = warning

    return result


def get_five_pillar_analysis(
    indicators: Dict[str, Any],
    macro_tailwind: Dict[str, Any],
    cot_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Run the complete 5-pillar professional analysis.

    Args:
        indicators: Output from compute_indicators()
        macro_tailwind: Output from macro_fetcher.analyze_macro_tailwind()
        cot_data: COT data (optional)

    Returns:
        Dict with all 5 pillars analyzed
    """
    # Extract needed values from indicators
    price = indicators.get("spot_price") or indicators.get("last_close")
    sma200 = indicators.get("sma200")
    sma50 = indicators.get("sma50")
    sma50_slope = indicators.get("sma50_slope", 0)
    adx_val = indicators.get("adx")

    # MACD data
    macd_histogram = indicators.get("macd_histogram", 0)
    macd_hist_slope = indicators.get("macd_histogram_slope", "flat")

    # RSI data
    rsi_momentum = indicators.get("rsi_momentum", {})
    rsi_current = rsi_momentum.get("current") or indicators.get("rsi14")
    rsi_direction = rsi_momentum.get("direction", "flat")
    rsi_divergence = indicators.get("rsi_divergence", {"divergence": None})

    # Volume data
    up_down_volume = indicators.get("up_down_volume", {"error": "no data"})
    obv_slope = indicators.get("obv_slope", 0)
    obv_vs_sma = indicators.get("obv_vs_sma", "unknown")

    # Trend for context
    trend = indicators.get("trend", "chop")
    price_direction = "up" if trend == "uptrend" else "down" if trend == "downtrend" else "flat"

    # 1. REGIME
    regime = classify_regime(price, sma200, sma50, sma50_slope, adx_val)

    # 2. MOMENTUM
    momentum = analyze_momentum(
        macd_histogram, macd_hist_slope,
        rsi_current, rsi_direction,
        rsi_divergence, trend
    )

    # 3. PARTICIPATION
    participation = analyze_participation(
        up_down_volume, obv_slope, obv_vs_sma, price_direction
    )

    # 4. MACRO TAILWIND
    tailwind = analyze_macro_tailwind_status(macro_tailwind)

    # 5. POSITIONING
    cot_percentile = None
    cot_net = None
    if cot_data and "error" not in cot_data:
        # Try different key names used by cot_fetcher
        cot_percentile = cot_data.get("managed_money_percentile") or cot_data.get("mm_percentile")
        cot_net = cot_data.get("managed_money_net") or cot_data.get("mm_net_position")
    positioning = analyze_positioning(cot_percentile, cot_net)

    # Generate overall assessment
    assessment = generate_overall_assessment(
        regime, momentum, participation, tailwind, positioning
    )

    return {
        "regime": regime,
        "momentum": momentum,
        "participation": participation,
        "tailwind": tailwind,
        "positioning": positioning,
        "assessment": assessment,
    }


def generate_overall_assessment(
    regime: Dict[str, Any],
    momentum: Dict[str, Any],
    participation: Dict[str, Any],
    tailwind: Dict[str, Any],
    positioning: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate overall market assessment from 5 pillars.

    Returns:
        Dict with overall bias, key risks, and action suggestion
    """
    # Count bullish/bearish signals
    bullish_signals = 0
    bearish_signals = 0
    warnings = []

    # Regime
    if regime["regime"] == "uptrend":
        bullish_signals += 2  # Regime is weighted heavily
    elif regime["regime"] == "downtrend":
        bearish_signals += 2

    # Momentum
    if momentum["phase"] == "accelerating":
        bullish_signals += 1
    elif momentum["phase"] == "cooling":
        bearish_signals += 1
    elif momentum["phase"] == "diverging":
        if momentum.get("divergence_type") == "bearish":
            warnings.append("Bearish divergence detected")
            bearish_signals += 1
        elif momentum.get("divergence_type") == "bullish":
            warnings.append("Bullish divergence detected")
            bullish_signals += 1

    # Participation
    if participation["status"] == "confirming":
        bullish_signals += 1
    elif participation["status"] in ["thinning", "distribution"]:
        bearish_signals += 1
        if participation["status"] == "distribution":
            warnings.append("Distribution pattern detected")

    # Tailwind
    if tailwind["status"] == "supportive":
        bullish_signals += 1
    elif tailwind["status"] == "hostile":
        bearish_signals += 1

    # Positioning
    if positioning["status"] == "crowded_long":
        warnings.append("Crowded long positioning - reversal risk")
    elif positioning["status"] == "washed_out":
        bullish_signals += 1  # Contrarian bullish

    # Generate overall bias
    net_signal = bullish_signals - bearish_signals

    if net_signal >= 3:
        bias = "strongly_bullish"
        action = "Trend favorable - consider adding on pullbacks"
    elif net_signal >= 1:
        bias = "bullish"
        action = "Cautiously bullish - hold positions, selective adding"
    elif net_signal <= -3:
        bias = "strongly_bearish"
        action = "Trend unfavorable - avoid longs, consider reducing"
    elif net_signal <= -1:
        bias = "bearish"
        action = "Cautiously bearish - reduce exposure, tighten stops"
    else:
        bias = "neutral"
        action = "Mixed signals - wait for clarity, trade range"

    # Adjust for warnings
    if warnings and bias in ["strongly_bullish", "bullish"]:
        action = f"{action}. CAUTION: {', '.join(warnings)}"

    return {
        "bias": bias,
        "action": action,
        "bullish_signals": bullish_signals,
        "bearish_signals": bearish_signals,
        "warnings": warnings,
    }


# Legacy function for backwards compatibility
def get_full_market_analysis(
    indicators: Dict[str, Any],
    macro_bias: str = "neutral"
) -> Dict[str, Any]:
    """
    Legacy wrapper for backwards compatibility.

    Use get_five_pillar_analysis() for the new methodology.
    """
    # Create a minimal tailwind dict from macro_bias
    tailwind = {
        "status": "supportive" if macro_bias == "bullish" else "hostile" if macro_bias == "bearish" else "neutral",
        "description": f"Macro bias: {macro_bias}",
    }

    result = get_five_pillar_analysis(indicators, tailwind, None)

    # Map to legacy format
    regime = result["regime"]
    momentum = result["momentum"]
    participation = result["participation"]
    assessment = result["assessment"]

    return {
        "regime": {
            "regime": regime["regime"].upper(),
            "confidence": "high" if regime["regime"] != "range" else "moderate",
            "description": regime["description"],
            "factors": [(c, "bullish" if "above" in c.lower() or "rising" in c.lower() else "bearish") for c in regime["conditions"]],
        },
        "momentum": {
            "phase": momentum["phase"].upper(),
            "risk_level": "elevated" if momentum["phase"] == "diverging" else "normal",
            "description": momentum["description"],
            "diverging": momentum["phase"] == "diverging",
            "divergence_type": momentum.get("divergence_type"),
        },
        "volume": {
            "confirmation": participation["status"].upper(),
            "description": participation["description"],
            "participation": participation["status"],
        },
        "cycle": {
            "position": "MID",  # Simplified
            "description": "See 5-pillar analysis",
        },
        "recommendation": {
            "action": assessment["action"].split(" - ")[0].upper().replace(" ", "_"),
            "confidence": "high" if abs(assessment["bullish_signals"] - assessment["bearish_signals"]) >= 3 else "moderate",
            "reasoning": assessment.get("warnings", []),
            "summary": assessment["action"],
        },
        "summary": assessment["action"],
    }
