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
    # Map tickers to local cache symbols
    symbol_map = {
        "XAUUSD=X": "XAU",
        "XAGUSD=X": "XAG",
        "GC=F": "XAU",
        "SI=F": "XAG",
    }
    symbol = symbol_map.get(yahoo_ticker)
    metal = "gold" if symbol == "XAU" else "silver" if symbol == "XAG" else None

    # Try local cache first
    if symbol:
        local = load_history(symbol)
        if local is not None and not local.empty:
            df = local
        else:
            df = fetch_history(yahoo_ticker, period=period)
    else:
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
        obv_sma = sma(obv_series, 20)
        if len(obv_sma.dropna()) > 0:
            out["obv_sma20"] = float(obv_sma.iloc[-1])
            out["obv_trend"] = "bullish" if out["obv"] > out["obv_sma20"] else "bearish"
        else:
            out["obv_sma20"] = None
            out["obv_trend"] = "unknown"
    else:
        out["obv"] = None
        out["obv_sma20"] = None
        out["obv_trend"] = "no volume data"

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
    else:
        out["macd_line"] = None
        out["macd_signal"] = None
        out["macd_histogram"] = None
        out["macd_histogram_slope"] = "unknown"
        out["macd_crossover"] = "unknown"

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
