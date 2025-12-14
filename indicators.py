import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any
from data_store import load_history


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    t = yf.Ticker(ticker)
    hist = t.history(period=period, interval=interval)
    return hist


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.rolling(window=window).mean()
    ma_down = down.rolling(window=window).mean()
    rs = ma_up / ma_down
    rsi = 100 - (100 / (1 + rs))
    return rsi


def high_low_52w(series: pd.Series) -> Dict[str, float]:
    """Calculate 52-week high and low."""
    # 52 weeks ~ 365 days; use last 252 trading days (~1 year)
    window = 252
    recent = series.dropna().iloc[-window:]
    return {
        "52w_high": float(recent.max()) if not recent.empty else float(series.max()),
        "52w_low": float(recent.min()) if not recent.empty else float(series.min()),
    }


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict[str, pd.Series]:
    """
    Calculate Average Directional Index (ADX) for trend strength measurement.

    ADX measures trend strength regardless of direction:
    - ADX > 25: Strong trend
    - ADX 18-25: Developing trend
    - ADX < 18: Weak/no trend (range-bound)

    Also returns +DI and -DI for directional bias.

    Returns:
        Dict with 'adx', 'plus_di', 'minus_di' series
    """
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # +DM and -DM (Directional Movement)
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)

    # Smoothed TR, +DM, -DM using Wilder's smoothing (EMA with alpha = 1/period)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    smooth_plus_dm = plus_dm.ewm(alpha=1/period, adjust=False).mean()
    smooth_minus_dm = minus_dm.ewm(alpha=1/period, adjust=False).mean()

    # +DI and -DI
    plus_di = 100 * smooth_plus_dm / atr
    minus_di = 100 * smooth_minus_dm / atr

    # DX (Directional Index)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

    # ADX is smoothed DX
    adx_series = dx.ewm(alpha=1/period, adjust=False).mean()

    return {
        "adx": adx_series,
        "plus_di": plus_di,
        "minus_di": minus_di,
    }


def sma_slope(sma_series: pd.Series, lookback: int = 20) -> float:
    """
    Calculate the slope of an SMA over a lookback period.

    Returns:
        Slope value (positive = rising, negative = falling)
        Normalized as percentage change over the lookback period
    """
    if len(sma_series.dropna()) < lookback:
        return 0.0

    recent = sma_series.dropna().iloc[-lookback:]
    start_val = recent.iloc[0]
    end_val = recent.iloc[-1]

    if start_val == 0:
        return 0.0

    # Return as percentage change over the period
    return ((end_val - start_val) / start_val) * 100


def detect_swing_highs_lows(close: pd.Series, lookback: int = 2) -> Dict[str, Any]:
    """
    Detect swing highs and lows in price series.

    A swing high is a high that is higher than the surrounding bars.
    A swing low is a low that is lower than the surrounding bars.

    Args:
        close: Price series
        lookback: Number of bars on each side to compare (default 2)

    Returns:
        Dict with recent swing highs/lows and their indices
    """
    if len(close) < lookback * 2 + 1:
        return {"swing_highs": [], "swing_lows": []}

    swing_highs = []
    swing_lows = []

    # Need lookback bars on each side, so start from lookback and end at -lookback
    for i in range(lookback, len(close) - lookback):
        # Check for swing high
        is_high = True
        is_low = True

        for j in range(1, lookback + 1):
            if close.iloc[i] <= close.iloc[i - j] or close.iloc[i] <= close.iloc[i + j]:
                is_high = False
            if close.iloc[i] >= close.iloc[i - j] or close.iloc[i] >= close.iloc[i + j]:
                is_low = False

        if is_high:
            swing_highs.append({
                "index": i,
                "date": close.index[i],
                "price": float(close.iloc[i])
            })
        if is_low:
            swing_lows.append({
                "index": i,
                "date": close.index[i],
                "price": float(close.iloc[i])
            })

    return {
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
    }


