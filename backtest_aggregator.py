"""
Backtest Aggregator

Aggregates backtest results by state combination to generate statistics
that power forward expectations.

Usage:
    python backtest_aggregator.py [metal]

Example:
    python backtest_aggregator.py gold
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional
import argparse

DATA_DIR = Path(__file__).resolve().parent / "data"


def load_backtest_results(metal: str) -> Optional[pd.DataFrame]:
    """Load backtest results CSV for a metal."""
    filepath = DATA_DIR / f"backtest_{metal}.csv"
    if not filepath.exists():
        print(f"No backtest results found at {filepath}")
        print(f"Run: python backtest_runner.py {metal}")
        return None

    df = pd.read_csv(filepath, parse_dates=["date"])
    return df


def aggregate_by_state(
    df: pd.DataFrame,
    min_samples: int = 10,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Aggregate backtest results by state_hash.

    Args:
        df: Backtest results DataFrame
        min_samples: Minimum observations required for statistical significance
        verbose: Print progress

    Returns:
        DataFrame with aggregated statistics per state
    """
    # Filter to valid observations only
    valid_df = df[df["valid"] == True].copy()

    if verbose:
        print(f"Aggregating {len(valid_df)} valid observations")
        print(f"Unique states: {valid_df['state_hash'].nunique()}")

    # Group by state_hash and compute statistics
    agg_list = []

    for state_hash, group in valid_df.groupby("state_hash"):
        if len(group) < min_samples:
            continue

        row = {
            "state_hash": state_hash,
            "n_samples": len(group),

            # State components (for readability)
            "regime": group["regime"].iloc[0],
            "momentum": group["momentum"].iloc[0],
            "participation": group["participation"].iloc[0],

            # 5-day forward returns
            "mean_5d": group["fwd_5d_return"].mean(),
            "median_5d": group["fwd_5d_return"].median(),
            "std_5d": group["fwd_5d_return"].std(),
            "min_5d": group["fwd_5d_return"].min(),
            "max_5d": group["fwd_5d_return"].max(),
            "hit_rate_5d": (group["fwd_5d_return"] > 0).mean() * 100,

            # 10-day forward returns
            "mean_10d": group["fwd_10d_return"].mean(),
            "median_10d": group["fwd_10d_return"].median(),
            "std_10d": group["fwd_10d_return"].std(),
            "hit_rate_10d": (group["fwd_10d_return"] > 0).mean() * 100,

            # 20-day forward returns
            "mean_20d": group["fwd_20d_return"].mean(),
            "median_20d": group["fwd_20d_return"].median(),
            "std_20d": group["fwd_20d_return"].std(),
            "hit_rate_20d": (group["fwd_20d_return"] > 0).mean() * 100,

            # Risk metrics (MAE = Max Adverse Excursion)
            "avg_mae_5d": group["fwd_5d_mae"].mean(),
            "median_mae_5d": group["fwd_5d_mae"].median(),
            "worst_mae_5d": group["fwd_5d_mae"].min(),  # Most negative

            # MFE (Max Favorable Excursion)
            "avg_mfe_5d": group["fwd_5d_mfe"].mean(),
            "median_mfe_5d": group["fwd_5d_mfe"].median(),
            "best_mfe_5d": group["fwd_5d_mfe"].max(),

            # 20-day risk metrics
            "avg_mae_20d": group["fwd_20d_mae"].mean() if "fwd_20d_mae" in group.columns else None,
            "avg_mfe_20d": group["fwd_20d_mfe"].mean() if "fwd_20d_mfe" in group.columns else None,
        }

        agg_list.append(row)

    agg_df = pd.DataFrame(agg_list)

    if len(agg_df) == 0:
        print(f"Warning: No states with >= {min_samples} samples")
        return pd.DataFrame()

    # Calculate confidence scores
    agg_df = calculate_confidence_scores(agg_df)

    # Calculate edge quality
    agg_df = calculate_edge_quality(agg_df)

    # Sort by confidence score
    agg_df = agg_df.sort_values("confidence_score", ascending=False)

    if verbose:
        print(f"Generated {len(agg_df)} aggregated states (min {min_samples} samples)")

    return agg_df


