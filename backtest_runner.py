"""
Forward Expectations Backtesting System

Walks through historical dates, computing 5-pillar state and forward returns.
This creates the foundation for probabilistic forward expectations based on
historical state-outcome relationships.

Usage:
    python backtest_runner.py [metal] [--start YYYY-MM-DD] [--end YYYY-MM-DD]

Example:
    python backtest_runner.py gold
    python backtest_runner.py silver --start 2020-01-01
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import argparse
import sys

from indicators import compute_indicators_from_df
from market_regime import get_five_pillar_analysis

# Configuration
DATA_DIR = Path(__file__).resolve().parent / "data"
WARMUP_DAYS = 220  # 200 for SMA200 + 20 buffer for slope calculations
FORWARD_WINDOW = 20  # Need 20 days forward for returns

# File mappings - use the full history files
HISTORY_FILES = {
    "gold": DATA_DIR / "xau_history_full.csv",
    "silver": DATA_DIR / "xag_history_full.csv",
    "copper": DATA_DIR / "hg_history.csv",  # Copper has limited history
}


def load_full_history(metal: str) -> Optional[pd.DataFrame]:
    """
    Load full historical OHLCV data for a metal.

    Args:
        metal: "gold", "silver", or "copper"

    Returns:
        DataFrame with DatetimeIndex and OHLCV columns, or None if not found
    """
    filepath = HISTORY_FILES.get(metal.lower())
    if filepath is None or not filepath.exists():
        print(f"Warning: No history file found for {metal} at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath, parse_dates=["Date"], index_col="Date")
        df = df.sort_index()

        # Ensure required columns exist
        required = ["Open", "High", "Low", "Close"]
        if not all(col in df.columns for col in required):
            print(f"Warning: Missing required columns in {filepath}")
            return None

        # Volume might not exist for all data sources
        if "Volume" not in df.columns:
            df["Volume"] = 0

        return df

    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def slice_to_date(df: pd.DataFrame, target_date: pd.Timestamp) -> pd.DataFrame:
    """
    Slice DataFrame to include only data up to and including target_date.

    This is THE KEY FUNCTION - it allows compute_indicators() with its .iloc[-1]
    calls to work correctly for any historical date.

    Args:
        df: Full historical DataFrame with DatetimeIndex
        target_date: The date to slice to (inclusive)

    Returns:
        DataFrame containing only rows <= target_date
    """
    return df[df.index <= target_date].copy()


def compute_state_for_date(
    full_history: pd.DataFrame,
    target_date: pd.Timestamp,
    metal: str = "gold"
) -> Optional[Dict[str, Any]]:
    """
    Compute 5-pillar state for a specific historical date.

    Args:
        full_history: Complete price history DataFrame
        target_date: Date to compute state for
        metal: "gold", "silver", or "copper"

    Returns:
        Dict with state information, or None if insufficient data
    """
    # Slice data to target date
    sliced_df = slice_to_date(full_history, target_date)

    # Check we have enough data for warmup
    if len(sliced_df) < WARMUP_DAYS:
        return None

    # Compute indicators from sliced DataFrame
    indicators = compute_indicators_from_df(sliced_df)
    if "error" in indicators:
        return None

    # Use neutral defaults for macro/COT in MVP
    # (Historical macro/COT data requires additional API setup)
    macro_tailwind = {"status": "neutral", "description": "Backtest MVP - using neutral"}
    cot_data = None  # Will result in "unknown" positioning

    # Run 5-pillar analysis
    try:
        five_pillar = get_five_pillar_analysis(indicators, macro_tailwind, cot_data)
    except Exception as e:
        print(f"Error in 5-pillar analysis for {target_date}: {e}")
        return None

    return {
        "date": target_date,
        "close": float(sliced_df["Close"].iloc[-1]),
        "regime": five_pillar["regime"]["regime"],
        "momentum": five_pillar["momentum"]["phase"],
        "participation": five_pillar["participation"]["status"],
        "tailwind": five_pillar["tailwind"]["status"],
        "positioning": five_pillar["positioning"]["status"],
        # Store raw values for debugging
        "adx": indicators.get("adx"),
        "rsi14": indicators.get("rsi14"),
        "sma50_slope": indicators.get("sma50_slope"),
    }


def calculate_forward_returns(
    full_history: pd.DataFrame,
    target_date: pd.Timestamp,
    horizons: List[int] = [5, 10, 20]
) -> Dict[str, Optional[float]]:
    """
    Calculate forward returns and risk metrics from target_date.

    Args:
        full_history: Complete price history
        target_date: Starting date
        horizons: List of forward days to calculate

    Returns:
        Dict with forward returns and MAE/MFE metrics
    """
    result = {}

    try:
        # Get index position of target_date
        if target_date not in full_history.index:
            # Find nearest date
            mask = full_history.index <= target_date
            if not mask.any():
                return {f"fwd_{h}d_return": None for h in horizons}
            target_date = full_history.index[mask][-1]

        target_idx = full_history.index.get_loc(target_date)
        base_price = full_history["Close"].iloc[target_idx]

        # Forward returns for each horizon
        for h in horizons:
            if target_idx + h < len(full_history):
                future_price = full_history["Close"].iloc[target_idx + h]
                result[f"fwd_{h}d_return"] = ((future_price - base_price) / base_price) * 100
            else:
                result[f"fwd_{h}d_return"] = None

        # MAE/MFE for 5-day window (Max Adverse/Favorable Excursion)
        if target_idx + 5 <= len(full_history):
            window = full_history["Close"].iloc[target_idx:target_idx + 6]  # Include start day
            # MAE: worst drawdown from entry (negative value)
            result["fwd_5d_mae"] = ((window.min() - base_price) / base_price) * 100
            # MFE: best gain from entry (positive value)
            result["fwd_5d_mfe"] = ((window.max() - base_price) / base_price) * 100
        else:
            result["fwd_5d_mae"] = None
            result["fwd_5d_mfe"] = None

        # 20-day MAE/MFE for longer-term risk assessment
        if target_idx + 20 <= len(full_history):
            window_20 = full_history["Close"].iloc[target_idx:target_idx + 21]
            result["fwd_20d_mae"] = ((window_20.min() - base_price) / base_price) * 100
            result["fwd_20d_mfe"] = ((window_20.max() - base_price) / base_price) * 100
        else:
            result["fwd_20d_mae"] = None
            result["fwd_20d_mfe"] = None

    except Exception as e:
        print(f"Error calculating forward returns for {target_date}: {e}")
        for h in horizons:
            result[f"fwd_{h}d_return"] = None
        result["fwd_5d_mae"] = None
        result["fwd_5d_mfe"] = None
        result["fwd_20d_mae"] = None
        result["fwd_20d_mfe"] = None

    return result


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
    since macro and positioning use neutral defaults.

    Args:
        regime: "uptrend", "downtrend", or "range"
        momentum: "accelerating", "cooling", "diverging", "steady"
        participation: "confirming", "thinning", "distribution", etc.
        tailwind: Optional macro tailwind status
        positioning: Optional COT positioning status
        include_all: If True, include all 5 pillars in hash

    Returns:
        String hash for grouping (e.g., "Ru_Ma_Pc" for Uptrend/Accelerating/Confirming)
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


def run_backtest(
    metal: str = "gold",
    start_date: str = None,
    end_date: str = None,
    step_days: int = 1,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Run backtest for a metal, computing state and forward returns for each date.

    Args:
        metal: "gold", "silver", or "copper"
        start_date: Start date string (YYYY-MM-DD), default: after warmup period
        end_date: End date string (YYYY-MM-DD), default: 20 days before last data
        step_days: Days between observations (1 = every day, 5 = weekly)
        verbose: Print progress updates

    Returns:
        DataFrame with all backtest observations
    """
    # Load full history
    full_history = load_full_history(metal)

    if full_history is None or len(full_history) < WARMUP_DAYS + FORWARD_WINDOW:
        raise ValueError(f"Insufficient history for {metal}")

    if verbose:
        print(f"Loaded {len(full_history)} rows of {metal} history")
        print(f"Date range: {full_history.index[0].date()} to {full_history.index[-1].date()}")

    # Determine date range
    if start_date is None:
        start_idx = WARMUP_DAYS
        start_dt = full_history.index[start_idx]
    else:
        start_dt = pd.to_datetime(start_date)

    if end_date is None:
        end_idx = len(full_history) - FORWARD_WINDOW - 1
        end_dt = full_history.index[end_idx]
    else:
        end_dt = pd.to_datetime(end_date)

    # Generate observation dates
    mask = (full_history.index >= start_dt) & (full_history.index <= end_dt)
    all_dates = full_history.loc[mask].index
    observation_dates = all_dates[::step_days]

    if verbose:
        print(f"\nRunning backtest: {len(observation_dates)} observations")
        print(f"Observation range: {observation_dates[0].date()} to {observation_dates[-1].date()}")

    records = []
    skipped = 0

    for i, target_date in enumerate(observation_dates):
        if verbose and i % 500 == 0:
            print(f"  Processing {i}/{len(observation_dates)}: {target_date.date()}")

        # Compute state
        state = compute_state_for_date(full_history, target_date, metal)

        if state is None:
            skipped += 1
            continue

        # Calculate forward returns
        fwd_returns = calculate_forward_returns(full_history, target_date)

        # Combine into record
        record = {
            **state,
            "metal": metal,
            "state_hash": encode_state_hash(
                state["regime"], state["momentum"], state["participation"]
            ),
            **fwd_returns,
            "valid": fwd_returns.get("fwd_20d_return") is not None
        }

        records.append(record)

    df = pd.DataFrame(records)

    if verbose:
        print(f"\nCompleted: {len(df)} valid observations ({skipped} skipped)")
        if len(df) > 0:
            print(f"Unique states: {df['state_hash'].nunique()}")
            print(f"\nState distribution:")
            print(df['state_hash'].value_counts().head(10))

    return df


