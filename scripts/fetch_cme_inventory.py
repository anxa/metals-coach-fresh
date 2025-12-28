#!/usr/bin/env python3
"""
CME Metals Inventory Fetcher

Downloads and parses CME warehouse inventory reports for:
- Copper: https://www.cmegroup.com/delivery_reports/Copper_Stocks.xls
- Platinum/Palladium: https://www.cmegroup.com/delivery_reports/PA-PL_Stck_Rprt.xls

Appends parsed data to data/cme_inventory.csv with per-warehouse granularity.
Includes GRAND_TOTAL row for each metal for easy lookups.

Usage:
    python scripts/fetch_cme_inventory.py

Scheduled via GitHub Actions daily after CME publishes (~5pm ET).
"""
import pandas as pd
import requests
import xlrd
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# URLs for CME delivery reports
CME_URLS = {
    "copper": "https://www.cmegroup.com/delivery_reports/Copper_Stocks.xls",
    "platinum_palladium": "https://www.cmegroup.com/delivery_reports/PA-PL_Stck_Rprt.xls",
}

# Path to inventory CSV
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INVENTORY_CSV = DATA_DIR / "cme_inventory.csv"

# CSV columns
INVENTORY_COLUMNS = [
    "date",           # Activity date (canonical date for deduplication)
    "metal",          # copper, platinum, palladium
    "warehouse",      # BALTIMORE, DETROIT, etc. or GRAND_TOTAL
    "registered",     # Registered (warranted) - available for delivery
    "eligible",       # Eligible (non-warranted) - in warehouse but not warranted
    "total",          # Total for this warehouse
    "received",       # Metal received
    "withdrawn",      # Metal withdrawn
    "net_change",     # Net change
    "report_date",    # Date on the CME report
    "activity_date",  # Activity date from CME report
    "fetched_at",     # When we fetched this data
]


def download_xls(url: str, timeout: int = 30) -> Optional[bytes]:
    """Download XLS file from CME with proper headers."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/vnd.ms-excel,*/*",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as e:
        print(f"Failed to download {url}: {e}")
        return None


def parse_date_from_text(text: str) -> Optional[str]:
    """Extract date from text like 'Report Date: 12/27/2024'."""
    match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', str(text))
    if match:
        try:
            dt = datetime.strptime(match.group(1), "%m/%d/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_number(value) -> Optional[int]:
    """Parse number from cell, handling various formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return int(value)
    try:
        cleaned = str(value).replace(",", "").strip()
        if cleaned == "" or cleaned.lower() == "nan":
            return None
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


def clean_warehouse_name(name: str) -> str:
    """Clean and normalize warehouse name."""
    name = str(name).strip().upper()
    # Remove any special characters except spaces and alphanumerics
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name


