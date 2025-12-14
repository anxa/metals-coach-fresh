"""
Professional Market Regime Analysis

This module implements the professional trader's framework:
- Regime classification (bullish/bearish/range)
- Momentum phase detection (accelerating/decelerating/diverging)
- Volume confirmation
- Cycle position (early/mid/late stage)
- Actionable recommendations (add/hold/reduce/wait)

Key principle: Trade transitions, not snapshots.
"""

from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np


def classify_regime(
    price: float,
    sma200: float,
    sma50: float,
    trend: str,
    rsi: float,
    macro_bias: str = "neutral"
) -> Dict[str, Any]:
    """
    Classify the market regime.

    Regimes:
    - BULLISH: Price > 200 SMA, trend up, RSI in bullish regime (40-80)
    - BEARISH: Price < 200 SMA, trend down, RSI in bearish regime (20-60)
    - RANGE/CONSOLIDATION: Mixed signals, no clear trend

    Returns regime classification with confidence.
    """
    if price is None or sma200 is None:
        return {"regime": "unknown", "confidence": "low", "description": "Insufficient data"}

    # Score components
    score = 0
    factors = []

    # Price vs 200 SMA (most important)
    pct_from_200 = ((price - sma200) / sma200) * 100
    if pct_from_200 > 5:
        score += 2
        factors.append(("Price well above 200 SMA", "bullish"))
    elif pct_from_200 > 0:
        score += 1
        factors.append(("Price above 200 SMA", "bullish"))
    elif pct_from_200 < -5:
        score -= 2
        factors.append(("Price well below 200 SMA", "bearish"))
    elif pct_from_200 < 0:
        score -= 1
        factors.append(("Price below 200 SMA", "bearish"))

    # Trend classification
    if trend == "uptrend":
        score += 2
        factors.append(("MA alignment bullish", "bullish"))
    elif trend == "downtrend":
        score -= 2
        factors.append(("MA alignment bearish", "bearish"))
    else:  # chop
        factors.append(("MA alignment mixed", "neutral"))

    # RSI regime (not level!)
    # Bullish regime: RSI tends to stay 40-80
    # Bearish regime: RSI tends to stay 20-60
    if rsi is not None:
        if rsi > 40 and rsi < 80:
            # Could be bullish regime
            if rsi > 50:
                score += 1
                factors.append(("RSI in bullish regime zone", "bullish"))
        elif rsi < 60 and rsi > 20:
            # Could be bearish regime
            if rsi < 50:
                score -= 1
                factors.append(("RSI in bearish regime zone", "bearish"))

    # Macro backdrop
    if macro_bias == "bullish":
        score += 1
        factors.append(("Macro supportive", "bullish"))
    elif macro_bias == "bearish":
        score -= 1
        factors.append(("Macro hostile", "bearish"))

    # Classify regime
    if score >= 3:
        regime = "BULLISH"
        confidence = "high" if score >= 4 else "moderate"
        description = "Uptrend intact - shorts are low probability"
    elif score <= -3:
        regime = "BEARISH"
        confidence = "high" if score <= -4 else "moderate"
        description = "Downtrend intact - longs are low probability"
    elif abs(score) <= 1:
        regime = "RANGE"
        confidence = "moderate"
        description = "No clear trend - wait for breakout or trade range"
    else:
        regime = "TRANSITIONAL"
        confidence = "low"
        description = "Regime changing - reduced position sizing advised"

    return {
        "regime": regime,
        "confidence": confidence,
        "description": description,
        "score": score,
        "pct_from_200sma": pct_from_200,
        "factors": factors,
    }