def detect_divergence(
    close: pd.Series,
    indicator: pd.Series,
    lookback: int = 30
) -> Dict[str, Any]:
    """
    Detect price/indicator divergence using swing highs and lows.

    Bearish divergence: Price higher high + Indicator lower high
    Bullish divergence: Price lower low + Indicator higher low

    Args:
        close: Price series
        indicator: Indicator series (RSI, MACD, etc.)
        lookback: Number of bars to analyze

    Returns:
        Dict with divergence type and details
    """
    if len(close) < lookback or len(indicator) < lookback:
        return {"divergence": None, "type": None}

    # Get recent data
    recent_close = close.iloc[-lookback:]
    recent_indicator = indicator.iloc[-lookback:]

    # Detect swings in both
    price_swings = detect_swing_highs_lows(recent_close, lookback=2)
    indicator_swings = detect_swing_highs_lows(recent_indicator, lookback=2)

    # Check for bearish divergence (price higher high, indicator lower high)
    price_highs = price_swings["swing_highs"]
    indicator_highs = indicator_swings["swing_highs"]

    if len(price_highs) >= 2 and len(indicator_highs) >= 2:
        # Compare last two swing highs
        if (price_highs[-1]["price"] > price_highs[-2]["price"] and
            indicator_highs[-1]["price"] < indicator_highs[-2]["price"]):
            return {
                "divergence": "bearish",
                "type": "regular",
                "description": "Price making higher highs while indicator making lower highs",
                "price_high_1": price_highs[-2]["price"],
                "price_high_2": price_highs[-1]["price"],
                "indicator_high_1": indicator_highs[-2]["price"],
                "indicator_high_2": indicator_highs[-1]["price"],
            }

    # Check for bullish divergence (price lower low, indicator higher low)
    price_lows = price_swings["swing_lows"]
    indicator_lows = indicator_swings["swing_lows"]

    if len(price_lows) >= 2 and len(indicator_lows) >= 2:
        # Compare last two swing lows
        if (price_lows[-1]["price"] < price_lows[-2]["price"] and
            indicator_lows[-1]["price"] > indicator_lows[-2]["price"]):
            return {
                "divergence": "bullish",
                "type": "regular",
                "description": "Price making lower lows while indicator making higher lows",
                "price_low_1": price_lows[-2]["price"],
                "price_low_2": price_lows[-1]["price"],
                "indicator_low_1": indicator_lows[-2]["price"],
                "indicator_low_2": indicator_lows[-1]["price"],
            }

    return {"divergence": None, "type": None}


def up_down_volume_ratio(
    close: pd.Series,
    volume: pd.Series,
    lookback: int = 10
) -> Dict[str, Any]:
    """
    Calculate volume ratio on up days vs down days.

    This tells us if volume is higher on advancing days (bullish)
    or declining days (bearish).

    Args:
        close: Close price series
        volume: Volume series
        lookback: Number of days to analyze

    Returns:
        Dict with up_volume, down_volume, and ratio
    """
    if len(close) < lookback + 1 or len(volume) < lookback:
        return {"error": "insufficient data"}

    # Calculate daily returns
    returns = close.pct_change()

    # Get recent data
    recent_returns = returns.iloc[-lookback:]
    recent_volume = volume.iloc[-lookback:]

    # Separate up and down days
    up_mask = recent_returns > 0
    down_mask = recent_returns < 0

    up_volume = recent_volume[up_mask].sum() if up_mask.any() else 0
    down_volume = recent_volume[down_mask].sum() if down_mask.any() else 0
    up_days = up_mask.sum()
    down_days = down_mask.sum()

    # Average volume per up day vs per down day
    avg_up_vol = up_volume / up_days if up_days > 0 else 0
    avg_down_vol = down_volume / down_days if down_days > 0 else 0

    # Ratio of average up-day volume to average down-day volume
    if avg_down_vol > 0:
        vol_ratio = avg_up_vol / avg_down_vol
    else:
        vol_ratio = 2.0 if avg_up_vol > 0 else 1.0

    # Interpretation
    if vol_ratio > 1.3:
        interpretation = "strong_buying"  # Much more volume on up days
    elif vol_ratio > 1.1:
        interpretation = "buying"
    elif vol_ratio < 0.7:
        interpretation = "strong_selling"  # Much more volume on down days
    elif vol_ratio < 0.9:
        interpretation = "selling"
    else:
        interpretation = "neutral"

    return {
        "up_volume": float(up_volume),
        "down_volume": float(down_volume),
        "up_days": int(up_days),
        "down_days": int(down_days),
        "avg_up_vol": float(avg_up_vol),
        "avg_down_vol": float(avg_down_vol),
        "vol_ratio": float(vol_ratio),
        "interpretation": interpretation,
    }


def all_time_high(series: pd.Series) -> float:
    """Calculate all-time high from full history."""
    return float(series.dropna().max())


def pct_from_level(current: float, level: float) -> float:
    """Calculate percentage difference from a price level."""
    if level == 0:
        return 0.0
    return ((current - level) / level) * 100


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Calculate On-Balance Volume (OBV).
    OBV adds volume on up days and subtracts on down days.
    """
    direction = np.sign(close.diff())
    direction.iloc[0] = 0
    return (direction * volume).cumsum()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Returns:
        Dict with 'macd' line, 'signal' line, and 'histogram'
    """
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }


def histogram_slope(histogram: pd.Series, lookback: int = 3) -> str:
    """
    Determine if MACD histogram is rising, falling, or flat.

    Args:
        histogram: MACD histogram series
        lookback: number of bars to check

    Returns:
        "rising", "falling", or "flat"
    """
    recent = histogram.dropna().iloc[-lookback:]
    if len(recent) < 2:
        return "unknown"

    diff = recent.iloc[-1] - recent.iloc[0]
    threshold = abs(recent.mean()) * 0.1  # 10% of average as threshold

    if diff > threshold:
        return "rising"
    elif diff < -threshold:
        return "falling"
    return "flat"


