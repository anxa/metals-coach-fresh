"""
CFTC Commitment of Traders (COT) data fetcher for precious metals.

Fetches disaggregated futures COT data directly from CFTC and calculates:
- Commercial hedgers net position (Producers/Merchants + Swap Dealers)
- Managed money net position (trend followers/hedge funds)
- 3-year percentile rankings
- Week-over-week changes
"""
import requests
import zipfile
import io
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
COT_CACHE_FILE = DATA_DIR / "cot_cache.csv"


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def fetch_cot_year(year: int) -> Optional[pd.DataFrame]:
    """Fetch COT disaggregated data for a given year from CFTC."""
    url = f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return None

        z = zipfile.ZipFile(io.BytesIO(resp.content))
        for name in z.namelist():
            if name.endswith('.txt'):
                with z.open(name) as f:
                    return pd.read_csv(f, low_memory=False)
    except Exception as e:
        print(f"Error fetching COT data for {year}: {e}")
    return None


def fetch_cot_multi_year(years: list = None) -> pd.DataFrame:
    """Fetch and combine multiple years of COT data."""
    if years is None:
        current_year = datetime.now().year
        years = [current_year - 2, current_year - 1, current_year]

    dfs = []
    for year in years:
        df = fetch_cot_year(year)
        if df is not None:
            dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)


def get_metal_cot(df: pd.DataFrame, metal: str) -> pd.DataFrame:
    """Filter COT data for a specific metal (GOLD, SILVER, or COPPER)."""
    # Market names vary by metal - copper has a different format
    market_names = {
        "GOLD": "GOLD - COMMODITY EXCHANGE INC.",
        "SILVER": "SILVER - COMMODITY EXCHANGE INC.",
        "COPPER": "COPPER- #1 - COMMODITY EXCHANGE INC.",  # Note the dash and #1
    }
    market_name = market_names.get(metal.upper())
    if not market_name:
        return pd.DataFrame()
    metal_df = df[df['Market_and_Exchange_Names'] == market_name].copy()
    metal_df = metal_df.sort_values('Report_Date_as_YYYY-MM-DD')
    return metal_df