def save_backtest_results(df: pd.DataFrame, metal: str) -> Path:
    """Save backtest results to CSV."""
    output_path = DATA_DIR / f"backtest_{metal}.csv"
    df.to_csv(output_path, index=False)
    print(f"Saved backtest results to {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run forward expectations backtest")
    parser.add_argument("metal", nargs="?", default="gold",
                        choices=["gold", "silver", "copper"],
                        help="Metal to backtest (default: gold)")
    parser.add_argument("--start", type=str, default=None,
                        help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None,
                        help="End date (YYYY-MM-DD)")
    parser.add_argument("--step", type=int, default=1,
                        help="Days between observations (default: 1)")
    parser.add_argument("--no-save", action="store_true",
                        help="Don't save results to CSV")

    args = parser.parse_args()

    print(f"=== Forward Expectations Backtest: {args.metal.upper()} ===\n")

    try:
        results = run_backtest(
            metal=args.metal,
            start_date=args.start,
            end_date=args.end,
            step_days=args.step,
            verbose=True
        )

        if not args.no_save and len(results) > 0:
            save_backtest_results(results, args.metal)

        # Print summary statistics
        if len(results) > 0:
            print("\n=== Summary Statistics ===")
            valid = results[results["valid"] == True]
            print(f"Total observations: {len(results)}")
            print(f"Valid (with 20d forward): {len(valid)}")
            print(f"\nOverall forward returns:")
            print(f"  5D mean:  {valid['fwd_5d_return'].mean():+.2f}%")
            print(f"  10D mean: {valid['fwd_10d_return'].mean():+.2f}%")
            print(f"  20D mean: {valid['fwd_20d_return'].mean():+.2f}%")
            print(f"  5D hit rate: {(valid['fwd_5d_return'] > 0).mean()*100:.1f}%")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
