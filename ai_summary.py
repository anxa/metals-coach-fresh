"""
AI-powered market summary using Anthropic Claude API.

Synthesizes all indicators into an educational, actionable summary.
"""
import os
from typing import Dict, Any, Optional
import anthropic


def get_api_key():
    """Get Anthropic API key from Streamlit secrets or environment."""
    # Try Streamlit secrets first (for cloud deployment)
    try:
        import streamlit as st
        key = st.secrets.get("api_keys", {}).get("ANTHROPIC_API_KEY")
        if key:
            return key
    except Exception:
        pass

    # Fall back to environment variable (for local development)
    return os.getenv("ANTHROPIC_API_KEY")


def build_market_context(
    metal: str,
    spot_price: float,
    indicators: Dict[str, Any],
    cot: Dict[str, Any],
    macro: Dict[str, Any],
    term_structure: Dict[str, Any],
) -> str:
    """Build a structured context string with all market data."""

    lines = [f"=== {metal.upper()} MARKET DATA ===\n"]

    # Price levels
    lines.append("PRICE LEVELS:")
    lines.append(f"  Spot Price: ${spot_price:,.2f}" if spot_price else "  Spot Price: N/A")
    lines.append(f"  Futures Price: ${indicators.get('futures_price', 0):,.2f}" if indicators.get('futures_price') else "  Futures: N/A")
    lines.append(f"  All-Time High: ${indicators.get('ath', 0):,.2f}" if indicators.get('ath') else "  ATH: N/A")
    lines.append(f"  52-Week High: ${indicators.get('52w_high', 0):,.2f}" if indicators.get('52w_high') else "  52w High: N/A")
    lines.append(f"  52-Week Low: ${indicators.get('52w_low', 0):,.2f}" if indicators.get('52w_low') else "  52w Low: N/A")
    lines.append(f"  % from ATH: {indicators.get('pct_from_ath', 0):+.1f}%" if indicators.get('pct_from_ath') is not None else "")
    lines.append(f"  % from 52w High: {indicators.get('pct_from_52w_high', 0):+.1f}%" if indicators.get('pct_from_52w_high') is not None else "")
    lines.append(f"  % from 52w Low: {indicators.get('pct_from_52w_low', 0):+.1f}%" if indicators.get('pct_from_52w_low') is not None else "")

    # Trend & Moving Averages
    lines.append("\nTREND & MOVING AVERAGES:")
    lines.append(f"  Trend Classification: {indicators.get('trend', 'unknown').upper()}")
    lines.append(f"  SMA 20/50/200: ${indicators.get('sma20', 0):,.2f} / ${indicators.get('sma50', 0):,.2f} / ${indicators.get('sma200', 0):,.2f}")
    lines.append(f"  EMA 20/50/200: ${indicators.get('ema20', 0):,.2f} / ${indicators.get('ema50', 0):,.2f} / ${indicators.get('ema200', 0):,.2f}")

    # Price vs MAs
    if spot_price and indicators.get('sma200'):
        pct_above_200 = ((spot_price - indicators['sma200']) / indicators['sma200']) * 100
        lines.append(f"  Price vs 200-day SMA: {pct_above_200:+.1f}%")

    # Momentum
    lines.append("\nMOMENTUM INDICATORS:")
    lines.append(f"  RSI(14): {indicators.get('rsi14', 0):.1f}" if indicators.get('rsi14') else "  RSI: N/A")
    lines.append(f"  MACD Crossover: {indicators.get('macd_crossover', 'unknown')}")
    lines.append(f"  MACD Histogram Slope: {indicators.get('macd_histogram_slope', 'unknown')}")
    lines.append(f"  OBV Trend: {indicators.get('obv_trend', 'unknown')}")
    lines.append(f"  Volume vs 20d Avg: {indicators.get('volume_ratio', 0):.2f}x ({indicators.get('volume_signal', 'N/A')})" if indicators.get('volume_ratio') else "  Volume: N/A")

    # COT Positioning
    if "error" not in cot:
        lines.append("\nCOT POSITIONING (Commitment of Traders):")
        lines.append(f"  Report Date: {cot.get('report_date', 'N/A')}")
        lines.append(f"  Commercial Hedgers Net: {cot.get('commercial_net', 0):,} contracts")
        lines.append(f"  Commercial WoW Change: {cot.get('commercial_wow', 0):+,}")
        lines.append(f"  Commercial 3yr Percentile: {cot.get('commercial_percentile', 0):.1f}%")
        lines.append(f"  Commercial Signal: {cot.get('commercial_signal', 'neutral')}")
        lines.append(f"  Managed Money Net: {cot.get('managed_money_net', 0):,} contracts")
        lines.append(f"  Managed Money WoW Change: {cot.get('managed_money_wow', 0):+,}")
        lines.append(f"  Managed Money 3yr Percentile: {cot.get('managed_money_percentile', 0):.1f}%")
        lines.append(f"  Managed Money Signal: {cot.get('managed_money_signal', 'neutral')}")
        lines.append(f"  MM Momentum: {cot.get('mm_momentum', 'unknown')}")
        lines.append(f"  Open Interest: {cot.get('open_interest', 0):,}")
    else:
        lines.append("\nCOT POSITIONING: Data unavailable")

    # Macro Drivers
    if "error" not in macro:
        lines.append("\nMACRO DRIVERS:")
        lines.append(f"  Overall Macro Bias: {macro.get('macro_bias', 'neutral').upper()}")

        inds = macro.get("indicators", {})

        dxy = inds.get("dxy", {})
        if "error" not in dxy:
            lines.append(f"  US Dollar (DXY): {dxy.get('value', 0):.2f} (change: {dxy.get('change', 0):+.2f})")
            lines.append(f"    Gold Impact: {dxy.get('gold_impact', 'neutral')}")

        real = inds.get("real_yield", {})
        if "current" in real:
            lines.append(f"  10Y Real Yield (TIPS): {real.get('current', 0):.2f}%")
            lines.append(f"    Gold Impact: {real.get('gold_impact', 'neutral')}")
            lines.append(f"    Interpretation: {real.get('interpretation', '')}")

        vix = inds.get("vix", {})
        if "error" not in vix:
            lines.append(f"  VIX: {vix.get('value', 0):.1f} ({vix.get('regime', '')})")
            lines.append(f"    Gold Impact: {vix.get('gold_impact', 'neutral')}")

        move = inds.get("move", {})
        if "error" not in move:
            lines.append(f"  MOVE Index: {move.get('value', 0):.1f} ({move.get('regime', '')})")
            lines.append(f"    Gold Impact: {move.get('gold_impact', 'neutral')}")
    else:
        lines.append("\nMACRO DRIVERS: Data unavailable")

    # Term Structure
    if "error" not in term_structure:
        lines.append("\nTERM STRUCTURE (Futures Curve):")
        lines.append(f"  Structure: {term_structure.get('structure', 'unknown').upper()}")
        lines.append(f"  Spot vs Futures Spread: {term_structure.get('spread_pct', 0):+.2f}%")
        lines.append(f"  Annualized Basis: {term_structure.get('annualized_basis_pct', 0):+.1f}%")
        lines.append(f"  Signal: {term_structure.get('signal', 'neutral')}")
        lines.append(f"  Interpretation: {term_structure.get('interpretation', '')}")
    else:
        lines.append("\nTERM STRUCTURE: Data unavailable")

    return "\n".join(lines)