def analyze_rsi_momentum(rsi_series: pd.Series, lookback: int = 5) -> Dict[str, Any]:
    """
    Analyze RSI trajectory to give actionable signals.

    Returns:
        Dict with:
        - current: current RSI value
        - previous: RSI value N bars ago
        - change: RSI change over lookback period
        - zone: "overbought", "oversold", or "neutral"
        - direction: "rising", "falling", or "flat"
        - signal: actionable signal like "WAIT - RSI falling from overbought"
    """
    recent = rsi_series.dropna().iloc[-lookback:]
    if len(recent) < 2:
        return {"error": "insufficient data"}

    current = float(recent.iloc[-1])
    previous = float(recent.iloc[0])
    change = current - previous

    # Determine zone
    if current > 70:
        zone = "overbought"
    elif current < 30:
        zone = "oversold"
    else:
        zone = "neutral"

    # Determine direction (with threshold to avoid noise)
    if change > 3:
        direction = "rising"
    elif change < -3:
        direction = "falling"
    else:
        direction = "flat"

    # Generate actionable signal
    signal = ""
    signal_type = "neutral"

    if zone == "overbought":
        if direction == "falling":
            signal = "WAIT - RSI falling from overbought, potential pullback"
            signal_type = "bearish"
        elif direction == "rising":
            signal = "CAUTION - RSI rising in overbought zone, extended"
            signal_type = "bearish"
        else:
            signal = "WATCH - RSI holding overbought, momentum may fade"
            signal_type = "neutral"
    elif zone == "oversold":
        if direction == "rising":
            signal = "BUY SIGNAL - RSI rising from oversold, recovery underway"
            signal_type = "bullish"
        elif direction == "falling":
            signal = "WAIT - RSI still falling in oversold, not yet bottomed"
            signal_type = "neutral"
        else:
            signal = "WATCH - RSI holding oversold, potential bounce setup"
            signal_type = "bullish"
    else:  # neutral zone
        if direction == "rising" and current > 50:
            signal = "BULLISH - RSI rising with positive momentum"
            signal_type = "bullish"
        elif direction == "falling" and current < 50:
            signal = "BEARISH - RSI falling with negative momentum"
            signal_type = "bearish"
        elif direction == "rising":
            signal = "IMPROVING - RSI turning up from low levels"
            signal_type = "bullish"
        elif direction == "falling":
            signal = "WEAKENING - RSI turning down from high levels"
            signal_type = "bearish"
        else:
            signal = "NEUTRAL - RSI flat, wait for direction"
            signal_type = "neutral"

    return {
        "current": current,
        "previous": previous,
        "change": change,
        "zone": zone,
        "direction": direction,
        "signal": signal,
        "signal_type": signal_type,
    }


def analyze_macd_momentum(macd_data: Dict[str, pd.Series], lookback: int = 5) -> Dict[str, Any]:
    """
    Analyze MACD trajectory to give actionable signals.

    Looks at:
    - MACD/Signal crossover timing (recent vs old)
    - Histogram expansion/contraction
    - Zero-line position

    Returns actionable trading signals.
    """
    macd_line = macd_data["macd"].dropna()
    signal_line = macd_data["signal"].dropna()
    histogram = macd_data["histogram"].dropna()

    if len(histogram) < lookback + 1:
        return {"error": "insufficient data"}

    current_macd = float(macd_line.iloc[-1])
    current_signal = float(signal_line.iloc[-1])
    current_hist = float(histogram.iloc[-1])
    prev_hist = float(histogram.iloc[-lookback])

    # Check for recent crossover (within last N bars)
    crossover_detected = False
    crossover_type = None
    bars_since_crossover = None

    for i in range(1, min(lookback + 1, len(macd_line))):
        prev_macd = macd_line.iloc[-(i+1)]
        prev_signal = signal_line.iloc[-(i+1)]
        curr_macd = macd_line.iloc[-i]
        curr_signal = signal_line.iloc[-i]

        # Bullish crossover: MACD crosses above signal
        if prev_macd <= prev_signal and curr_macd > curr_signal:
            crossover_detected = True
            crossover_type = "bullish"
            bars_since_crossover = i
            break
        # Bearish crossover: MACD crosses below signal
        elif prev_macd >= prev_signal and curr_macd < curr_signal:
            crossover_detected = True
            crossover_type = "bearish"
            bars_since_crossover = i
            break

    # Histogram analysis
    hist_change = current_hist - prev_hist
    if current_hist > 0:
        if hist_change > 0:
            histogram_status = "expanding_bullish"
        else:
            histogram_status = "contracting_bullish"
    else:
        if hist_change < 0:
            histogram_status = "expanding_bearish"
        else:
            histogram_status = "contracting_bearish"

    # Zero-line analysis
    above_zero = current_macd > 0

    # Generate actionable signal
    signal = ""
    signal_type = "neutral"

    if crossover_detected and bars_since_crossover <= 3:
        if crossover_type == "bullish":
            if above_zero:
                signal = "STRONG BUY - Fresh bullish crossover above zero line"
                signal_type = "bullish"
            else:
                signal = "BUY SIGNAL - Bullish crossover, momentum turning"
                signal_type = "bullish"
        else:
            if not above_zero:
                signal = "STRONG SELL - Fresh bearish crossover below zero line"
                signal_type = "bearish"
            else:
                signal = "SELL SIGNAL - Bearish crossover, momentum fading"
                signal_type = "bearish"
    elif histogram_status == "expanding_bullish":
        signal = "BULLISH - Histogram expanding, momentum building"
        signal_type = "bullish"
    elif histogram_status == "expanding_bearish":
        signal = "BEARISH - Histogram expanding downward, selling pressure"
        signal_type = "bearish"
    elif histogram_status == "contracting_bullish":
        signal = "CAUTION - Bullish momentum fading, watch for reversal"
        signal_type = "neutral"
    elif histogram_status == "contracting_bearish":
        signal = "IMPROVING - Bearish momentum fading, potential bottom"
        signal_type = "neutral"

    return {
        "macd": current_macd,
        "signal_line": current_signal,
        "histogram": current_hist,
        "histogram_change": hist_change,
        "histogram_status": histogram_status,
        "above_zero": above_zero,
        "crossover_detected": crossover_detected,
        "crossover_type": crossover_type,
        "bars_since_crossover": bars_since_crossover,
        "signal": signal,
        "signal_type": signal_type,
    }