def parse_copper_xls(content: bytes) -> List[Dict]:
    """
    Parse Copper Stocks XLS file.

    Returns list of dicts, one per warehouse (including GRAND_TOTAL).
    """
    records = []

    try:
        workbook = xlrd.open_workbook(file_contents=content)
        sheet = workbook.sheet_by_index(0)

        # Find dates (usually in rows 6-7)
        report_date = None
        activity_date = None

        for row_idx in range(min(15, sheet.nrows)):
            row_text = " ".join(str(sheet.cell_value(row_idx, col))
                               for col in range(sheet.ncols))

            if "Report Date:" in row_text and not report_date:
                report_date = parse_date_from_text(row_text)
            if "Activity Date:" in row_text and not activity_date:
                activity_date = parse_date_from_text(row_text)

        if not activity_date:
            print("Could not find activity date in copper XLS")
            return []

        # Find the header row (contains "DELIVERY POINT" or "PREV TOTAL")
        header_row = None
        for row_idx in range(min(20, sheet.nrows)):
            row_text = " ".join(str(sheet.cell_value(row_idx, col))
                               for col in range(sheet.ncols)).upper()
            if "DELIVERY POINT" in row_text or "PREV TOTAL" in row_text:
                header_row = row_idx
                break

        if header_row is None:
            print("Could not find header row in copper XLS")
            return []

        # Parse warehouse data
        # Structure: Each warehouse has location name row, then Registered/Eligible/Total rows
        current_warehouse = None
        warehouse_data = {}

        for row_idx in range(header_row + 1, sheet.nrows):
            first_cell = str(sheet.cell_value(row_idx, 0)).strip()

            # Skip empty rows
            if not first_cell or first_cell.lower() == 'nan':
                continue

            # Skip disclaimer rows at the bottom
            if "information in this report" in first_cell.lower():
                break
            if "disclaimer" in first_cell.lower():
                break
            if "questions regarding" in first_cell.lower():
                break

            first_cell_upper = first_cell.upper()

            # Check if this is a warehouse name (location header)
            # Warehouse names are typically all caps, single words or city names
            if first_cell_upper in ["BALTIMORE", "DETROIT", "EL PASO", "NEW ORLEANS",
                                     "CHICAGO", "ST LOUIS", "TUCSON", "GRAND TOTAL",
                                     "NEW YORK", "LOS ANGELES", "SAN FRANCISCO"]:
                current_warehouse = clean_warehouse_name(first_cell)
                warehouse_data[current_warehouse] = {
                    "registered": None,
                    "eligible": None,
                    "total": None,
                    "received": None,
                    "withdrawn": None,
                    "net_change": None,
                }
                continue

            # Check if this is a data row (Registered/Eligible/Total)
            if current_warehouse and ("registered" in first_cell.lower() or
                                       "eligible" in first_cell.lower() or
                                       first_cell.lower() == "total"):

                # Column mapping (0-indexed):
                # 0: Label, 1: empty?, 2: PREV TOTAL, 3: RECEIVED, 4: WITHDRAWN,
                # 5: NET CHANGE, 6: ADJUSTMENT, 7: TOTAL TODAY

                # Try to find the right columns
                total_today = parse_number(sheet.cell_value(row_idx, 7) if sheet.ncols > 7
                                          else sheet.cell_value(row_idx, sheet.ncols - 1))
                received = parse_number(sheet.cell_value(row_idx, 3) if sheet.ncols > 3 else None)
                withdrawn = parse_number(sheet.cell_value(row_idx, 4) if sheet.ncols > 4 else None)
                net_change = parse_number(sheet.cell_value(row_idx, 5) if sheet.ncols > 5 else None)

                if "registered" in first_cell.lower():
                    warehouse_data[current_warehouse]["registered"] = total_today
                    warehouse_data[current_warehouse]["received"] = received
                    warehouse_data[current_warehouse]["withdrawn"] = withdrawn
                    warehouse_data[current_warehouse]["net_change"] = net_change
                elif "eligible" in first_cell.lower():
                    warehouse_data[current_warehouse]["eligible"] = total_today
                elif first_cell.lower() == "total":
                    warehouse_data[current_warehouse]["total"] = total_today

        # Convert to records
        fetched_at = datetime.now().isoformat()

        for warehouse, data in warehouse_data.items():
            records.append({
                "date": activity_date,
                "metal": "copper",
                "warehouse": warehouse,
                "registered": data["registered"],
                "eligible": data["eligible"],
                "total": data["total"],
                "received": data["received"],
                "withdrawn": data["withdrawn"],
                "net_change": data["net_change"],
                "report_date": report_date,
                "activity_date": activity_date,
                "fetched_at": fetched_at,
            })

        return records

    except Exception as e:
        print(f"Error parsing copper XLS: {e}")
        import traceback
        traceback.print_exc()
        return []


