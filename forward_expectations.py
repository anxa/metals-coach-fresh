"""
Forward Expectations Generator

Generates probabilistic forward expectations based on historical state outcomes.
This is what gets displayed to the user - the final output of the backtest system.

Usage:
    from forward_expectations import get_forward_expectations

    expectations = get_forward_expectations(
        current_five_pillar=gold_five,
        metal="gold"
    )
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"


def encode_state_hash(
    regime: str,
    momentum: str,
    participation: str,
    tailwind: str = None,
    positioning: str = None,
    include_all: bool = False
) -> str:
    """
    Create a unique hash for a state combination.

    For MVP, we focus on the 3 technical pillars (regime, momentum, participation)
    since macro and positioning use neutral defaults in backtest.
    """
    regime_code = {
        "uptrend": "u", "downtrend": "d", "range": "r", "unknown": "x"
    }
    momentum_code = {
        "accelerating": "a", "cooling": "c", "diverging": "v", "steady": "s", "unknown": "x"
    }
    participation_code = {
        "confirming": "c", "thinning": "t", "distribution": "d",
        "accumulation": "a", "neutral": "n", "unknown": "x"
    }

    r = regime_code.get(regime.lower() if regime else "unknown", "x")
    m = momentum_code.get(momentum.lower() if momentum else "unknown", "x")
    p = participation_code.get(participation.lower() if participation else "unknown", "x")

    # MVP: 3-pillar hash
    base_hash = f"R{r}_M{m}_P{p}"

    if include_all and tailwind and positioning:
        tailwind_code = {
            "supportive": "s", "hostile": "h", "mixed": "m", "neutral": "n", "unknown": "x"
        }
        positioning_code_full = {
            "crowded_long": "cl", "washed_out": "wo", "elevated_long": "el",
            "light_positioning": "lp", "neutral": "n", "unknown": "u"
        }
        t = tailwind_code.get(tailwind.lower() if tailwind else "unknown", "x")
        pos = positioning_code_full.get(positioning.lower() if positioning else "unknown", "x")
        return f"{base_hash}_T{t}_C{pos}"

    return base_hash


def load_aggregated_stats(metal: str) -> Optional[pd.DataFrame]:
    """Load pre-computed aggregated statistics for a metal."""
    filepath = DATA_DIR / f"backtest_{metal}_agg.csv"
    if not filepath.exists():
        return None
    return pd.read_csv(filepath)


def format_state_readable(
    regime: str,
    momentum: str,
    participation: str
) -> str:
    """Format state for human-readable display."""
    return f"{regime.title()} / {momentum.title()} / {participation.title()}"


def classify_expected_return(mean_return: float) -> str:
    """
    Classify expected return into simple categories.

    This avoids false precision - we're communicating direction, not exact numbers.
    """
    if mean_return > 1.0:
        return "strongly_positive"
    elif mean_return > 0.25:
        return "positive"
    elif mean_return > -0.25:
        return "flat"
    elif mean_return > -1.0:
        return "negative"
    else:
        return "strongly_negative"


def generate_risk_warnings(
    stats: Dict[str, Any],
    current_state: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate risk warnings based on statistics and current state.

    Warnings come from:
    1. Statistical patterns (low hit rate, high volatility, large MAE)
    2. Current state conditions (divergence, crowded positioning)
    """
    warnings = []

    # === Statistical warnings ===

    # Low sample size warning
    n_samples = stats.get("n_samples", 0)
    if n_samples < 30:
        warnings.append({
            "type": "low_samples",
            "severity": "medium",
            "message": f"Only {n_samples} historical observations - statistics may be less reliable"
        })

    # High volatility warning
    std_5d = stats.get("std_5d", 0)
    if std_5d > 3.0:
        warnings.append({
            "type": "high_volatility",
            "severity": "high",
            "message": f"High volatility state - expect {std_5d:.1f}% swings in 5 days"
        })

    # Near 50% hit rate (low directional edge)
    hit_rate = stats.get("hit_rate_5d", 50)
    if 45 < hit_rate < 55:
        warnings.append({
            "type": "low_edge",
            "severity": "medium",
            "message": "Near 50% hit rate - no clear directional edge historically"
        })

    # Large adverse excursion warning
    avg_mae = stats.get("avg_mae_5d", 0)
    if avg_mae < -2.0:
        warnings.append({
            "type": "drawdown_risk",
            "severity": "high",
            "message": f"Avg drawdown of {abs(avg_mae):.1f}% before gains materialize"
        })

    # Poor risk/reward
    risk_reward = stats.get("risk_reward_5d", 1.0)
    if risk_reward < 0.8:
        warnings.append({
            "type": "poor_risk_reward",
            "severity": "medium",
            "message": f"Risk/reward ratio of {risk_reward:.2f} - drawdowns exceed gains"
        })

    # === State-based warnings ===

    # Momentum divergence warning
    momentum_data = current_state.get("momentum", {})
    if momentum_data.get("divergence_type"):
        div_type = momentum_data["divergence_type"]
        warnings.append({
            "type": "divergence_active",
            "severity": "high",
            "message": f"{div_type.title()} divergence detected - elevated reversal risk"
        })

    # Cooling momentum in uptrend
    regime = current_state.get("regime", {}).get("regime", "")
    momentum_phase = momentum_data.get("phase", "")
    participation = current_state.get("participation", {}).get("status", "")

    if regime == "uptrend" and momentum_phase == "cooling":
        if participation in ["thinning", "distribution"]:
            warnings.append({
                "type": "pullback_likely",
                "severity": "high",
                "message": "Uptrend with cooling momentum and weak participation - pullback probable"
            })
        else:
            warnings.append({
                "type": "momentum_weakening",
                "severity": "medium",
                "message": "Momentum cooling in uptrend - watch for trend continuation or reversal"
            })

    # Crowded positioning warning
    positioning = current_state.get("positioning", {})
    pos_status = positioning.get("status", "")
    if pos_status in ["crowded_long", "elevated_long"]:
        warnings.append({
            "type": "crowded_positioning",
            "severity": "medium",
            "message": "Elevated long positioning - late-cycle risk, watch for profit-taking"
        })
    elif pos_status == "washed_out":
        warnings.append({
            "type": "washed_out",
            "severity": "low",  # This is actually bullish!
            "message": "Light positioning - room for new longs if setup confirms"
        })

    # Distribution in uptrend
    if regime == "uptrend" and participation == "distribution":
        warnings.append({
            "type": "distribution_warning",
            "severity": "high",
            "message": "Distribution pattern detected - smart money may be selling into strength"
        })

    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    warnings.sort(key=lambda w: severity_order.get(w["severity"], 3))

    return warnings