def analyze_obv_momentum(close: pd.Series, obv_series: pd.Series, lookback: int = 10) -> Dict[str, Any]:
    """
    Analyze OBV trajectory and detect divergences.

    Divergences:
    - Bullish divergence: Price making lower lows, OBV making higher lows (accumulation)
    - Bearish divergence: Price making higher highs, OBV making lower highs (distribution)

    Returns actionable signals.
    """
    if len(close) < lookback + 5 or len(obv_series) < lookback + 5:
        return {"error": "insufficient data"}

    recent_close = close.iloc[-lookback:]
    recent_obv = obv_series.iloc[-lookback:]
    prev_close = close.iloc[-(lookback*2):-lookback]
    prev_obv = obv_series.iloc[-(lookback*2):-lookback]

    # Calculate trend direction
    current_obv = float(obv_series.iloc[-1])
    obv_change = float(recent_obv.iloc[-1] - recent_obv.iloc[0])
    price_change = float(recent_close.iloc[-1] - recent_close.iloc[0])

    # Determine OBV trend
    obv_sma = obv_series.rolling(20).mean()
    if len(obv_sma.dropna()) > 0:
        obv_vs_sma = "above" if current_obv > obv_sma.iloc[-1] else "below"
    else:
        obv_vs_sma = "unknown"

    # Check for divergence
    # Compare recent highs/lows of price vs OBV
    price_recent_high = recent_close.max()
    price_prev_high = prev_close.max() if len(prev_close) > 0 else price_recent_high
    obv_recent_high = recent_obv.max()
    obv_prev_high = prev_obv.max() if len(prev_obv) > 0 else obv_recent_high

    price_recent_low = recent_close.min()
    price_prev_low = prev_close.min() if len(prev_close) > 0 else price_recent_low
    obv_recent_low = recent_obv.min()
    obv_prev_low = prev_obv.min() if len(prev_obv) > 0 else obv_recent_low

    divergence = None
    # Bearish divergence: price higher high, OBV lower high
    if price_recent_high > price_prev_high and obv_recent_high < obv_prev_high:
        divergence = "bearish"
    # Bullish divergence: price lower low, OBV higher low
    elif price_recent_low < price_prev_low and obv_recent_low > obv_prev_low:
        divergence = "bullish"

    # Determine direction
    if obv_change > 0 and price_change > 0:
        direction = "confirming_uptrend"
    elif obv_change < 0 and price_change < 0:
        direction = "confirming_downtrend"
    elif obv_change > 0 and price_change <= 0:
        direction = "accumulation"
    elif obv_change < 0 and price_change >= 0:
        direction = "distribution"
    else:
        direction = "neutral"

    # Generate actionable signal
    signal = ""
    signal_type = "neutral"

    if divergence == "bullish":
        signal = "BULLISH DIVERGENCE - Smart money accumulating despite price drop"
        signal_type = "bullish"
    elif divergence == "bearish":
        signal = "BEARISH DIVERGENCE - Distribution despite price rise, caution"
        signal_type = "bearish"
    elif direction == "accumulation":
        signal = "ACCUMULATION - OBV rising while price flat/down, watch for breakout"
        signal_type = "bullish"
    elif direction == "distribution":
        signal = "DISTRIBUTION - OBV falling while price flat/up, watch for breakdown"
        signal_type = "bearish"
    elif direction == "confirming_uptrend":
        signal = "CONFIRMED UPTREND - Price and volume rising together"
        signal_type = "bullish"
    elif direction == "confirming_downtrend":
        signal = "CONFIRMED DOWNTREND - Price and volume falling together"
        signal_type = "bearish"
    else:
        signal = "NEUTRAL - No clear OBV signal"
        signal_type = "neutral"

    return {
        "current_obv": current_obv,
        "obv_change": obv_change,
        "obv_vs_sma": obv_vs_sma,
        "price_change": price_change,
        "direction": direction,
        "divergence": divergence,
        "signal": signal,
        "signal_type": signal_type,
    }