def calculate_net_positions(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate net positions for each category."""
    df = df.copy()

    # Commercial = Producers/Merchants + Swap Dealers
    # Note: CFTC has typo in column name (Swap__Positions_Short_All with double underscore)
    df['prod_merc_net'] = (
        df['Prod_Merc_Positions_Long_All'].fillna(0) -
        df['Prod_Merc_Positions_Short_All'].fillna(0)
    )

    df['swap_net'] = (
        df['Swap_Positions_Long_All'].fillna(0) -
        df['Swap__Positions_Short_All'].fillna(0)
    )

    # Total commercial (hedgers)
    df['commercial_net'] = df['prod_merc_net'] + df['swap_net']

    # Managed Money (speculators/trend followers)
    df['managed_money_net'] = (
        df['M_Money_Positions_Long_All'].fillna(0) -
        df['M_Money_Positions_Short_All'].fillna(0)
    )

    # Other reportables
    df['other_net'] = (
        df['Other_Rept_Positions_Long_All'].fillna(0) -
        df['Other_Rept_Positions_Short_All'].fillna(0)
    )

    return df


def calculate_percentile(series: pd.Series, value: float) -> float:
    """Calculate percentile rank of a value within a series."""
    return (series <= value).sum() / len(series) * 100


def analyze_cot(metal: str = "GOLD", years: list = None) -> Dict[str, Any]:
    """
    Fetch and analyze COT data for a metal.

    Args:
        metal: "GOLD", "SILVER", or "COPPER"
        years: List of years to fetch (default: last 3 years)

    Returns:
        Dict with COT analysis including:
        - report_date: Date of latest COT report
        - commercial_net: Net position of commercial hedgers
        - commercial_wow: Week-over-week change
        - commercial_percentile: 3-year percentile ranking
        - managed_money_net: Net position of managed money
        - managed_money_wow: Week-over-week change
        - managed_money_percentile: 3-year percentile ranking
        - open_interest: Total open interest
    """
    # Fetch data
    all_data = fetch_cot_multi_year(years)
    if all_data.empty:
        return {"error": "Failed to fetch COT data"}

    # Filter to metal
    metal_df = get_metal_cot(all_data, metal)
    if metal_df.empty:
        return {"error": f"No COT data found for {metal}"}

    # Calculate net positions
    metal_df = calculate_net_positions(metal_df)

    # Get latest and previous week
    latest = metal_df.iloc[-1]
    prev = metal_df.iloc[-2] if len(metal_df) > 1 else latest

    # Week-over-week changes
    comm_wow = int(latest['commercial_net'] - prev['commercial_net'])
    mm_wow = int(latest['managed_money_net'] - prev['managed_money_net'])

    # Percentile rankings (where does current value rank in history)
    comm_pct = calculate_percentile(metal_df['commercial_net'], latest['commercial_net'])
    mm_pct = calculate_percentile(metal_df['managed_money_net'], latest['managed_money_net'])

    return {
        "report_date": latest['Report_Date_as_YYYY-MM-DD'],
        "commercial_net": int(latest['commercial_net']),
        "commercial_wow": comm_wow,
        "commercial_percentile": round(comm_pct, 1),
        "managed_money_net": int(latest['managed_money_net']),
        "managed_money_wow": mm_wow,
        "managed_money_percentile": round(mm_pct, 1),
        "open_interest": int(latest['Open_Interest_All']),
        "prod_merc_net": int(latest['prod_merc_net']),
        "swap_net": int(latest['swap_net']),
        "other_net": int(latest['other_net']),
    }


def get_cot_summary(metal: str = "GOLD") -> Dict[str, Any]:
    """
    Get a summary interpretation of COT data.

    Returns dict with raw data plus interpretation signals.
    """
    cot = analyze_cot(metal)
    if "error" in cot:
        return cot

    # Add interpretation
    # Commercial hedgers: When they're very short (low percentile),
    # it often means price is high and may be due for correction
    # When they're less short (high percentile), price may be low
    if cot['commercial_percentile'] > 80:
        cot['commercial_signal'] = 'bullish'
    elif cot['commercial_percentile'] < 20:
        cot['commercial_signal'] = 'bearish'
    else:
        cot['commercial_signal'] = 'neutral'

    # Managed money: Extreme positioning can indicate crowded trades
    # Very high = potentially crowded long, very low = potentially crowded short
    if cot['managed_money_percentile'] > 80:
        cot['managed_money_signal'] = 'extreme_long'
    elif cot['managed_money_percentile'] < 20:
        cot['managed_money_signal'] = 'extreme_short'
    else:
        cot['managed_money_signal'] = 'neutral'

    # Week-over-week momentum
    if cot['managed_money_wow'] > 10000:
        cot['mm_momentum'] = 'strong_buying'
    elif cot['managed_money_wow'] > 0:
        cot['mm_momentum'] = 'buying'
    elif cot['managed_money_wow'] > -10000:
        cot['mm_momentum'] = 'selling'
    else:
        cot['mm_momentum'] = 'strong_selling'

    return cot


if __name__ == "__main__":
    print("=== GOLD COT Analysis ===")
    gold = get_cot_summary("GOLD")
    if "error" not in gold:
        print(f"Report Date: {gold['report_date']}")
        print(f"\nCommercial Hedgers:")
        print(f"  Net Position:  {gold['commercial_net']:>12,}")
        print(f"  WoW Change:    {gold['commercial_wow']:>+12,}")
        print(f"  Percentile:    {gold['commercial_percentile']:>11.1f}%")
        print(f"  Signal:        {gold['commercial_signal']}")
        print(f"\nManaged Money:")
        print(f"  Net Position:  {gold['managed_money_net']:>12,}")
        print(f"  WoW Change:    {gold['managed_money_wow']:>+12,}")
        print(f"  Percentile:    {gold['managed_money_percentile']:>11.1f}%")
        print(f"  Signal:        {gold['managed_money_signal']}")
        print(f"  Momentum:      {gold['mm_momentum']}")
        print(f"\nOpen Interest:   {gold['open_interest']:>12,}")
    else:
        print(gold)

    print("\n" + "=" * 40)
    print("=== SILVER COT Analysis ===")
    silver = get_cot_summary("SILVER")
    if "error" not in silver:
        print(f"Report Date: {silver['report_date']}")
        print(f"\nCommercial Hedgers:")
        print(f"  Net Position:  {silver['commercial_net']:>12,}")
        print(f"  WoW Change:    {silver['commercial_wow']:>+12,}")
        print(f"  Percentile:    {silver['commercial_percentile']:>11.1f}%")
        print(f"  Signal:        {silver['commercial_signal']}")
        print(f"\nManaged Money:")
        print(f"  Net Position:  {silver['managed_money_net']:>12,}")
        print(f"  WoW Change:    {silver['managed_money_wow']:>+12,}")
        print(f"  Percentile:    {silver['managed_money_percentile']:>11.1f}%")
        print(f"  Signal:        {silver['managed_money_signal']}")
        print(f"  Momentum:      {silver['mm_momentum']}")
        print(f"\nOpen Interest:   {silver['open_interest']:>12,}")
    else:
        print(silver)

    print("\n" + "=" * 40)
    print("=== COPPER COT Analysis ===")
    copper = get_cot_summary("COPPER")
    if "error" not in copper:
        print(f"Report Date: {copper['report_date']}")
        print(f"\nCommercial Hedgers:")
        print(f"  Net Position:  {copper['commercial_net']:>12,}")
        print(f"  WoW Change:    {copper['commercial_wow']:>+12,}")
        print(f"  Percentile:    {copper['commercial_percentile']:>11.1f}%")
        print(f"  Signal:        {copper['commercial_signal']}")
        print(f"\nManaged Money:")
        print(f"  Net Position:  {copper['managed_money_net']:>12,}")
        print(f"  WoW Change:    {copper['managed_money_wow']:>+12,}")
        print(f"  Percentile:    {copper['managed_money_percentile']:>11.1f}%")
        print(f"  Signal:        {copper['managed_money_signal']}")
        print(f"  Momentum:      {copper['mm_momentum']}")
        print(f"\nOpen Interest:   {copper['open_interest']:>12,}")
    else:
        print(copper)