def calculate_invalidation_level(
    current_state: Dict[str, Any],
    stats: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate price level that would invalidate the current setup.

    This teaches discipline - every trade idea has a point where it's wrong.
    """
    regime = current_state.get("regime", {}).get("regime", "range")
    metrics = current_state.get("regime", {}).get("metrics", {})

    # Get MAE for stop suggestion
    avg_mae = abs(stats.get("avg_mae_5d", 2.0))

    if regime == "uptrend":
        return {
            "trigger": "Close below SMA200",
            "description": "A daily close below the 200-day SMA invalidates the uptrend thesis",
            "structural_level": "SMA200",
            "suggested_stop": f"Consider stop at {avg_mae:.1f}% below entry based on historical MAE",
            "based_on_mae": round(stats.get("avg_mae_5d", -2.0), 2)
        }
    elif regime == "downtrend":
        return {
            "trigger": "Close above SMA200",
            "description": "A daily close above the 200-day SMA invalidates the downtrend thesis",
            "structural_level": "SMA200",
            "suggested_stop": f"Consider stop at {avg_mae:.1f}% above entry (for shorts)",
            "based_on_mae": round(stats.get("avg_mae_5d", -2.0), 2)
        }
    else:  # range
        return {
            "trigger": "ADX crossing above 25 with directional break",
            "description": "Strong trend emergence (ADX > 25) ends the range-bound condition",
            "structural_level": "Range boundaries",
            "suggested_stop": f"Consider stop at {avg_mae:.1f}% outside range boundaries",
            "based_on_mae": round(stats.get("avg_mae_5d", -2.0), 2)
        }


def get_forward_expectations(
    current_five_pillar: Dict[str, Any],
    metal: str = "gold"
) -> Dict[str, Any]:
    """
    Generate forward expectations JSON for UI display.

    This is the main entry point - takes current 5-pillar state and returns
    probabilistic expectations based on historical data.

    Args:
        current_five_pillar: Output from get_five_pillar_analysis()
        metal: "gold", "silver", or "copper"

    Returns:
        Dict with expectations, risk warnings, and invalidation levels
    """
    # Extract state components
    regime = current_five_pillar.get("regime", {}).get("regime", "unknown")
    momentum = current_five_pillar.get("momentum", {}).get("phase", "unknown")
    participation = current_five_pillar.get("participation", {}).get("status", "unknown")
    tailwind = current_five_pillar.get("tailwind", {}).get("status", "neutral")
    positioning = current_five_pillar.get("positioning", {}).get("status", "unknown")

    # Generate state hash (3-pillar MVP version)
    state_hash = encode_state_hash(regime, momentum, participation)

    # Load pre-computed statistics
    agg_stats = load_aggregated_stats(metal)

    if agg_stats is None:
        return {
            "metal": metal,
            "state_hash": state_hash,
            "state_readable": format_state_readable(regime, momentum, participation),
            "has_data": False,
            "message": f"No backtest data available for {metal}. Run: python backtest_runner.py {metal}",
            "suggestion": "Historical statistics not yet computed"
        }

    # Look up stats for current state
    state_match = agg_stats[agg_stats["state_hash"] == state_hash]

    if state_match.empty:
        # State not found - might be rare or need more samples
        return {
            "metal": metal,
            "state_hash": state_hash,
            "state_readable": format_state_readable(regime, momentum, participation),
            "has_data": False,
            "message": "This state combination is rare in historical data",
            "suggestion": "Insufficient observations - use caution and rely on other signals",
            "total_states_available": len(agg_stats)
        }

    # Extract statistics
    stats = state_match.iloc[0].to_dict()

    # Generate output
    result = {
        "metal": metal,
        "state_hash": state_hash,
        "state_readable": format_state_readable(regime, momentum, participation),
        "has_data": True,

        # Sample info
        "n_samples": int(stats["n_samples"]),
        "confidence_score": round(stats["confidence_score"], 1),
        "edge_class": stats.get("edge_class", "neutral"),

        # Forward expectations by horizon
        "expectations": {
            "5d": {
                "mean": round(stats["mean_5d"], 2),
                "median": round(stats["median_5d"], 2),
                "std": round(stats["std_5d"], 2),
                "hit_rate": round(stats["hit_rate_5d"], 1),
                "direction": classify_expected_return(stats["mean_5d"]),
                "typical_range": [
                    round(stats["median_5d"] - stats["std_5d"], 2),
                    round(stats["median_5d"] + stats["std_5d"], 2)
                ]
            },
            "10d": {
                "mean": round(stats["mean_10d"], 2),
                "median": round(stats["median_10d"], 2),
                "std": round(stats["std_10d"], 2),
                "hit_rate": round(stats["hit_rate_10d"], 1),
                "direction": classify_expected_return(stats["mean_10d"]),
            },
            "20d": {
                "mean": round(stats["mean_20d"], 2),
                "median": round(stats["median_20d"], 2),
                "std": round(stats["std_20d"], 2),
                "hit_rate": round(stats["hit_rate_20d"], 1),
                "direction": classify_expected_return(stats["mean_20d"]),
            }
        },

        # Risk metrics
        "risk_metrics": {
            "avg_drawdown_5d": round(stats["avg_mae_5d"], 2),
            "worst_drawdown_5d": round(stats.get("worst_mae_5d", stats["avg_mae_5d"]), 2),
            "avg_runup_5d": round(stats["avg_mfe_5d"], 2),
            "risk_reward_ratio": round(stats.get("risk_reward_5d", 1.0), 2),
            "expectancy_5d": round(stats.get("expectancy_5d", 0), 3)
        },

        # Risk warnings
        "warnings": generate_risk_warnings(stats, current_five_pillar),

        # Invalidation level
        "invalidation": calculate_invalidation_level(current_five_pillar, stats),

        # Current state details (for context)
        "current_state": {
            "regime": regime,
            "momentum": momentum,
            "participation": participation,
            "tailwind": tailwind,
            "positioning": positioning
        }
    }

    return result


def format_expectations_text(expectations: Dict[str, Any]) -> str:
    """
    Format expectations as human-readable text summary.

    This is what an expert trader would say about the setup.
    """
    if not expectations.get("has_data"):
        return expectations.get("message", "No historical data available")

    state = expectations["state_readable"]
    n = expectations["n_samples"]
    conf = expectations["confidence_score"]

    exp_5d = expectations["expectations"]["5d"]
    exp_20d = expectations["expectations"]["20d"]

    lines = [
        f"**State:** {state}",
        f"**Historical Observations:** {n} instances (confidence: {conf:.0f}/100)",
        "",
        "**Forward Expectations:**",
        f"• 5-Day: {exp_5d['direction'].replace('_', ' ').title()} "
        f"(mean {exp_5d['mean']:+.2f}%, hit rate {exp_5d['hit_rate']:.0f}%)",
        f"• 20-Day: {exp_20d['direction'].replace('_', ' ').title()} "
        f"(mean {exp_20d['mean']:+.2f}%, hit rate {exp_20d['hit_rate']:.0f}%)",
        "",
        f"**Risk Profile:**",
        f"• Typical 5D range: {exp_5d['typical_range'][0]:+.1f}% to {exp_5d['typical_range'][1]:+.1f}%",
        f"• Avg drawdown before gains: {expectations['risk_metrics']['avg_drawdown_5d']:.1f}%",
    ]

    # Add warnings
    warnings = expectations.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("**Warnings:**")
        for w in warnings[:3]:  # Top 3 warnings
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(w["severity"], "⚪")
            lines.append(f"• {severity_icon} {w['message']}")

    # Add invalidation
    inv = expectations.get("invalidation", {})
    if inv:
        lines.append("")
        lines.append(f"**Invalidation:** {inv.get('trigger', 'N/A')}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test with sample data
    print("=== Forward Expectations Test ===\n")

    # Simulate current 5-pillar state
    test_state = {
        "regime": {"regime": "uptrend", "metrics": {}},
        "momentum": {"phase": "cooling", "divergence_type": None},
        "participation": {"status": "confirming"},
        "tailwind": {"status": "neutral"},
        "positioning": {"status": "neutral"}
    }

    expectations = get_forward_expectations(test_state, metal="gold")

    if expectations.get("has_data"):
        print(format_expectations_text(expectations))
    else:
        print(expectations.get("message"))
        print("\nRun the following to generate backtest data:")
        print("  python backtest_runner.py gold")
        print("  python backtest_aggregator.py gold")