def generate_ai_summary(
    metal: str,
    spot_price: float,
    indicators: Dict[str, Any],
    cot: Dict[str, Any],
    macro: Dict[str, Any],
    term_structure: Dict[str, Any],
) -> Optional[str]:
    """
    Generate an AI-powered market summary using Claude.

    Returns:
        Markdown-formatted summary string, or None if API unavailable.
    """
    api_key = get_api_key()
    if not api_key:
        return None

    # Build context
    context = build_market_context(metal, spot_price, indicators, cot, macro, term_structure)

    prompt = f"""You are an expert precious metals analyst and trading coach. Analyze the following market data for {metal} and provide an educational summary.

{context}

Please provide a comprehensive analysis in the following format:

## Overall Assessment
Give a clear 1-2 sentence verdict on the current market setup (bullish, bearish, or neutral) with confidence level.

## What the Data is Telling Us
Explain the key signals from each category in plain English:
- Price action and trend
- Momentum indicators
- COT positioning (what the smart money is doing)
- Macro environment
- Term structure

## Key Confluence Signals
Identify where multiple indicators are pointing in the same direction (this is what matters most).

## What to Watch
List 2-3 specific levels, events, or data points that could change the outlook.

## Educational Takeaway
Explain ONE key lesson about reading markets that this current setup illustrates well.

Keep the tone educational and instructive. Explain the "why" behind each observation. Be direct about probabilities and avoid wishy-washy language. If the setup is unclear, say so - that's useful information too.

Format your response in clean markdown."""

    try:
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text

    except Exception as e:
        return f"*AI Summary unavailable: {str(e)}*"


