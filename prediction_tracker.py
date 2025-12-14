"""
Prediction Tracker

Logs daily 5-pillar predictions and forward expectations, then updates with
actual outcomes to measure prediction accuracy over time.

Features:
- Auto-logs predictions after US market close (4pm ET)
- Tracks invalidation levels and whether they were hit
- Updates actuals automatically when data becomes available
- Calculates accuracy statistics by state

Usage:
    from prediction_tracker import auto_log_daily, update_actuals, get_accuracy_stats

    # Auto-log today's predictions (called from app.py)
    auto_log_daily(gold_five, gold_exp, gold_price, gold_indicators,
                   silver_five, silver_exp, silver_price, silver_indicators)

    # Update pending actuals
    update_actuals()

    # Get accuracy stats
    stats = get_accuracy_stats()
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import pytz

DATA_DIR = Path(__file__).resolve().parent / "data"
PREDICTION_LOG_PATH = DATA_DIR / "prediction_log.csv"

# Timezone for US market hours
ET = pytz.timezone("US/Eastern")

# CSV columns
PREDICTION_COLUMNS = [
    "date", "metal", "spot_price",
    "regime", "momentum", "participation", "tailwind", "positioning",
    "state_hash",
    "exp_5d_mean", "exp_5d_hit_rate", "exp_20d_mean", "exp_20d_hit_rate",
    "confidence_score", "edge_class", "n_samples",
    "invalidation_trigger", "invalidation_level",
    "actual_5d_return", "actual_20d_return",
    "direction_correct_5d", "direction_correct_20d",
    "was_invalidated", "invalidation_date",
    "logged_at", "updated_at"
]


def load_prediction_log() -> pd.DataFrame:
    """Load existing prediction log or create empty DataFrame."""
    if PREDICTION_LOG_PATH.exists():
        df = pd.read_csv(PREDICTION_LOG_PATH, parse_dates=["date", "logged_at", "updated_at", "invalidation_date"])
        return df
    return pd.DataFrame(columns=PREDICTION_COLUMNS)


def save_prediction_log(df: pd.DataFrame) -> None:
    """Save prediction log to CSV."""
    DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(PREDICTION_LOG_PATH, index=False)


def is_market_closed() -> bool:
    """Check if US market is closed (after 4pm ET)."""
    now_et = datetime.now(ET)
    market_close = time(16, 0)  # 4pm ET
    return now_et.time() >= market_close


def get_today_et() -> datetime:
    """Get today's date in ET timezone."""
    return datetime.now(ET).date()


def prediction_exists(date: datetime, metal: str) -> bool:
    """Check if prediction already exists for date/metal combo."""
    df = load_prediction_log()
    if df.empty:
        return False

    date_str = pd.to_datetime(date).strftime("%Y-%m-%d")
    mask = (df["date"].dt.strftime("%Y-%m-%d") == date_str) & (df["metal"] == metal)
    return mask.any()


def calculate_invalidation_level(
    five_pillar: Dict[str, Any],
    indicators: Dict[str, Any],
    spot_price: float
) -> Tuple[str, Optional[float]]:
    """
    Calculate the actual price level that would invalidate the current thesis.

    Returns:
        Tuple of (trigger_description, price_level)
    """
    regime = five_pillar.get("regime", {}).get("regime", "unknown")

    # Get SMA200 from indicators
    sma200 = indicators.get("sma200")

    if regime == "uptrend":
        trigger = "Close below SMA200"
        level = sma200 if sma200 else None
    elif regime == "downtrend":
        trigger = "Close above SMA200"
        level = sma200 if sma200 else None
    else:  # range
        trigger = "ADX > 25 with directional break"
        level = None  # Range invalidation is not a specific price level

    return trigger, level