def calculate_confidence_scores(agg_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate confidence score based on:
    1. Sample size (more samples = higher confidence)
    2. Consistency (lower std = higher confidence)
    3. Hit rate distance from 50% (more extreme = higher confidence)

    Score ranges from 0-100.
    """
    scores = []

    for _, row in agg_df.iterrows():
        # Sample size component (0-40 points)
        # 10 samples = 4 pts, 50 samples = 20 pts, 100+ samples = 40 pts
        n = row["n_samples"]
        sample_score = min(40, n * 0.4)

        # Consistency component (0-30 points)
        # Lower coefficient of variation = higher score
        if row["std_5d"] > 0 and abs(row["mean_5d"]) > 0.01:
            cv = abs(row["std_5d"] / row["mean_5d"])
            consistency_score = max(0, 30 - min(cv * 5, 30))
        else:
            consistency_score = 15  # Default for edge cases

        # Hit rate component (0-30 points)
        # Distance from 50% hit rate (50% = no edge)
        hit_rate = row["hit_rate_5d"]
        hr_distance = abs(hit_rate - 50)
        hr_score = min(30, hr_distance * 0.6)

        total = sample_score + consistency_score + hr_score
        scores.append(min(100, max(0, total)))

    agg_df["confidence_score"] = scores

    return agg_df


def calculate_edge_quality(agg_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate edge quality metrics:
    - Risk/Reward ratio
    - Expectancy
    - Edge classification
    """
    # Risk/Reward ratio (MFE / |MAE|)
    agg_df["risk_reward_5d"] = agg_df.apply(
        lambda r: abs(r["avg_mfe_5d"] / r["avg_mae_5d"])
        if r["avg_mae_5d"] != 0 else 0, axis=1
    )

    # Expectancy = (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
    # Approximated using mean return and hit rate
    agg_df["expectancy_5d"] = agg_df.apply(
        lambda r: (r["hit_rate_5d"]/100 * r["avg_mfe_5d"]) +
                  ((100-r["hit_rate_5d"])/100 * r["avg_mae_5d"]), axis=1
    )

    # Edge classification
    def classify_edge(row):
        hr = row["hit_rate_5d"]
        rr = row["risk_reward_5d"]
        mean = row["mean_5d"]

        if hr >= 60 and mean > 0.5:
            return "strong_bullish"
        elif hr >= 55 and mean > 0.2:
            return "bullish"
        elif hr <= 40 and mean < -0.5:
            return "strong_bearish"
        elif hr <= 45 and mean < -0.2:
            return "bearish"
        elif rr > 1.5 and mean > 0:
            return "asymmetric_bullish"
        elif rr > 1.5 and mean < 0:
            return "asymmetric_bearish"
        else:
            return "neutral"

    agg_df["edge_class"] = agg_df.apply(classify_edge, axis=1)

    return agg_df


def get_state_stats(
    agg_df: pd.DataFrame,
    state_hash: str
) -> Optional[Dict[str, Any]]:
    """Get statistics for a specific state hash."""
    match = agg_df[agg_df["state_hash"] == state_hash]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def format_state_readable(regime: str, momentum: str, participation: str) -> str:
    """Format state components for human-readable display."""
    return f"{regime.title()} / {momentum.title()} / {participation.title()}"


def print_state_analysis(agg_df: pd.DataFrame, top_n: int = 10):
    """Print detailed analysis of top states."""
    print("\n" + "=" * 70)
    print("TOP STATES BY CONFIDENCE SCORE")
    print("=" * 70)

    for i, (_, row) in enumerate(agg_df.head(top_n).iterrows()):
        state = format_state_readable(row["regime"], row["momentum"], row["participation"])
        print(f"\n{i+1}. {state}")
        print(f"   Hash: {row['state_hash']} | Samples: {row['n_samples']}")
        print(f"   Confidence: {row['confidence_score']:.1f} | Edge: {row['edge_class']}")
        print(f"   5D:  Mean {row['mean_5d']:+.2f}% | Hit Rate {row['hit_rate_5d']:.1f}%")
        print(f"   20D: Mean {row['mean_20d']:+.2f}% | Hit Rate {row['hit_rate_20d']:.1f}%")
        print(f"   Risk: Avg MAE {row['avg_mae_5d']:.2f}% | R:R {row['risk_reward_5d']:.2f}")


def save_aggregated_results(agg_df: pd.DataFrame, metal: str) -> Path:
    """Save aggregated results to CSV."""
    output_path = DATA_DIR / f"backtest_{metal}_agg.csv"
    agg_df.to_csv(output_path, index=False)
    print(f"Saved aggregated results to {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aggregate backtest results")
    parser.add_argument("metal", nargs="?", default="gold",
                        choices=["gold", "silver", "copper"],
                        help="Metal to aggregate (default: gold)")
    parser.add_argument("--min-samples", type=int, default=10,
                        help="Minimum samples per state (default: 10)")
    parser.add_argument("--top", type=int, default=10,
                        help="Number of top states to display (default: 10)")

    args = parser.parse_args()

    print(f"=== Backtest Aggregation: {args.metal.upper()} ===\n")

    # Load backtest results
    results = load_backtest_results(args.metal)
    if results is None:
        exit(1)

    print(f"Loaded {len(results)} backtest observations")

    # Aggregate by state
    agg = aggregate_by_state(results, min_samples=args.min_samples)

    if len(agg) > 0:
        # Save results
        save_aggregated_results(agg, args.metal)

        # Print analysis
        print_state_analysis(agg, top_n=args.top)

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total states analyzed: {len(agg)}")
        print(f"Strong bullish states: {len(agg[agg['edge_class'] == 'strong_bullish'])}")
        print(f"Bullish states: {len(agg[agg['edge_class'] == 'bullish'])}")
        print(f"Neutral states: {len(agg[agg['edge_class'] == 'neutral'])}")
        print(f"Bearish states: {len(agg[agg['edge_class'] == 'bearish'])}")
        print(f"Strong bearish states: {len(agg[agg['edge_class'] == 'strong_bearish'])}")