def get_quick_verdict(
    indicators: Dict[str, Any],
    cot: Dict[str, Any],
    macro: Dict[str, Any],
    term_structure: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a quick algorithmic verdict without AI.
    Useful as a fallback or for quick display.
    """
    bullish_signals = 0
    bearish_signals = 0
    signals = []

    # Trend
    trend = indicators.get('trend', 'unknown')
    if trend == 'uptrend':
        bullish_signals += 2
        signals.append(("Trend", "bullish", "Price in uptrend (MA alignment)"))
    elif trend == 'downtrend':
        bearish_signals += 2
        signals.append(("Trend", "bearish", "Price in downtrend (MA alignment)"))
    else:
        signals.append(("Trend", "neutral", "Choppy/unclear trend"))

    # RSI
    rsi = indicators.get('rsi14')
    if rsi:
        if rsi < 30:
            bullish_signals += 1
            signals.append(("RSI", "bullish", f"Oversold at {rsi:.1f}"))
        elif rsi > 70:
            bearish_signals += 1
            signals.append(("RSI", "bearish", f"Overbought at {rsi:.1f}"))
        else:
            signals.append(("RSI", "neutral", f"Neutral at {rsi:.1f}"))

    # MACD
    macd_cross = indicators.get('macd_crossover')
    macd_slope = indicators.get('macd_histogram_slope')
    if macd_cross == 'bullish' and macd_slope == 'rising':
        bullish_signals += 1
        signals.append(("MACD", "bullish", "Bullish crossover with rising histogram"))
    elif macd_cross == 'bearish' and macd_slope == 'falling':
        bearish_signals += 1
        signals.append(("MACD", "bearish", "Bearish crossover with falling histogram"))
    elif macd_cross:
        signals.append(("MACD", "neutral", f"{macd_cross} crossover, histogram {macd_slope}"))

    # COT
    if "error" not in cot:
        comm_signal = cot.get('commercial_signal')
        mm_signal = cot.get('managed_money_signal')

        if comm_signal == 'bullish':
            bullish_signals += 2
            signals.append(("COT Commercials", "bullish", "Hedgers less short than usual"))
        elif comm_signal == 'bearish':
            bearish_signals += 2
            signals.append(("COT Commercials", "bearish", "Hedgers very short"))

        if mm_signal == 'extreme_short':
            bullish_signals += 1  # Contrarian
            signals.append(("COT Managed Money", "bullish", "Specs very short (contrarian bullish)"))
        elif mm_signal == 'extreme_long':
            bearish_signals += 1  # Contrarian
            signals.append(("COT Managed Money", "bearish", "Specs very long (contrarian bearish)"))

    # Macro
    if "error" not in macro:
        macro_bias = macro.get('macro_bias')
        if macro_bias == 'bullish':
            bullish_signals += 2
            signals.append(("Macro", "bullish", "Multiple macro factors supportive"))
        elif macro_bias == 'bearish':
            bearish_signals += 2
            signals.append(("Macro", "bearish", "Macro headwinds for gold"))
        else:
            signals.append(("Macro", "neutral", "Mixed macro signals"))

    # Term Structure
    if "error" not in term_structure:
        structure = term_structure.get('structure', '')
        if 'backwardation' in structure:
            bullish_signals += 2
            signals.append(("Term Structure", "bullish", f"{structure} - physical tightness"))
        elif 'steep contango' in structure:
            bearish_signals += 1
            signals.append(("Term Structure", "bearish", "Steep contango - weak physical demand"))
        else:
            signals.append(("Term Structure", "neutral", structure))

    # Overall verdict
    net_score = bullish_signals - bearish_signals
    if net_score >= 4:
        verdict = "STRONGLY BULLISH"
    elif net_score >= 2:
        verdict = "BULLISH"
    elif net_score <= -4:
        verdict = "STRONGLY BEARISH"
    elif net_score <= -2:
        verdict = "BEARISH"
    else:
        verdict = "NEUTRAL"

    return {
        "verdict": verdict,
        "bullish_signals": bullish_signals,
        "bearish_signals": bearish_signals,
        "net_score": net_score,
        "signals": signals,
    }


def get_copper_verdict(
    indicators: Dict[str, Any],
    cot: Dict[str, Any],
    copper_macro: Dict[str, Any],
    term_structure: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a copper-specific algorithmic verdict.

    Copper uses different signals than gold:
    - PMI data (China + US) instead of real yields
    - No VIX/MOVE (copper is risk-on, not safe haven)
    - USD/CNY instead of just DXY
    """
    bullish_signals = 0
    bearish_signals = 0
    signals = []

    # Trend (same as gold)
    trend = indicators.get('trend', 'unknown')
    if trend == 'uptrend':
        bullish_signals += 2
        signals.append(("Trend", "bullish", "Price in uptrend (MA alignment)"))
    elif trend == 'downtrend':
        bearish_signals += 2
        signals.append(("Trend", "bearish", "Price in downtrend (MA alignment)"))
    else:
        signals.append(("Trend", "neutral", "Choppy/unclear trend"))

    # RSI (same as gold)
    rsi = indicators.get('rsi14')
    if rsi:
        if rsi < 30:
            bullish_signals += 1
            signals.append(("RSI", "bullish", f"Oversold at {rsi:.1f}"))
        elif rsi > 70:
            bearish_signals += 1
            signals.append(("RSI", "bearish", f"Overbought at {rsi:.1f}"))
        else:
            signals.append(("RSI", "neutral", f"Neutral at {rsi:.1f}"))

    # MACD (same as gold)
    macd_cross = indicators.get('macd_crossover')
    macd_slope = indicators.get('macd_histogram_slope')
    if macd_cross == 'bullish' and macd_slope == 'rising':
        bullish_signals += 1
        signals.append(("MACD", "bullish", "Bullish crossover with rising histogram"))
    elif macd_cross == 'bearish' and macd_slope == 'falling':
        bearish_signals += 1
        signals.append(("MACD", "bearish", "Bearish crossover with falling histogram"))
    elif macd_cross:
        signals.append(("MACD", "neutral", f"{macd_cross} crossover, histogram {macd_slope}"))

    # COT (same as gold)
    if "error" not in cot:
        comm_signal = cot.get('commercial_signal')
        mm_signal = cot.get('managed_money_signal')

        if comm_signal == 'bullish':
            bullish_signals += 2
            signals.append(("COT Commercials", "bullish", "Hedgers less short than usual"))
        elif comm_signal == 'bearish':
            bearish_signals += 2
            signals.append(("COT Commercials", "bearish", "Hedgers very short"))

        if mm_signal == 'extreme_short':
            bullish_signals += 1  # Contrarian
            signals.append(("COT Managed Money", "bullish", "Specs very short (contrarian bullish)"))
        elif mm_signal == 'extreme_long':
            bearish_signals += 1  # Contrarian
            signals.append(("COT Managed Money", "bearish", "Specs very long (contrarian bearish)"))

    # Copper-specific: PMI data (instead of real yields/VIX)
    if "error" not in copper_macro:
        copper_inds = copper_macro.get("indicators", {})

        # China PMI - THE key driver for copper
        china_pmi = copper_inds.get("china_pmi", {})
        if "value" in china_pmi:
            pmi_val = china_pmi["value"]
            impact = china_pmi.get("copper_impact", "neutral")
            if impact in ["strongly bullish", "bullish"]:
                bullish_signals += 2
                signals.append(("China PMI", "bullish", f"Manufacturing expanding at {pmi_val:.1f}"))
            elif impact in ["strongly bearish", "bearish"]:
                bearish_signals += 2
                signals.append(("China PMI", "bearish", f"Manufacturing contracting at {pmi_val:.1f}"))
            else:
                signals.append(("China PMI", "neutral", f"PMI at {pmi_val:.1f}"))

        # US ISM PMI
        us_pmi = copper_inds.get("us_ism_pmi", {})
        if "value" in us_pmi:
            pmi_val = us_pmi["value"]
            impact = us_pmi.get("copper_impact", "neutral")
            if impact in ["bullish", "mildly bullish"]:
                bullish_signals += 1
                signals.append(("US ISM PMI", "bullish", f"US manufacturing at {pmi_val:.1f}"))
            elif impact in ["bearish", "mildly bearish"]:
                bearish_signals += 1
                signals.append(("US ISM PMI", "bearish", f"US manufacturing at {pmi_val:.1f}"))
            else:
                signals.append(("US ISM PMI", "neutral", f"PMI at {pmi_val:.1f}"))

        # USD/CNY
        usd_cny = copper_inds.get("usd_cny", {})
        if "value" in usd_cny:
            impact = usd_cny.get("copper_impact", "neutral")
            trend = usd_cny.get("trend", "stable")
            if impact == "bullish":
                bullish_signals += 1
                signals.append(("USD/CNY", "bullish", f"USD weakening vs yuan ({trend})"))
            elif impact == "bearish":
                bearish_signals += 1
                signals.append(("USD/CNY", "bearish", f"USD strengthening vs yuan ({trend})"))
            else:
                signals.append(("USD/CNY", "neutral", trend))

    # Term Structure (same as gold)
    if "error" not in term_structure:
        structure = term_structure.get('structure', '')
        if 'backwardation' in structure:
            bullish_signals += 2
            signals.append(("Term Structure", "bullish", f"{structure} - physical tightness"))
        elif 'steep contango' in structure:
            bearish_signals += 1
            signals.append(("Term Structure", "bearish", "Steep contango - weak physical demand"))
        else:
            signals.append(("Term Structure", "neutral", structure))

    # Overall verdict
    net_score = bullish_signals - bearish_signals
    if net_score >= 4:
        verdict = "STRONGLY BULLISH"
    elif net_score >= 2:
        verdict = "BULLISH"
    elif net_score <= -4:
        verdict = "STRONGLY BEARISH"
    elif net_score <= -2:
        verdict = "BEARISH"
    else:
        verdict = "NEUTRAL"

    return {
        "verdict": verdict,
        "bullish_signals": bullish_signals,
        "bearish_signals": bearish_signals,
        "net_score": net_score,
        "signals": signals,
    }


if __name__ == "__main__":
    # Test with sample data
    test_indicators = {
        "trend": "uptrend",
        "rsi14": 58.5,
        "macd_crossover": "bullish",
        "macd_histogram_slope": "rising",
        "futures_price": 2650.0,
        "ath": 2800.0,
        "52w_high": 2750.0,
        "52w_low": 1950.0,
        "pct_from_ath": -5.4,
        "sma20": 2620.0,
        "sma50": 2580.0,
        "sma200": 2400.0,
    }

    test_cot = {
        "commercial_net": -250000,
        "commercial_percentile": 45.0,
        "commercial_signal": "neutral",
        "managed_money_net": 180000,
        "managed_money_percentile": 65.0,
        "managed_money_signal": "neutral",
    }

    test_macro = {
        "macro_bias": "bullish",
    }

    test_term = {
        "structure": "mild contango",
        "signal": "neutral",
    }

    verdict = get_quick_verdict(test_indicators, test_cot, test_macro, test_term)
    print(f"Verdict: {verdict['verdict']}")
    print(f"Bullish signals: {verdict['bullish_signals']}")
    print(f"Bearish signals: {verdict['bearish_signals']}")
    print("\nSignals:")
    for name, direction, desc in verdict['signals']:
        print(f"  {name}: {direction} - {desc}")