def analyze_momentum_phase(
    rsi_current: float,
    rsi_change: float,
    rsi_direction: str,
    macd_histogram: float,
    macd_hist_change: float,
    macd_above_zero: bool,
    price_trend: str
) -> Dict[str, Any]:
    """
    Determine momentum phase.

    Phases:
    - ACCELERATING: Momentum building (RSI rising, histogram expanding)
    - STEADY: Momentum stable (normal trend behavior)
    - DECELERATING: Momentum cooling (RSI falling, histogram shrinking)
    - DIVERGING: Momentum conflicting with price (warning signal)

    Key insight: Deceleration != Reversal. Deceleration = Risk Rising.
    """
    if rsi_current is None:
        return {"phase": "unknown", "risk_level": "unknown"}

    # Determine RSI behavior
    rsi_accelerating = rsi_direction == "rising" and rsi_change > 5
    rsi_decelerating = rsi_direction == "falling" and rsi_change < -5
    rsi_stable = abs(rsi_change) <= 5

    # Determine MACD behavior
    macd_accelerating = macd_hist_change > 0 and macd_histogram > 0
    macd_decelerating = macd_hist_change < 0 and macd_histogram > 0  # Still positive but shrinking
    macd_bearish_accelerating = macd_hist_change < 0 and macd_histogram < 0

    # Check for divergence (price up but momentum down, or vice versa)
    diverging = False
    divergence_type = None

    if price_trend == "uptrend":
        if rsi_direction == "falling" and rsi_change < -8:
            diverging = True
            divergence_type = "bearish"
        if macd_hist_change < 0 and macd_histogram > 0:
            # MACD falling but above zero - common in uptrends
            pass  # This is normal cooling, not divergence
    elif price_trend == "downtrend":
        if rsi_direction == "rising" and rsi_change > 8:
            diverging = True
            divergence_type = "bullish"

    # Classify phase
    if diverging:
        phase = "DIVERGING"
        risk_level = "elevated"
        description = f"{divergence_type.title()} divergence - trend continuation with rising risk"
        action_bias = "reduce" if divergence_type == "bearish" else "watch for reversal"
    elif rsi_accelerating and (macd_accelerating or macd_above_zero):
        phase = "ACCELERATING"
        risk_level = "normal"
        description = "Momentum building - trend strengthening"
        action_bias = "hold or add on pullbacks"
    elif rsi_decelerating or macd_decelerating:
        phase = "DECELERATING"
        risk_level = "rising"
        description = "Momentum cooling - normal but watch closely"
        action_bias = "hold, stop chasing"
    else:
        phase = "STEADY"
        risk_level = "normal"
        description = "Momentum stable - trend intact"
        action_bias = "hold"

    return {
        "phase": phase,
        "risk_level": risk_level,
        "description": description,
        "action_bias": action_bias,
        "rsi_behavior": "accelerating" if rsi_accelerating else "decelerating" if rsi_decelerating else "stable",
        "macd_behavior": "accelerating" if macd_accelerating else "decelerating" if macd_decelerating else "stable",
        "diverging": diverging,
        "divergence_type": divergence_type,
    }


def analyze_volume_confirmation(
    volume_ratio: float,
    volume_signal: str,
    obv_direction: str,
    obv_divergence: str,
    price_direction: str  # "up", "down", "flat"
) -> Dict[str, Any]:
    """
    Volume is the tiebreaker when indicators conflict.

    Key questions:
    - Is volume expanding or contracting?
    - Is it expanding on advances or declines?
    - Is money committing or backing away?
    """
    if volume_ratio is None:
        return {"confirmation": "unknown", "description": "No volume data"}

    # Volume expansion/contraction
    volume_expanding = volume_ratio > 1.2
    volume_contracting = volume_ratio < 0.8
    volume_normal = 0.8 <= volume_ratio <= 1.2

    # OBV tells us if volume is on up days or down days
    obv_bullish = obv_direction in ["confirming_uptrend", "accumulation"]
    obv_bearish = obv_direction in ["confirming_downtrend", "distribution"]

    # Analyze confirmation
    if volume_expanding and obv_bullish:
        confirmation = "STRONG"
        description = "Volume expanding on advances - money committing to upside"
        participation = "increasing"
    elif volume_expanding and obv_bearish:
        confirmation = "STRONG_BEARISH"
        description = "Volume expanding on declines - distribution underway"
        participation = "increasing (sellers)"
    elif volume_contracting and obv_bullish:
        confirmation = "WEAK"
        description = "Low volume advance - fragile move, needs confirmation"
        participation = "thin"
    elif volume_contracting and obv_bearish:
        confirmation = "WEAK_BEARISH"
        description = "Low volume decline - may be temporary"
        participation = "thin"
    elif obv_divergence == "bullish":
        confirmation = "DIVERGENT_BULLISH"
        description = "Accumulation despite price weakness - smart money buying"
        participation = "hidden buying"
    elif obv_divergence == "bearish":
        confirmation = "DIVERGENT_BEARISH"
        description = "Distribution despite price strength - smart money selling"
        participation = "hidden selling"
    else:
        confirmation = "NEUTRAL"
        description = "Volume neutral - no strong signal"
        participation = "normal"

    return {
        "confirmation": confirmation,
        "description": description,
        "participation": participation,
        "volume_ratio": volume_ratio,
        "volume_expanding": volume_expanding,
        "volume_contracting": volume_contracting,
    }


