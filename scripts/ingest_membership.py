"""
Reads new membership submissions from the Jotform membership spreadsheet (M1)
and upserts into the master spreadsheet's `riders` and `memberships` tabs.

Reads from:
  M1 (Jotform membership sheet) — Sheets API, Viewer access, never written to.

Writes to (SFR_Master spreadsheet, Editor access):
  riders tab       — one row per unique RUSA ID
                     columns: rusa_id, first_name, last_name, email, phone,
                              backup_contact (blank), backup_phone (blank),
                              address, city, state, zip, country (blank)
                     key: rusa_id (latest submission wins on update)
  memberships tab  — one row per (rusa_id, year) pair
                     columns: rusa_id, year, status
                     key: rusa_id|year composite

Also triggers riders_view regeneration in the annual spreadsheet so any
updated rider info (name, email) is immediately reflected there.

Handles:
- New riders (insert)
- Updated rider info (upsert by rusa_id — latest submission wins)
- Multi-year membership field (e.g. "2024\\n2025\\n2026" → one row per year)

Usage:
    python scripts/ingest_membership.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import re
from datetime import date, datetime

import gspread
from google.oauth2.service_account import Credentials

from utils import format_sheet_headers
from config import (
    CREDENTIALS_FILE, MASTER_SPREADSHEET_ID, get_active_annual_ids,
    M1_SPREADSHEET_ID, M1_SHEET_NAME,
    MasterTab, M1Col, CURRENT_YEAR,
)
from scripts.ingest_registration import regenerate_riders_view

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MEMBERSHIP_STATUSES = {"X", "Y"}  # valid paid/free membership values in M1


def get_client():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def fetch_m1_rows(client):
    """Fetch all rows from M1 (Jotform membership sheet) via authenticated Sheets API."""
    ss = client.open_by_key(M1_SPREADSHEET_ID)
    ws = ss.worksheet(M1_SHEET_NAME)
    rows = ws.get_all_values()
    return rows[0], rows[1:]  # headers, data rows


def parse_membership_years(sfr_membership_field):
    """
    Parse the SFR membership field which contains one or more years.
    E.g. "2024\n2025\n2026" or "2024, 2025" or just "2026".
    Returns list of (year, status) tuples. Status defaults to 'X' (paid)
    until more nuanced parsing is needed.
    """
    text = sfr_membership_field.strip()
    years = re.findall(r"20\d{2}", text)
    return [(int(y), "X") for y in set(years)]


def build_rider_row(row):
    """Map an M1 data row to a riders tab row."""
    def col(i):
        return row[i].strip() if i < len(row) else ""

    return [
        col(M1Col.RUSA_ID),
        col(M1Col.FIRST_NAME),
        col(M1Col.LAST_NAME),
        col(M1Col.EMAIL),
        col(M1Col.PHONE),
        "",  # backup_contact (not in M1)
        "",  # backup_phone (not in M1)
        col(M1Col.ADDRESS),
        col(M1Col.CITY),
        col(M1Col.STATE),
        col(M1Col.ZIP),
        "",  # country (not in M1)
    ]


def load_existing(ws, key_col=0):
    """Load a worksheet into a dict keyed by the value in key_col."""
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return {}, all_rows[0] if all_rows else []
    headers = all_rows[0]
    data = {str(row[key_col]).strip(): (i + 2, row) for i, row in enumerate(all_rows[1:]) if row[key_col]}
    return data, headers


def upsert_rows(ws, existing, new_rows, key_col=0):
    """
    Upsert rows into a worksheet.
    existing: dict of {key: (sheet_row_number, row_data)}
    new_rows: list of rows to upsert
    Returns counts of inserted and updated rows.
    """
    inserts = []
    updates = []

    for row in new_rows:
        key = str(row[key_col]).strip()
        if not key:
            continue
        if key in existing:
            sheet_row, _ = existing[key]
            if sheet_row is not None:  # None means queued for insert this run
                updates.append((sheet_row, row))
        else:
            inserts.append(row)
            existing[key] = (None, row)  # prevent duplicate inserts in same run

    # Batch update existing rows (single API call)
    if updates:
        ws.batch_update([
            {"range": f"A{sheet_row}", "values": [row]}
            for sheet_row, row in updates
        ])

    # Append new rows
    if inserts:
        ws.append_rows(inserts, value_input_option="USER_ENTERED")

    return len(inserts), len(updates)


def regenerate_memberships_view(master_ss):
    """
    Build and write the memberships_view pivot tab in SFR_Master.

    Columns: rusa_id, first_name, last_name, sfr_member, rusa_member, [year...]
      sfr_member:  status for CURRENT_YEAR from the memberships tab (X/Y or blank)
      rusa_member: X if RUSA expiration_date >= today, blank otherwise
      year cols:   one per year found in the memberships tab (sorted ascending)

    The tab is cleared and fully rewritten on each call.
    Creates the tab if it doesn't exist.
    """

    # Load rider info
    ws_riders = master_ss.worksheet(MasterTab.RIDERS)
    rider_rows = ws_riders.get_all_values()[1:]
    rider_info = {}
    for row in rider_rows:
        if row and row[0]:
            rider_info[row[0].strip()] = {
                "first_name": row[1] if len(row) > 1 else "",
                "last_name":  row[2] if len(row) > 2 else "",
            }

    # Load all SFR memberships: {rusa_id: {year: status}}
    ws_memb = master_ss.worksheet(MasterTab.MEMBERSHIPS)
    memb_rows = ws_memb.get_all_values()[1:]
    memb_by_rider = {}
    for row in memb_rows:
        if len(row) >= 3 and row[0] and row[1]:
            try:
                year = int(row[1].strip())
            except ValueError:
                continue
            memb_by_rider.setdefault(row[0].strip(), {})[year] = row[2].strip()

    # Load RUSA memberships: {rusa_id: "X" if current, "" if expired/missing}
    ws_rusa = master_ss.worksheet(MasterTab.RUSA)
    rusa_rows = ws_rusa.get_all_values()[1:]
    rusa_membership = {}
    today = date.today().isoformat()
    for row in rusa_rows:
        if len(row) >= 2 and row[0] and row[1]:
            rusa_id  = row[0].strip()
            exp_date = row[1].strip()
            rusa_membership[rusa_id] = "X" if exp_date >= today else ""

    # Collect all years across all riders, sorted
    all_years = sorted({year for years in memb_by_rider.values() for year in years})

    fixed_headers = ["rusa_id", "first_name", "last_name", "sfr_member", "rusa_member"]
    header = fixed_headers + [str(y) for y in all_years]

    data_rows = []
    for rusa_id, year_map in sorted(memb_by_rider.items()):
        info = rider_info.get(rusa_id, {"first_name": "", "last_name": ""})
        row = [
            rusa_id,
            info["first_name"],
            info["last_name"],
            year_map.get(CURRENT_YEAR, ""),
            rusa_membership.get(rusa_id, ""),
        ] + [year_map.get(y, "") for y in all_years]
        data_rows.append(row)

    # Write to memberships_view (clear and rewrite)
    try:
        ws_view = master_ss.worksheet(MasterTab.MEMBERSHIPS_VIEW)
    except Exception:
        ws_view = master_ss.add_worksheet(title=MasterTab.MEMBERSHIPS_VIEW, rows=2000, cols=30)

    ws_view.clear()
    ws_view.update([header] + data_rows, "A1")
    format_sheet_headers(ws_view, num_cols=len(header))

    # Freeze header row and first 4 columns
    master_ss.batch_update({"requests": [{
        "updateSheetProperties": {
            "properties": {
                "sheetId": ws_view.id,
                "gridProperties": {
                    "frozenRowCount": 1,
                    "frozenColumnCount": 5,
                }
            },
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"
        }
    }]})

    print(f"  memberships_view: {len(data_rows)} riders, {len(all_years)} years ({', '.join(str(y) for y in all_years)})")


def main():
    print("Connecting to spreadsheets...")
    try:
        client = get_client()
        master_ss = client.open_by_key(MASTER_SPREADSHEET_ID)
    except Exception as e:
        print(f"ERROR: Could not connect to Google Sheets — {e}")
        sys.exit(1)

    print("Fetching M1 membership data...")
    try:
        _, m1_rows = fetch_m1_rows(client)
    except Exception as e:
        print(f"ERROR: Could not read M1 membership sheet — {e}")
        sys.exit(1)
    print(f"  {len(m1_rows)} submission rows found")

    ws_riders      = master_ss.worksheet(MasterTab.RIDERS)
    ws_memberships = master_ss.worksheet(MasterTab.MEMBERSHIPS)

    existing_riders, _ = load_existing(ws_riders, key_col=0)

    # Build composite key index for memberships: "rusa_id|year" → (sheet_row, row)
    existing_memb_keys = {}
    for i, row in enumerate(ws_memberships.get_all_values()[1:], start=2):
        if len(row) >= 2 and row[0] and row[1]:
            k = f"{row[0].strip()}|{row[1].strip()}"
            existing_memb_keys[k] = (i, row)

    new_rider_rows = []
    new_membership_rows = []
    skipped = 0

    for row in m1_rows:
        rusa_id = row[M1Col.RUSA_ID].strip() if len(row) > M1Col.RUSA_ID else ""
        if not rusa_id:
            skipped += 1
            continue

        new_rider_rows.append(build_rider_row(row))

        sfr_field = row[M1Col.SFR_MEMBERSHIP].strip() if len(row) > M1Col.SFR_MEMBERSHIP else ""
        for year, status in parse_membership_years(sfr_field):
            new_membership_rows.append([rusa_id, year, status])

    print(f"  {skipped} rows skipped (no RUSA ID)")

    print("Upserting riders...")
    r_ins, r_upd = upsert_rows(ws_riders, existing_riders, new_rider_rows, key_col=0)
    print(f"  {r_ins} inserted, {r_upd} updated")

    print("Upserting memberships...")
    memb_inserts = []
    memb_updates = []
    for row in new_membership_rows:
        k = f"{row[0]}|{row[1]}"
        if k in existing_memb_keys:
            sheet_row, _ = existing_memb_keys[k]
            if sheet_row is not None:
                memb_updates.append((sheet_row, row))
        else:
            memb_inserts.append(row)
            existing_memb_keys[k] = (None, row)

    if memb_updates:
        ws_memberships.batch_update([
            {"range": f"A{sheet_row}", "values": [row]}
            for sheet_row, row in memb_updates
        ])
    if memb_inserts:
        ws_memberships.append_rows(memb_inserts, value_input_option="USER_ENTERED")
    print(f"  {len(memb_inserts)} inserted, {len(memb_updates)} updated")

    print("Regenerating memberships_view...")
    regenerate_memberships_view(master_ss)

    # Regenerate riders_view in all active annual spreadsheets so updated rider info is reflected
    for year, sid in get_active_annual_ids():
        print(f"Regenerating riders_view for SFR_{year}...")
        regenerate_riders_view(client.open_by_key(sid), master_ss)

    print("Done.")


if __name__ == "__main__":
    main()