def log_prediction(
    metal: str,
    five_pillar: Dict[str, Any],
    forward_expectations: Dict[str, Any],
    spot_price: float,
    indicators: Dict[str, Any],
    date: datetime = None
) -> bool:
    """
    Log one prediction with invalidation level.

    Deduplicates on (date, metal) - won't log if already exists.

    Args:
        metal: "gold" or "silver"
        five_pillar: Output from get_five_pillar_analysis()
        forward_expectations: Output from get_forward_expectations()
        spot_price: Current spot price
        indicators: Output from compute_indicators()
        date: Date to log for (defaults to today ET)

    Returns:
        True if logged, False if already exists or error
    """
    if date is None:
        date = get_today_et()

    # Check for duplicates
    if prediction_exists(date, metal):
        return False

    # Extract 5-pillar components
    regime = five_pillar.get("regime", {}).get("regime", "unknown")
    momentum = five_pillar.get("momentum", {}).get("phase", "unknown")
    participation = five_pillar.get("participation", {}).get("status", "unknown")
    tailwind = five_pillar.get("tailwind", {}).get("status", "unknown")
    positioning = five_pillar.get("positioning", {}).get("status", "unknown")

    # Extract forward expectations
    has_data = forward_expectations.get("has_data", False)

    if has_data:
        exp_5d = forward_expectations.get("expectations", {}).get("5d", {})
        exp_20d = forward_expectations.get("expectations", {}).get("20d", {})
        exp_5d_mean = exp_5d.get("mean")
        exp_5d_hit_rate = exp_5d.get("hit_rate")
        exp_20d_mean = exp_20d.get("mean")
        exp_20d_hit_rate = exp_20d.get("hit_rate")
        confidence_score = forward_expectations.get("confidence_score")
        edge_class = forward_expectations.get("edge_class")
        n_samples = forward_expectations.get("n_samples")
        state_hash = forward_expectations.get("state_hash")
    else:
        exp_5d_mean = None
        exp_5d_hit_rate = None
        exp_20d_mean = None
        exp_20d_hit_rate = None
        confidence_score = None
        edge_class = None
        n_samples = None
        state_hash = forward_expectations.get("state_hash", "unknown")

    # Calculate invalidation level
    inv_trigger, inv_level = calculate_invalidation_level(five_pillar, indicators, spot_price)

    # Create record
    record = {
        "date": pd.to_datetime(date),
        "metal": metal,
        "spot_price": spot_price,
        "regime": regime,
        "momentum": momentum,
        "participation": participation,
        "tailwind": tailwind,
        "positioning": positioning,
        "state_hash": state_hash,
        "exp_5d_mean": exp_5d_mean,
        "exp_5d_hit_rate": exp_5d_hit_rate,
        "exp_20d_mean": exp_20d_mean,
        "exp_20d_hit_rate": exp_20d_hit_rate,
        "confidence_score": confidence_score,
        "edge_class": edge_class,
        "n_samples": n_samples,
        "invalidation_trigger": inv_trigger,
        "invalidation_level": inv_level,
        "actual_5d_return": None,
        "actual_20d_return": None,
        "direction_correct_5d": None,
        "direction_correct_20d": None,
        "was_invalidated": None,
        "invalidation_date": None,
        "logged_at": datetime.now(ET),
        "updated_at": None
    }

    # Load, append, save
    df = load_prediction_log()
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    save_prediction_log(df)

    return True


def auto_log_daily(
    gold_five: Dict[str, Any],
    gold_exp: Dict[str, Any],
    gold_price: float,
    gold_indicators: Dict[str, Any],
    silver_five: Dict[str, Any],
    silver_exp: Dict[str, Any],
    silver_price: float,
    silver_indicators: Dict[str, Any]
) -> Dict[str, bool]:
    """
    Auto-log today's predictions if:
    1. Not already logged today
    2. After 4pm ET (US market close)

    Returns:
        Dict of {metal: was_logged}
    """
    results = {"gold": False, "silver": False}

    # Only log after market close
    if not is_market_closed():
        return results

    today = get_today_et()

    # Log gold
    if not prediction_exists(today, "gold"):
        results["gold"] = log_prediction(
            metal="gold",
            five_pillar=gold_five,
            forward_expectations=gold_exp,
            spot_price=gold_price,
            indicators=gold_indicators,
            date=today
        )

    # Log silver
    if not prediction_exists(today, "silver"):
        results["silver"] = log_prediction(
            metal="silver",
            five_pillar=silver_five,
            forward_expectations=silver_exp,
            spot_price=silver_price,
            indicators=silver_indicators,
            date=today
        )

    return results


