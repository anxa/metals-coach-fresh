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

    out["history"] = df
    return out