def detect_cycle_position(
    pct_from_52w_low: float,
    pct_from_52w_high: float,
    rsi: float,
    momentum_phase: str,
    volume_confirmation: str
) -> Dict[str, Any]:
    """
    Determine where we are in the cycle.

    Positions:
    - EARLY: Near lows, momentum turning, good risk/reward
    - MID: Trend established, still room to run
    - LATE: Extended, euphoric, reduced risk/reward
    - BOTTOMING: Near lows, momentum stabilizing
    - TOPPING: Near highs, momentum fading
    """
    if pct_from_52w_low is None or pct_from_52w_high is None:
        return {"position": "unknown"}

    # Calculate position in range
    total_range = pct_from_52w_low - pct_from_52w_high  # This will be positive
    # pct_from_52w_high is negative (below high), pct_from_52w_low is positive (above low)

    # Near 52w high
    near_high = pct_from_52w_high > -5  # Within 5% of high
    near_low = pct_from_52w_low < 15  # Within 15% of low

    # RSI extremes
    rsi_overbought = rsi > 70 if rsi else False
    rsi_oversold = rsi < 30 if rsi else False

    # Classify position
    if near_low and momentum_phase in ["ACCELERATING", "STEADY"]:
        position = "EARLY"
        description = "Early stage advance - best risk/reward"
        action = "Consider adding on confirmation"
        risk_reward = "favorable"
    elif near_low and momentum_phase == "DECELERATING":
        position = "BOTTOMING"
        description = "Potential bottom forming - watch for momentum turn"
        action = "Watch, prepare to buy on strength"
        risk_reward = "favorable if confirmed"
    elif near_high and momentum_phase == "DECELERATING":
        position = "LATE"
        description = "Late stage advance - risk elevated"
        action = "Trade management, not new entries"
        risk_reward = "unfavorable"
    elif near_high and rsi_overbought:
        position = "TOPPING"
        description = "Potential top forming - extreme caution"
        action = "Consider reducing, tighten stops"
        risk_reward = "poor"
    elif pct_from_52w_high < -20 and momentum_phase == "ACCELERATING":
        position = "MID"
        description = "Mid-trend advance - trend intact"
        action = "Hold, add on pullbacks"
        risk_reward = "moderate"
    else:
        position = "MID"
        description = "Mid-cycle - normal trend behavior"
        action = "Hold current position"
        risk_reward = "moderate"

    return {
        "position": position,
        "description": description,
        "action": action,
        "risk_reward": risk_reward,
        "pct_from_high": pct_from_52w_high,
        "pct_from_low": pct_from_52w_low,
    }