def volume_vs_average(volume: pd.Series, window: int = 20) -> Dict[str, Any]:
    """
    Compare current volume to its moving average.

    Returns:
        Dict with current_volume, avg_volume, volume_ratio, volume_signal
    """
    if volume is None or volume.empty:
        return {
            "current_volume": None,
            "avg_volume_20d": None,
            "volume_ratio": None,
            "volume_signal": "no data",
        }

    current = float(volume.iloc[-1])
    avg = float(volume.rolling(window=window).mean().iloc[-1])

    if avg == 0:
        ratio = 0
    else:
        ratio = current / avg

    # Classify volume
    if ratio > 1.5:
        signal = "high"
    elif ratio > 1.0:
        signal = "above avg"
    elif ratio > 0.5:
        signal = "below avg"
    else:
        signal = "low"

    return {
        "current_volume": current,
        "avg_volume_20d": avg,
        "volume_ratio": ratio,
        "volume_signal": signal,
    }


def classify_trend(close: pd.Series, sma20: float, sma50: float, sma200: float) -> str:
    """
    Classify trend based on moving average alignment and price position.

    Uptrend: Price > SMA20 > SMA50 > SMA200
    Downtrend: Price < SMA20 < SMA50 < SMA200
    Chop: Mixed signals
    """
    if sma20 is None or sma50 is None or sma200 is None:
        return "unknown"

    current = float(close.iloc[-1])

    # Strong uptrend: price and MAs in bullish alignment
    if current > sma20 > sma50 > sma200:
        return "uptrend"

    # Strong downtrend: price and MAs in bearish alignment
    if current < sma20 < sma50 < sma200:
        return "downtrend"

    # Check for weaker trends
    above_count = sum([current > sma20, current > sma50, current > sma200])
    ma_bullish = sma20 > sma50 > sma200
    ma_bearish = sma20 < sma50 < sma200

    if above_count >= 2 and ma_bullish:
        return "uptrend"
    if above_count <= 1 and ma_bearish:
        return "downtrend"

    return "chop"


def fetch_spot_and_futures(metal: str = "gold") -> Dict[str, Any]:
    """
    Fetch front-month futures price from Yahoo Finance.

    Note: Yahoo spot tickers (XAUUSD=X, XAGUSD=X) are no longer available.
    Use Gold-API for spot prices instead (handled in alpha_vantage_fetcher.py).

    Args:
        metal: "gold" or "silver"

    Returns:
        Dict with futures_price and futures_ticker
    """
    futures_ticker = "GC=F" if metal.lower() == "gold" else "SI=F"

    result = {
        "spot_price": None,  # Get from Gold-API instead
        "spot_source": None,
        "futures_price": None,
        "futures_ticker": futures_ticker,
    }

    # Get futures price only (spot tickers are broken on Yahoo)
    try:
        t = yf.Ticker(futures_ticker)
        hist = t.history(period="1d")
        if not hist.empty:
            result["futures_price"] = float(hist["Close"].iloc[-1])
    except Exception:
        pass

    return result