def load_price_history(metal: str) -> Optional[pd.DataFrame]:
    """Load price history for calculating actuals."""
    history_files = {
        "gold": DATA_DIR / "xau_history_full.csv",
        "silver": DATA_DIR / "xag_history_full.csv",
    }

    filepath = history_files.get(metal.lower())
    if filepath is None or not filepath.exists():
        return None

    df = pd.read_csv(filepath, parse_dates=["Date"], index_col="Date")
    df = df.sort_index()
    return df


def get_trading_day_offset(history: pd.DataFrame, base_date: datetime, offset: int) -> Optional[datetime]:
    """
    Get the trading day that is `offset` days after base_date.

    Args:
        history: Price history DataFrame with DatetimeIndex
        base_date: Starting date
        offset: Number of trading days forward

    Returns:
        Target date or None if not available
    """
    base_date = pd.to_datetime(base_date)

    # Find index of base_date or next available date
    mask = history.index >= base_date
    if not mask.any():
        return None

    future_dates = history.index[mask]

    if len(future_dates) <= offset:
        return None

    return future_dates[offset]


def check_invalidation(
    history: pd.DataFrame,
    base_date: datetime,
    invalidation_level: float,
    invalidation_trigger: str,
    max_days: int = 20
) -> Tuple[bool, Optional[datetime]]:
    """
    Check if price hit invalidation level within max_days.

    Args:
        history: Price history DataFrame
        base_date: Starting date
        invalidation_level: Price level to check
        invalidation_trigger: Type of invalidation
        max_days: Maximum trading days to check

    Returns:
        Tuple of (was_invalidated, invalidation_date)
    """
    if invalidation_level is None:
        return False, None

    base_date = pd.to_datetime(base_date)

    # Get future data window
    mask = history.index > base_date
    future_data = history[mask].head(max_days)

    if future_data.empty:
        return False, None

    # Check based on trigger type
    if "below" in invalidation_trigger.lower():
        # For uptrend: check if close went below level
        breaches = future_data[future_data["Close"] < invalidation_level]
    elif "above" in invalidation_trigger.lower():
        # For downtrend: check if close went above level
        breaches = future_data[future_data["Close"] > invalidation_level]
    else:
        # For range-bound, no specific level to check
        return False, None

    if not breaches.empty:
        return True, breaches.index[0]

    return False, None


def calculate_direction_correct(expected_mean: float, actual_return: float) -> Optional[bool]:
    """
    Determine if direction prediction was correct.

    Rules:
    - Expected > 0.25% (bullish) + Actual > 0 = Correct
    - Expected < -0.25% (bearish) + Actual < 0 = Correct
    - Expected -0.25% to 0.25% (flat) + Actual -1% to +1% = Correct
    """
    if expected_mean is None or actual_return is None:
        return None

    if pd.isna(expected_mean) or pd.isna(actual_return):
        return None

    # Bullish expectation
    if expected_mean > 0.25:
        return actual_return > 0

    # Bearish expectation
    if expected_mean < -0.25:
        return actual_return < 0

    # Flat expectation
    return -1.0 <= actual_return <= 1.0