def parse_platinum_palladium_xls(content: bytes) -> List[Dict]:
    """
    Parse PA-PL Stock Report XLS file.

    Returns list of dicts for both platinum and palladium.
    """
    records = []

    try:
        workbook = xlrd.open_workbook(file_contents=content)
        sheet = workbook.sheet_by_index(0)

        # Find dates
        report_date = None
        activity_date = None

        for row_idx in range(min(20, sheet.nrows)):
            row_text = " ".join(str(sheet.cell_value(row_idx, col))
                               for col in range(sheet.ncols))

            if "Report Date:" in row_text and not report_date:
                report_date = parse_date_from_text(row_text)
            if "Activity Date:" in row_text and not activity_date:
                activity_date = parse_date_from_text(row_text)

        if not activity_date:
            print("Could not find activity date in platinum/palladium XLS")
            return []

        fetched_at = datetime.now().isoformat()

        # Find sections for each metal
        for metal in ["palladium", "platinum"]:
            metal_upper = metal.upper()

            # Find the metal section header
            metal_start = None
            for row_idx in range(sheet.nrows):
                cell_value = str(sheet.cell_value(row_idx, 0)).strip().upper()
                if metal_upper in cell_value:
                    metal_start = row_idx
                    break

            if metal_start is None:
                print(f"Could not find {metal} section")
                continue

            # Parse similar to copper, but only until next metal section or end
            current_warehouse = None
            warehouse_data = {}

            for row_idx in range(metal_start + 1, sheet.nrows):
                first_cell = str(sheet.cell_value(row_idx, 0)).strip()

                # Stop if we hit another metal section
                if first_cell.upper() in ["PALLADIUM", "PLATINUM"] and first_cell.upper() != metal_upper:
                    break

                # Skip empty rows
                if not first_cell or first_cell.lower() == 'nan':
                    continue

                # Skip disclaimer rows
                if "information in this report" in first_cell.lower():
                    break

                first_cell_upper = first_cell.upper()

                # Check if this is a warehouse/depository name
                if first_cell_upper in ["BRINKS", "DELAWARE DEPOSITORY", "HSBC", "JP MORGAN",
                                         "MALCA AMIT", "LOOMIS", "GRAND TOTAL", "TOTAL",
                                         "NEW YORK", "DELAWARE"]:
                    current_warehouse = clean_warehouse_name(first_cell)
                    warehouse_data[current_warehouse] = {
                        "registered": None,
                        "eligible": None,
                        "total": None,
                        "received": None,
                        "withdrawn": None,
                        "net_change": None,
                    }
                    continue

                # Check if this is a data row
                if current_warehouse and ("registered" in first_cell.lower() or
                                           "eligible" in first_cell.lower() or
                                           first_cell.lower() == "total"):

                    total_today = parse_number(sheet.cell_value(row_idx, 7) if sheet.ncols > 7
                                              else sheet.cell_value(row_idx, sheet.ncols - 1))
                    received = parse_number(sheet.cell_value(row_idx, 3) if sheet.ncols > 3 else None)
                    withdrawn = parse_number(sheet.cell_value(row_idx, 4) if sheet.ncols > 4 else None)
                    net_change = parse_number(sheet.cell_value(row_idx, 5) if sheet.ncols > 5 else None)

                    if "registered" in first_cell.lower():
                        warehouse_data[current_warehouse]["registered"] = total_today
                        warehouse_data[current_warehouse]["received"] = received
                        warehouse_data[current_warehouse]["withdrawn"] = withdrawn
                        warehouse_data[current_warehouse]["net_change"] = net_change
                    elif "eligible" in first_cell.lower():
                        warehouse_data[current_warehouse]["eligible"] = total_today
                    elif first_cell.lower() == "total":
                        warehouse_data[current_warehouse]["total"] = total_today

            # Convert to records
            for warehouse, data in warehouse_data.items():
                records.append({
                    "date": activity_date,
                    "metal": metal,
                    "warehouse": warehouse,
                    "registered": data["registered"],
                    "eligible": data["eligible"],
                    "total": data["total"],
                    "received": data["received"],
                    "withdrawn": data["withdrawn"],
                    "net_change": data["net_change"],
                    "report_date": report_date,
                    "activity_date": activity_date,
                    "fetched_at": fetched_at,
                })

        return records

    except Exception as e:
        print(f"Error parsing platinum/palladium XLS: {e}")
        import traceback
        traceback.print_exc()
        return []


def load_inventory_csv() -> pd.DataFrame:
    """Load existing inventory CSV or create empty DataFrame."""
    if INVENTORY_CSV.exists():
        return pd.read_csv(INVENTORY_CSV)
    return pd.DataFrame(columns=INVENTORY_COLUMNS)


def save_inventory_csv(df: pd.DataFrame) -> None:
    """Save inventory DataFrame to CSV."""
    DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(INVENTORY_CSV, index=False)


def append_records(records: List[Dict]) -> int:
    """
    Append inventory records to CSV with deduplication.

    Deduplicates on (date, metal, warehouse).

    Returns number of new records added.
    """
    if not records:
        return 0

    df = load_inventory_csv()
    added = 0

    for record in records:
        date = record["date"]
        metal = record["metal"]
        warehouse = record["warehouse"]

        # Check for duplicate
        if not df.empty:
            mask = (df["date"] == date) & (df["metal"] == metal) & (df["warehouse"] == warehouse)
            if mask.any():
                continue

        # Add record
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        added += 1

    if added > 0:
        # Sort by date, metal, warehouse
        df = df.sort_values(["date", "metal", "warehouse"])
        save_inventory_csv(df)

    return added


def main():
    """Main entry point for fetching CME inventory data."""
    print("=" * 50)
    print("CME Inventory Fetcher")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 50)
    print()

    total_added = 0

    # Fetch Copper
    print("Fetching Copper stocks...")
    copper_content = download_xls(CME_URLS["copper"])
    if copper_content:
        copper_records = parse_copper_xls(copper_content)
        if copper_records:
            added = append_records(copper_records)
            total_added += added
            print(f"  Parsed {len(copper_records)} warehouse entries, added {added} new records")
        else:
            print("  Failed to parse Copper XLS")
    else:
        print("  Failed to download Copper XLS")

    print()

    # Fetch Platinum/Palladium
    print("Fetching Platinum/Palladium stocks...")
    papl_content = download_xls(CME_URLS["platinum_palladium"])
    if papl_content:
        papl_records = parse_platinum_palladium_xls(papl_content)
        if papl_records:
            added = append_records(papl_records)
            total_added += added
            print(f"  Parsed {len(papl_records)} entries, added {added} new records")
        else:
            print("  Failed to parse Platinum/Palladium XLS")
    else:
        print("  Failed to download Platinum/Palladium XLS")

    print()
    print("=" * 50)
    print(f"Complete: {total_added} total records added")
    print("=" * 50)

    return total_added > 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