def compute_indicators(yahoo_ticker: str, period: str = "1y", spot_price: float = None) -> Dict[str, Any]:
    """Fetch history and compute common indicators. Returns a dict.

    Tries local CSV cache first (for Gold-API daily snapshots), then falls back to yfinance.
    For gold/silver, uses futures tickers (GC=F, SI=F) as Yahoo spot tickers no longer work.

    Keys returned:
        - last_close: most recent closing price from history
        - spot_price: live spot price (if provided)
        - futures_price: front-month futures price
        - sma20, sma50, sma200: Simple Moving Averages
        - ema20, ema50, ema200: Exponential Moving Averages
        - rsi14: 14-day RSI
        - ath: All-Time High
        - 52w_high, 52w_low: 52-week high and low
        - pct_from_ath: % below all-time high
        - pct_from_52w_high: % below 52-week high
        - pct_from_52w_low: % above 52-week low
        - trend: "uptrend", "downtrend", or "chop"
        - history: full DataFrame
    """
    # Map tickers to local cache symbols and futures tickers
    symbol_map = {
        "XAUUSD=X": "XAU",
        "XAGUSD=X": "XAG",
        "GC=F": "XAU",
        "SI=F": "XAG",
        "HG=F": "HG",  # Copper
    }
    # Yahoo spot tickers are broken, use futures instead
    futures_ticker_map = {
        "XAUUSD=X": "GC=F",
        "XAGUSD=X": "SI=F",
        "GC=F": "GC=F",
        "SI=F": "SI=F",
        "HG=F": "HG=F",  # Copper
    }
    symbol = symbol_map.get(yahoo_ticker)
    metal = "gold" if symbol == "XAU" else "silver" if symbol == "XAG" else "copper" if symbol == "HG" else None

    # Get the working futures ticker for yfinance fallback
    yf_ticker = futures_ticker_map.get(yahoo_ticker, yahoo_ticker)

    # Try local cache first
    df = None
    if symbol:
        local = load_history(symbol)
        if local is not None and not local.empty and len(local) >= 50:
            # Only use local cache if we have enough data for indicators
            df = local

    # Fallback to Yahoo Finance (always use futures tickers for metals)
    if df is None or df.empty:
        df = fetch_history(yf_ticker, period=period)

    # If still no data, try without local cache preference
    if df is None or df.empty:
        df = fetch_history(yahoo_ticker, period=period)

    if df is None or df.empty:
        return {"error": "no history"}

    close = df["Close"].dropna()
    out = {}

    # Basic price
    out["last_close"] = float(close.iloc[-1])

    # Spot and futures prices
    if metal:
        spot_fut = fetch_spot_and_futures(metal)
        out["spot_price"] = spot_price if spot_price else spot_fut["spot_price"]
        out["futures_price"] = spot_fut["futures_price"]
        out["futures_ticker"] = spot_fut["futures_ticker"]
    else:
        out["spot_price"] = spot_price
        out["futures_price"] = None
        out["futures_ticker"] = None

    # Moving averages - SMA
    out["sma20"] = float(sma(close, 20).iloc[-1]) if len(close) >= 20 else None
    out["sma50"] = float(sma(close, 50).iloc[-1]) if len(close) >= 50 else None
    out["sma200"] = float(sma(close, 200).iloc[-1]) if len(close) >= 200 else None

    # Moving averages - EMA
    out["ema20"] = float(ema(close, 20).iloc[-1]) if len(close) >= 20 else None
    out["ema50"] = float(ema(close, 50).iloc[-1]) if len(close) >= 50 else None
    out["ema200"] = float(ema(close, 200).iloc[-1]) if len(close) >= 200 else None

    # RSI
    r = rsi(close, 14)
    out["rsi14"] = float(r.iloc[-1]) if len(r.dropna()) else None

    # RSI Momentum Analysis
    if len(r.dropna()) >= 5:
        rsi_momentum = analyze_rsi_momentum(r)
        out["rsi_momentum"] = rsi_momentum
    else:
        out["rsi_momentum"] = {"error": "insufficient data"}

    # All-time high
    out["ath"] = all_time_high(close)

    # 52-week high/low
    hl = high_low_52w(close)
    out.update(hl)

    # Percentage from key levels (use spot_price if available, else last_close)
    ref_price = out["spot_price"] if out["spot_price"] else out["last_close"]
    out["pct_from_ath"] = pct_from_level(ref_price, out["ath"])
    out["pct_from_52w_high"] = pct_from_level(ref_price, out["52w_high"])
    out["pct_from_52w_low"] = pct_from_level(ref_price, out["52w_low"])

    # Trend classification
    out["trend"] = classify_trend(close, out["sma20"], out["sma50"], out["sma200"])

    # === MOMENTUM INDICATORS ===
    volume = df["Volume"] if "Volume" in df.columns else None

    # OBV (On-Balance Volume)
    if volume is not None and not volume.empty:
        obv_series = obv(close, volume)
        out["obv"] = float(obv_series.iloc[-1])
        # OBV trend: compare current to 20-day SMA of OBV
        obv_sma_series = sma(obv_series, 20)
        if len(obv_sma_series.dropna()) > 0:
            out["obv_sma20"] = float(obv_sma_series.iloc[-1])
            out["obv_trend"] = "bullish" if out["obv"] > out["obv_sma20"] else "bearish"
        else:
            out["obv_sma20"] = None
            out["obv_trend"] = "unknown"

        # OBV Momentum Analysis (divergence detection)
        obv_momentum = analyze_obv_momentum(close, obv_series)
        out["obv_momentum"] = obv_momentum
    else:
        out["obv"] = None
        out["obv_sma20"] = None
        out["obv_trend"] = "no volume data"
        out["obv_momentum"] = {"error": "no volume data"}

    # MACD
    if len(close) >= 26:
        macd_data = macd(close)
        out["macd_line"] = float(macd_data["macd"].iloc[-1])
        out["macd_signal"] = float(macd_data["signal"].iloc[-1])
        out["macd_histogram"] = float(macd_data["histogram"].iloc[-1])
        out["macd_histogram_slope"] = histogram_slope(macd_data["histogram"])
        # MACD crossover signal
        if out["macd_line"] > out["macd_signal"]:
            out["macd_crossover"] = "bullish"
        else:
            out["macd_crossover"] = "bearish"

        # MACD Momentum Analysis
        macd_momentum = analyze_macd_momentum(macd_data)
        out["macd_momentum"] = macd_momentum
    else:
        out["macd_line"] = None
        out["macd_signal"] = None
        out["macd_histogram"] = None
        out["macd_histogram_slope"] = "unknown"
        out["macd_crossover"] = "unknown"
        out["macd_momentum"] = {"error": "insufficient data"}

    # Volume vs 20-day average
    if volume is not None:
        vol_analysis = volume_vs_average(volume, 20)
        out["current_volume"] = vol_analysis["current_volume"]
        out["avg_volume_20d"] = vol_analysis["avg_volume_20d"]
        out["volume_ratio"] = vol_analysis["volume_ratio"]
        out["volume_signal"] = vol_analysis["volume_signal"]
    else:
        out["current_volume"] = None
        out["avg_volume_20d"] = None
        out["volume_ratio"] = None
        out["volume_signal"] = "no data"

    # === NEW PROFESSIONAL INDICATORS ===

    # ADX (Average Directional Index) for trend strength
    if "High" in df.columns and "Low" in df.columns and len(close) >= 28:
        adx_data = adx(df["High"], df["Low"], close, period=14)
        out["adx"] = float(adx_data["adx"].iloc[-1])
        out["plus_di"] = float(adx_data["plus_di"].iloc[-1])
        out["minus_di"] = float(adx_data["minus_di"].iloc[-1])
        out["adx_series"] = adx_data["adx"]
    else:
        out["adx"] = None
        out["plus_di"] = None
        out["minus_di"] = None
        out["adx_series"] = None

    # SMA50 slope over 20 days
    if len(close) >= 70:  # Need 50 for SMA + 20 for slope
        sma50_series = sma(close, 50)
        out["sma50_slope"] = sma_slope(sma50_series, lookback=20)
        out["sma50_series"] = sma50_series
    else:
        out["sma50_slope"] = 0.0
        out["sma50_series"] = None

    # RSI divergence detection
    if len(close) >= 30:
        rsi_series = rsi(close, 14)
        rsi_div = detect_divergence(close, rsi_series, lookback=30)
        out["rsi_divergence"] = rsi_div
    else:
        out["rsi_divergence"] = {"divergence": None, "type": None}

    # Up/Down volume ratio
    if volume is not None and not volume.empty and len(close) >= 11:
        ud_vol = up_down_volume_ratio(close, volume, lookback=10)
        out["up_down_volume"] = ud_vol
    else:
        out["up_down_volume"] = {"error": "insufficient data"}

    # OBV trend direction (for participation analysis)
    if volume is not None and not volume.empty and len(close) >= 20:
        obv_series = obv(close, volume)
        obv_sma_20 = sma(obv_series, 20)

        # OBV slope over 10 days
        if len(obv_series) >= 10:
            obv_recent = obv_series.iloc[-10:]
            obv_start = obv_recent.iloc[0]
            obv_end = obv_recent.iloc[-1]
            if obv_start != 0:
                out["obv_slope"] = ((obv_end - obv_start) / abs(obv_start)) * 100
            else:
                out["obv_slope"] = 0.0
        else:
            out["obv_slope"] = 0.0

        # Is OBV above or below its 20-day SMA?
        if len(obv_sma_20.dropna()) > 0:
            out["obv_vs_sma"] = "above" if obv_series.iloc[-1] > obv_sma_20.iloc[-1] else "below"
        else:
            out["obv_vs_sma"] = "unknown"
    else:
        out["obv_slope"] = 0.0
        out["obv_vs_sma"] = "unknown"

    out["history"] = df
    return out