def update_actuals(force_update: bool = False) -> Dict[str, int]:
    """
    Fill in actual returns and check invalidation for predictions >=5d or >=20d old.

    Args:
        force_update: If True, recalculate even if already filled

    Returns:
        Dict with counts: {"5d_updated": N, "20d_updated": N, "invalidations_checked": N}
    """
    df = load_prediction_log()

    if df.empty:
        return {"5d_updated": 0, "20d_updated": 0, "invalidations_checked": 0}

    counts = {"5d_updated": 0, "20d_updated": 0, "invalidations_checked": 0}
    today = pd.to_datetime(get_today_et())

    # Load price histories
    histories = {
        "gold": load_price_history("gold"),
        "silver": load_price_history("silver")
    }

    for idx, row in df.iterrows():
        metal = row["metal"]
        history = histories.get(metal)

        if history is None:
            continue

        pred_date = pd.to_datetime(row["date"])
        base_price = row["spot_price"]

        # Calculate days since prediction
        days_elapsed = (today - pred_date).days

        # Update 5d actual if eligible
        if days_elapsed >= 5 and (pd.isna(row["actual_5d_return"]) or force_update):
            target_date = get_trading_day_offset(history, pred_date, 5)

            if target_date is not None and target_date in history.index:
                target_price = history.loc[target_date, "Close"]
                actual_5d = ((target_price - base_price) / base_price) * 100
                df.at[idx, "actual_5d_return"] = round(actual_5d, 4)
                df.at[idx, "direction_correct_5d"] = calculate_direction_correct(
                    row["exp_5d_mean"], actual_5d
                )
                df.at[idx, "updated_at"] = datetime.now(ET)
                counts["5d_updated"] += 1

        # Update 20d actual if eligible
        if days_elapsed >= 20 and (pd.isna(row["actual_20d_return"]) or force_update):
            target_date = get_trading_day_offset(history, pred_date, 20)

            if target_date is not None and target_date in history.index:
                target_price = history.loc[target_date, "Close"]
                actual_20d = ((target_price - base_price) / base_price) * 100
                df.at[idx, "actual_20d_return"] = round(actual_20d, 4)
                df.at[idx, "direction_correct_20d"] = calculate_direction_correct(
                    row["exp_20d_mean"], actual_20d
                )
                df.at[idx, "updated_at"] = datetime.now(ET)
                counts["20d_updated"] += 1

        # Check invalidation if not already checked and has invalidation level
        if pd.isna(row["was_invalidated"]) and pd.notna(row["invalidation_level"]):
            was_inv, inv_date = check_invalidation(
                history, pred_date, row["invalidation_level"], row["invalidation_trigger"]
            )
            df.at[idx, "was_invalidated"] = was_inv
            if was_inv:
                df.at[idx, "invalidation_date"] = inv_date
            df.at[idx, "updated_at"] = datetime.now(ET)
            counts["invalidations_checked"] += 1

    save_prediction_log(df)
    return counts


def get_accuracy_stats(metal: str = None, state_hash: str = None) -> Dict[str, Any]:
    """
    Calculate accuracy metrics.

    Args:
        metal: Filter by metal (optional)
        state_hash: Filter by state hash (optional)

    Returns:
        Dict with accuracy statistics
    """
    df = load_prediction_log()

    if df.empty:
        return {
            "total_predictions": 0,
            "predictions_with_5d_actuals": 0,
            "predictions_with_20d_actuals": 0,
            "accuracy_5d": None,
            "accuracy_20d": None,
            "invalidation_rate": None,
            "accuracy_excluding_invalidated": None
        }

    # Apply filters
    if metal:
        df = df[df["metal"] == metal]
    if state_hash:
        df = df[df["state_hash"] == state_hash]

    total = len(df)

    # Count predictions with actuals
    has_5d = df["actual_5d_return"].notna().sum()
    has_20d = df["actual_20d_return"].notna().sum()

    # Calculate 5d accuracy
    df_5d = df[df["direction_correct_5d"].notna()]
    accuracy_5d = df_5d["direction_correct_5d"].mean() * 100 if len(df_5d) > 0 else None

    # Calculate 20d accuracy
    df_20d = df[df["direction_correct_20d"].notna()]
    accuracy_20d = df_20d["direction_correct_20d"].mean() * 100 if len(df_20d) > 0 else None

    # Invalidation rate
    df_inv_checked = df[df["was_invalidated"].notna()]
    if len(df_inv_checked) > 0:
        invalidation_rate = df_inv_checked["was_invalidated"].mean() * 100
    else:
        invalidation_rate = None

    # Accuracy excluding invalidated (for 20d)
    df_not_invalidated = df[(df["direction_correct_20d"].notna()) & (df["was_invalidated"] == False)]
    if len(df_not_invalidated) > 0:
        accuracy_excl_inv = df_not_invalidated["direction_correct_20d"].mean() * 100
    else:
        accuracy_excl_inv = None

    return {
        "total_predictions": total,
        "predictions_with_5d_actuals": int(has_5d),
        "predictions_with_20d_actuals": int(has_20d),
        "accuracy_5d": round(accuracy_5d, 1) if accuracy_5d else None,
        "accuracy_20d": round(accuracy_20d, 1) if accuracy_20d else None,
        "invalidation_rate": round(invalidation_rate, 1) if invalidation_rate else None,
        "accuracy_excluding_invalidated": round(accuracy_excl_inv, 1) if accuracy_excl_inv else None
    }