def generate_pro_recommendation(
    regime: Dict[str, Any],
    momentum: Dict[str, Any],
    volume: Dict[str, Any],
    cycle: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate professional-style recommendation.

    Possible actions (most of the time it's NOT buy/sell):
    - ADD: Increase position
    - HOLD: Maintain current position
    - REDUCE: Decrease position
    - WAIT: Stay on sidelines
    - TIGHTEN: Keep position but tighten stops
    - DO NOTHING: Valid professional decision
    """
    regime_type = regime.get("regime", "unknown")
    momentum_phase = momentum.get("phase", "unknown")
    volume_conf = volume.get("confirmation", "unknown")
    cycle_pos = cycle.get("position", "unknown")

    # Decision matrix
    action = "HOLD"
    reasoning = []
    confidence = "moderate"

    # Regime-based baseline
    if regime_type == "BULLISH":
        action = "HOLD"
        reasoning.append("Regime bullish - maintain long bias")

        if momentum_phase == "ACCELERATING" and volume_conf == "STRONG":
            action = "ADD"
            reasoning.append("Momentum accelerating with volume confirmation")
            confidence = "high"
        elif momentum_phase == "DECELERATING":
            action = "HOLD"
            reasoning.append("Momentum cooling - stop chasing, but don't sell")
        elif momentum_phase == "DIVERGING":
            action = "TIGHTEN"
            reasoning.append("Divergence detected - tighten risk management")

    elif regime_type == "BEARISH":
        action = "WAIT"
        reasoning.append("Regime bearish - avoid longs")

        if momentum_phase == "DIVERGING" and momentum.get("divergence_type") == "bullish":
            action = "WATCH"
            reasoning.append("Bullish divergence in downtrend - potential reversal")
        elif volume_conf == "DIVERGENT_BULLISH":
            action = "WATCH"
            reasoning.append("Accumulation detected - smart money may be buying")

    elif regime_type == "RANGE":
        action = "WAIT"
        reasoning.append("No clear trend - wait for breakout")
        confidence = "low"

    elif regime_type == "TRANSITIONAL":
        action = "REDUCE"
        reasoning.append("Regime changing - reduce exposure")

    # Cycle position adjustments
    if cycle_pos == "LATE":
        if action == "ADD":
            action = "HOLD"
            reasoning.append("Late stage - not adding at elevated levels")
        elif action == "HOLD":
            action = "TIGHTEN"
            reasoning.append("Late stage advance - tighten stops")

    elif cycle_pos == "EARLY":
        if action in ["HOLD", "WAIT"] and regime_type == "BULLISH":
            action = "ADD"
            reasoning.append("Early stage with bullish regime - favorable entry")
            confidence = "high"

    # Volume confirmation adjustments
    if volume_conf in ["WEAK", "WEAK_BEARISH"]:
        if action == "ADD":
            action = "WAIT"
            reasoning.append("Low volume - wait for participation")
        reasoning.append("Thin participation - move is fragile")

    if volume_conf == "DIVERGENT_BEARISH" and action != "WAIT":
        action = "REDUCE"
        reasoning.append("Distribution detected - reduce exposure")

    # Generate summary
    summary = generate_market_summary(regime, momentum, volume, cycle, action)

    return {
        "action": action,
        "confidence": confidence,
        "reasoning": reasoning,
        "summary": summary,
        "regime": regime_type,
        "momentum_phase": momentum_phase,
        "cycle_position": cycle_pos,
    }


def generate_market_summary(
    regime: Dict[str, Any],
    momentum: Dict[str, Any],
    volume: Dict[str, Any],
    cycle: Dict[str, Any],
    action: str
) -> str:
    """
    Generate a professional market summary label.

    Examples:
    - "Bullish trend, momentum cooling - hold, stop chasing"
    - "Late-stage advance, risk elevated - tighten stops"
    - "Consolidation within uptrend - wait for breakout"
    - "Distribution risk rising - consider reducing"
    """
    regime_type = regime.get("regime", "unknown")
    momentum_phase = momentum.get("phase", "unknown")
    cycle_pos = cycle.get("position", "unknown")
    volume_conf = volume.get("confirmation", "unknown")

    # Build summary
    parts = []

    # Regime part
    if regime_type == "BULLISH":
        parts.append("Bullish trend")
    elif regime_type == "BEARISH":
        parts.append("Bearish trend")
    elif regime_type == "RANGE":
        parts.append("Range-bound")
    elif regime_type == "TRANSITIONAL":
        parts.append("Regime transitioning")

    # Momentum part
    if momentum_phase == "ACCELERATING":
        parts.append("momentum building")
    elif momentum_phase == "DECELERATING":
        parts.append("momentum cooling")
    elif momentum_phase == "DIVERGING":
        parts.append("divergence warning")
    elif momentum_phase == "STEADY":
        parts.append("momentum stable")

    # Risk/cycle part
    if cycle_pos == "LATE":
        parts.append("late-stage")
    elif cycle_pos == "EARLY":
        parts.append("early-stage")
    elif cycle_pos == "TOPPING":
        parts.append("topping risk")
    elif cycle_pos == "BOTTOMING":
        parts.append("bottoming pattern")

    # Volume part (only if notable)
    if volume_conf == "DIVERGENT_BEARISH":
        parts.append("distribution detected")
    elif volume_conf == "DIVERGENT_BULLISH":
        parts.append("accumulation detected")
    elif volume_conf in ["WEAK", "WEAK_BEARISH"]:
        parts.append("thin participation")

    # Join parts
    if len(parts) >= 2:
        summary = f"{parts[0]}, {', '.join(parts[1:])}"
    else:
        summary = parts[0] if parts else "Insufficient data"

    # Add action
    action_labels = {
        "ADD": "consider adding",
        "HOLD": "hold position",
        "REDUCE": "consider reducing",
        "WAIT": "stay patient",
        "TIGHTEN": "tighten stops",
        "WATCH": "watch for confirmation",
        "DO NOTHING": "no action needed"
    }

    action_label = action_labels.get(action, action.lower())
    summary = f"{summary} - {action_label}"

    return summary


def get_full_market_analysis(
    indicators: Dict[str, Any],
    macro_bias: str = "neutral"
) -> Dict[str, Any]:
    """
    Run the complete professional analysis framework.

    Returns comprehensive analysis with:
    - Regime classification
    - Momentum phase
    - Volume confirmation
    - Cycle position
    - Pro recommendation
    """
    # Extract needed values
    price = indicators.get("spot_price") or indicators.get("last_close")
    sma200 = indicators.get("sma200")
    sma50 = indicators.get("sma50")
    trend = indicators.get("trend", "unknown")
    rsi = indicators.get("rsi14")

    # RSI momentum data
    rsi_momentum = indicators.get("rsi_momentum", {})
    rsi_change = rsi_momentum.get("change", 0)
    rsi_direction = rsi_momentum.get("direction", "flat")

    # MACD data
    macd_momentum = indicators.get("macd_momentum", {})
    macd_histogram = macd_momentum.get("histogram", 0)
    macd_hist_change = macd_momentum.get("histogram_change", 0)
    macd_above_zero = macd_momentum.get("above_zero", False)

    # Volume data
    volume_ratio = indicators.get("volume_ratio")
    volume_signal = indicators.get("volume_signal", "N/A")
    obv_momentum = indicators.get("obv_momentum", {})
    obv_direction = obv_momentum.get("direction", "neutral")
    obv_divergence = obv_momentum.get("divergence")

    # Price levels
    pct_from_52w_low = indicators.get("pct_from_52w_low", 0)
    pct_from_52w_high = indicators.get("pct_from_52w_high", 0)

    # Run analysis
    regime = classify_regime(price, sma200, sma50, trend, rsi, macro_bias)

    # Determine price direction for volume analysis
    if trend == "uptrend":
        price_direction = "up"
    elif trend == "downtrend":
        price_direction = "down"
    else:
        price_direction = "flat"

    momentum = analyze_momentum_phase(
        rsi, rsi_change, rsi_direction,
        macd_histogram, macd_hist_change, macd_above_zero,
        trend
    )

    volume = analyze_volume_confirmation(
        volume_ratio, volume_signal,
        obv_direction, obv_divergence,
        price_direction
    )

    cycle = detect_cycle_position(
        pct_from_52w_low, pct_from_52w_high,
        rsi, momentum.get("phase", "unknown"),
        volume.get("confirmation", "unknown")
    )

    recommendation = generate_pro_recommendation(regime, momentum, volume, cycle)

    return {
        "regime": regime,
        "momentum": momentum,
        "volume": volume,
        "cycle": cycle,
        "recommendation": recommendation,
        "summary": recommendation.get("summary", "Analysis unavailable"),
    }