def compute_indicators_from_df(df: pd.DataFrame, spot_price: float = None) -> Dict[str, Any]:
    """
    Compute indicators from a provided DataFrame (for backtesting).

    This is identical to compute_indicators() but accepts a DataFrame directly
    instead of fetching from yfinance. Used for historical backtesting where
    we slice the DataFrame to a specific date.

    Args:
        df: DataFrame with OHLCV data (must have Close, and optionally High, Low, Volume)
        spot_price: Optional spot price override

    Returns:
        Dict with all computed indicators (same structure as compute_indicators)
    """
    if df is None or df.empty:
        return {"error": "no history"}

    close = df["Close"].dropna()
    if len(close) < 50:
        return {"error": "insufficient data (need at least 50 bars)"}

    out = {}

    # Basic price
    out["last_close"] = float(close.iloc[-1])
    out["spot_price"] = spot_price if spot_price else out["last_close"]
    out["futures_price"] = None  # Not applicable for backtest
    out["futures_ticker"] = None

    # Moving averages - SMA
    out["sma20"] = float(sma(close, 20).iloc[-1]) if len(close) >= 20 else None
    out["sma50"] = float(sma(close, 50).iloc[-1]) if len(close) >= 50 else None
    out["sma200"] = float(sma(close, 200).iloc[-1]) if len(close) >= 200 else None

    # Moving averages - EMA
    out["ema20"] = float(ema(close, 20).iloc[-1]) if len(close) >= 20 else None
    out["ema50"] = float(ema(close, 50).iloc[-1]) if len(close) >= 50 else None
    out["ema200"] = float(ema(close, 200).iloc[-1]) if len(close) >= 200 else None

    # RSI
    r = rsi(close, 14)
    out["rsi14"] = float(r.iloc[-1]) if len(r.dropna()) else None

    # RSI Momentum Analysis
    if len(r.dropna()) >= 5:
        rsi_momentum = analyze_rsi_momentum(r)
        out["rsi_momentum"] = rsi_momentum
    else:
        out["rsi_momentum"] = {"error": "insufficient data"}

    # All-time high (within provided data)
    out["ath"] = all_time_high(close)

    # 52-week high/low
    hl = high_low_52w(close)
    out.update(hl)

    # Percentage from key levels
    ref_price = out["spot_price"] if out["spot_price"] else out["last_close"]
    out["pct_from_ath"] = pct_from_level(ref_price, out["ath"])
    out["pct_from_52w_high"] = pct_from_level(ref_price, out["52w_high"])
    out["pct_from_52w_low"] = pct_from_level(ref_price, out["52w_low"])

    # Trend classification
    out["trend"] = classify_trend(close, out["sma20"], out["sma50"], out["sma200"])

    # === MOMENTUM INDICATORS ===
    volume = df["Volume"] if "Volume" in df.columns else None

    # OBV (On-Balance Volume)
    if volume is not None and not volume.empty:
        obv_series = obv(close, volume)
        out["obv"] = float(obv_series.iloc[-1])
        obv_sma_series = sma(obv_series, 20)
        if len(obv_sma_series.dropna()) > 0:
            out["obv_sma20"] = float(obv_sma_series.iloc[-1])
            out["obv_trend"] = "bullish" if out["obv"] > out["obv_sma20"] else "bearish"
        else:
            out["obv_sma20"] = None
            out["obv_trend"] = "unknown"
        obv_momentum = analyze_obv_momentum(close, obv_series)
        out["obv_momentum"] = obv_momentum
    else:
        out["obv"] = None
        out["obv_sma20"] = None
        out["obv_trend"] = "no volume data"
        out["obv_momentum"] = {"error": "no volume data"}

    # MACD
    if len(close) >= 26:
        macd_data = macd(close)
        out["macd_line"] = float(macd_data["macd"].iloc[-1])
        out["macd_signal"] = float(macd_data["signal"].iloc[-1])
        out["macd_histogram"] = float(macd_data["histogram"].iloc[-1])
        out["macd_histogram_slope"] = histogram_slope(macd_data["histogram"])
        out["macd_crossover"] = "bullish" if out["macd_line"] > out["macd_signal"] else "bearish"
        macd_momentum = analyze_macd_momentum(macd_data)
        out["macd_momentum"] = macd_momentum
    else:
        out["macd_line"] = None
        out["macd_signal"] = None
        out["macd_histogram"] = None
        out["macd_histogram_slope"] = "unknown"
        out["macd_crossover"] = "unknown"
        out["macd_momentum"] = {"error": "insufficient data"}

    # Volume vs 20-day average
    if volume is not None:
        vol_analysis = volume_vs_average(volume, 20)
        out["current_volume"] = vol_analysis["current_volume"]
        out["avg_volume_20d"] = vol_analysis["avg_volume_20d"]
        out["volume_ratio"] = vol_analysis["volume_ratio"]
        out["volume_signal"] = vol_analysis["volume_signal"]
    else:
        out["current_volume"] = None
        out["avg_volume_20d"] = None
        out["volume_ratio"] = None
        out["volume_signal"] = "no data"

    # === PROFESSIONAL INDICATORS (for 5-pillar analysis) ===

    # ADX (Average Directional Index) for trend strength
    if "High" in df.columns and "Low" in df.columns and len(close) >= 28:
        adx_data = adx(df["High"], df["Low"], close, period=14)
        out["adx"] = float(adx_data["adx"].iloc[-1])
        out["plus_di"] = float(adx_data["plus_di"].iloc[-1])
        out["minus_di"] = float(adx_data["minus_di"].iloc[-1])
        out["adx_series"] = adx_data["adx"]
    else:
        out["adx"] = None
        out["plus_di"] = None
        out["minus_di"] = None
        out["adx_series"] = None

    # SMA50 slope over 20 days
    if len(close) >= 70:
        sma50_series = sma(close, 50)
        out["sma50_slope"] = sma_slope(sma50_series, lookback=20)
        out["sma50_series"] = sma50_series
    else:
        out["sma50_slope"] = 0.0
        out["sma50_series"] = None

    # RSI divergence detection
    if len(close) >= 30:
        rsi_series = rsi(close, 14)
        rsi_div = detect_divergence(close, rsi_series, lookback=30)
        out["rsi_divergence"] = rsi_div
    else:
        out["rsi_divergence"] = {"divergence": None, "type": None}

    # Up/Down volume ratio
    if volume is not None and not volume.empty and len(close) >= 11:
        ud_vol = up_down_volume_ratio(close, volume, lookback=10)
        out["up_down_volume"] = ud_vol
    else:
        out["up_down_volume"] = {"error": "insufficient data"}

    # OBV trend direction (for participation analysis)
    if volume is not None and not volume.empty and len(close) >= 20:
        obv_series = obv(close, volume)
        obv_sma_20 = sma(obv_series, 20)

        if len(obv_series) >= 10:
            obv_recent = obv_series.iloc[-10:]
            obv_start = obv_recent.iloc[0]
            obv_end = obv_recent.iloc[-1]
            if obv_start != 0:
                out["obv_slope"] = ((obv_end - obv_start) / abs(obv_start)) * 100
            else:
                out["obv_slope"] = 0.0
        else:
            out["obv_slope"] = 0.0

        if len(obv_sma_20.dropna()) > 0:
            out["obv_vs_sma"] = "above" if obv_series.iloc[-1] > obv_sma_20.iloc[-1] else "below"
        else:
            out["obv_vs_sma"] = "unknown"
    else:
        out["obv_slope"] = 0.0
        out["obv_vs_sma"] = "unknown"

    out["history"] = df
    return out