def get_state_breakdown() -> pd.DataFrame:
    """
    Get accuracy breakdown by state hash.

    Returns:
        DataFrame with columns: state_hash, n_predictions, accuracy_5d, accuracy_20d,
                                invalidation_rate, avg_confidence
    """
    df = load_prediction_log()

    if df.empty:
        return pd.DataFrame()

    results = []

    for state_hash, group in df.groupby("state_hash"):
        # Only include states with actuals
        has_5d = group[group["direction_correct_5d"].notna()]
        has_20d = group[group["direction_correct_20d"].notna()]
        has_inv = group[group["was_invalidated"].notna()]

        row = {
            "state_hash": state_hash,
            "regime": group["regime"].iloc[0],
            "momentum": group["momentum"].iloc[0],
            "participation": group["participation"].iloc[0],
            "n_predictions": len(group),
            "n_with_5d": len(has_5d),
            "n_with_20d": len(has_20d),
            "accuracy_5d": round(has_5d["direction_correct_5d"].mean() * 100, 1) if len(has_5d) > 0 else None,
            "accuracy_20d": round(has_20d["direction_correct_20d"].mean() * 100, 1) if len(has_20d) > 0 else None,
            "invalidation_rate": round(has_inv["was_invalidated"].mean() * 100, 1) if len(has_inv) > 0 else None,
            "avg_confidence": round(group["confidence_score"].mean(), 1) if group["confidence_score"].notna().any() else None
        }
        results.append(row)

    return pd.DataFrame(results).sort_values("n_predictions", ascending=False)


def get_recent_predictions(limit: int = 10, metal: str = None) -> pd.DataFrame:
    """
    Get most recent predictions with expected vs actual for display.

    Args:
        limit: Maximum number of predictions to return
        metal: Filter by metal (optional)

    Returns:
        DataFrame with key columns for UI display
    """
    df = load_prediction_log()

    if df.empty:
        return pd.DataFrame()

    if metal:
        df = df[df["metal"] == metal]

    # Sort by date descending
    df = df.sort_values("date", ascending=False).head(limit)

    # Select columns for display
    display_cols = [
        "date", "metal", "spot_price",
        "regime", "momentum", "participation",
        "exp_5d_mean", "actual_5d_return", "direction_correct_5d",
        "exp_20d_mean", "actual_20d_return", "direction_correct_20d",
        "was_invalidated", "confidence_score"
    ]

    return df[display_cols].copy()


def get_pending_count() -> Dict[str, int]:
    """
    Get count of predictions waiting for actuals.

    Returns:
        Dict with counts: {"pending_5d": N, "pending_20d": N}
    """
    df = load_prediction_log()

    if df.empty:
        return {"pending_5d": 0, "pending_20d": 0}

    today = pd.to_datetime(get_today_et())

    # Pending 5d: logged but no actual, and at least 5 days old
    eligible_5d = df[(today - df["date"]).dt.days >= 5]
    pending_5d = eligible_5d["actual_5d_return"].isna().sum()

    # Pending 20d: logged but no actual, and at least 20 days old
    eligible_20d = df[(today - df["date"]).dt.days >= 20]
    pending_20d = eligible_20d["actual_20d_return"].isna().sum()

    return {"pending_5d": int(pending_5d), "pending_20d": int(pending_20d)}


if __name__ == "__main__":
    # Test functions
    print("=== Prediction Tracker Test ===\n")

    print(f"Market closed: {is_market_closed()}")
    print(f"Today ET: {get_today_et()}")

    # Load and show stats
    stats = get_accuracy_stats()
    print(f"\nAccuracy Stats: {stats}")

    pending = get_pending_count()
    print(f"Pending: {pending}")

    # Show recent predictions
    recent = get_recent_predictions(5)
    if not recent.empty:
        print(f"\nRecent Predictions:\n{recent}")
    else:
        print("\nNo predictions logged yet.")
