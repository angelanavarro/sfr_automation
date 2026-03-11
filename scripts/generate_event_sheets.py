"""
Generates per-event spreadsheets for events happening within the next 30 days.

For each qualifying event, creates (or updates) a spreadsheet with 5 tabs:
  Roster          — rusa, name, status only (no contact info); includes worker's ride section
  Full Roster     — complete contact info for all registered riders
  Worker's Ride   — contact info for W-status riders only
  Waiver Checklist — rusa, name, email, waiver submitted status
  Draft Results   — pre-populated rider list with blank result columns

Reads from:
  SFR_2026 events tab       — to find upcoming events and their existing sheet_id
  SFR_2026 registrations tab — rider registration data
  SFR_Master riders tab      — contact info

Writes to:
  Per-event spreadsheets in EVENTS_FOLDER_ID (created in user's Drive folder)
  SFR_2026 events tab        — sheet_id column updated after creation

Prerequisites:
  Create a folder in Google Drive, share it (Editor) with the service account,
  and set EVENTS_FOLDER_ID in config.py.

Usage:
    python scripts/generate_event_sheets.py [--days N]
    Default: events in the next 30 days.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse
import re
import time

import gspread
from google.oauth2.service_account import Credentials

from datetime import date, timedelta

from config import (
    CREDENTIALS_FILE, MASTER_SPREADSHEET_ID, ANNUAL_SPREADSHEET_ID,
    EVENTS_FOLDER_ID, MasterTab, AnnualTab, EventCol, RegStatus, CURRENT_YEAR,
)
from utils import format_sheet_headers, FLAG_YELLOW

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Tabs to create in each event spreadsheet, in order
EVENT_TABS = ["Roster", "Full Roster", "Worker's Ride", "Waiver Checklist", "Draft Results"]


def get_client():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def load_upcoming_events(annual_ss, days):
    """
    Return list of event dicts to process:
    - Events with an existing sheet_url are always included (update regardless of date)
    - Events without a sheet_url are included only if within the next `days` days (creation window)
    """
    ws = annual_ss.worksheet(AnnualTab.EVENTS)
    rows = ws.get_all_values()
    today = date.today()
    cutoff = today + timedelta(days=days)
    upcoming = []
    for i, row in enumerate(rows[1:], start=2):
        if not row[EventCol.EVENT_ID]:
            continue
        try:
            event_date = date.fromisoformat(row[EventCol.EVENT_DATE])
        except ValueError:
            continue
        sheet_url = row[EventCol.SHEET_URL] if len(row) > EventCol.SHEET_URL else ""
        # Always update existing sheets; only create new ones within the window
        if sheet_url or today <= event_date <= cutoff:
            upcoming.append({
                "sheet_row":        i,
                "event_id":         row[EventCol.EVENT_ID],
                "route_id":         row[EventCol.ROUTE_ID],
                "event_date":       row[EventCol.EVENT_DATE],
                "worker_ride_date": row[EventCol.WORKER_RIDE_DATE] if len(row) > EventCol.WORKER_RIDE_DATE else "",
                "sheet_url":        sheet_url,
            })
    return ws, upcoming


def load_riders(master_ss):
    """Load rider contact info keyed by rusa_id."""
    ws = master_ss.worksheet(MasterTab.RIDERS)
    rider_info = {}
    for row in ws.get_all_values()[1:]:
        if row and row[0]:
            rider_info[row[0].strip()] = {
                "first":   row[1] if len(row) > 1 else "",
                "last":    row[2] if len(row) > 2 else "",
                "email":   row[3] if len(row) > 3 else "",
                "phone":   row[4] if len(row) > 4 else "",
                "backup":  row[5] if len(row) > 5 else "",
                "backup_phone": row[6] if len(row) > 6 else "",
                "address": row[7] if len(row) > 7 else "",
                "city":    row[8] if len(row) > 8 else "",
                "state":   row[9] if len(row) > 9 else "",
                "zip":     row[10] if len(row) > 10 else "",
            }
    return rider_info


def load_memberships(master_ss):
    """
    Returns a dict {rusa_id: color} for riders with membership issues.

    Checks all rider IDs known from either the SFR memberships tab or the
    RUSA memberships tab:
      FLAG_ORANGE = no current RUSA membership (takes priority)
      FLAG_YELLOW = current RUSA membership but no SFR membership for CURRENT_YEAR

    Riders with both memberships current are not included in the dict.
    """
    FLAG_ORANGE = {"red": 1.0, "green": 0.8, "blue": 0.6}
    today = date.today().isoformat()

    # SFR memberships for current year: set of rusa_ids with a paid/free record
    ws_sfr = master_ss.worksheet(MasterTab.MEMBERSHIPS)
    sfr_current = set()
    for row in ws_sfr.get_all_values()[1:]:
        if len(row) >= 2 and row[0] and row[1]:
            try:
                if int(row[1].strip()) == CURRENT_YEAR:
                    sfr_current.add(row[0].strip())
            except ValueError:
                pass

    # RUSA memberships: set of rusa_ids whose expiration_date >= today
    ws_rusa = master_ss.worksheet(MasterTab.RUSA)
    rusa_current = set()
    for row in ws_rusa.get_all_values()[1:]:
        if len(row) >= 2 and row[0] and row[1] and row[1].strip() >= today:
            rusa_current.add(row[0].strip())

    # Flag every ID known from either source — orange wins over yellow
    flags = {}
    for rusa_id in sfr_current | rusa_current:
        no_rusa = rusa_id not in rusa_current
        no_sfr  = rusa_id not in sfr_current
        if no_rusa:
            flags[rusa_id] = FLAG_ORANGE
        elif no_sfr:
            flags[rusa_id] = FLAG_YELLOW
    return flags


def apply_rusa_cell_flags(ws, regs, flags, rusa_col_index=0, header_rows=1):
    """
    Color the RUSA# cell for riders with membership issues.
    rusa_col_index: 0-based column index of the RUSA# column.
    header_rows: number of header rows to skip.
    """
    requests = []
    for i, (rusa_id, _, _) in enumerate(regs):
        color = flags.get(rusa_id)
        if color:
            row_index = header_rows + i  # 0-based
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": ws.id,
                        "startRowIndex": row_index,
                        "endRowIndex":   row_index + 1,
                        "startColumnIndex": rusa_col_index,
                        "endColumnIndex":   rusa_col_index + 1,
                    },
                    "cell": {"userEnteredFormat": {"backgroundColor": color}},
                    "fields": "userEnteredFormat.backgroundColor",
                }
            })
    if requests:
        ws.spreadsheet.batch_update({"requests": requests})


def load_all_registrations(annual_ss):
    """Load all registrations once, returned as {event_id: [(rusa_id, status, waiver)]}."""
    ws = annual_ss.worksheet(AnnualTab.REGISTRATIONS)
    regs_by_event = {}
    for row in ws.get_all_values()[1:]:
        if len(row) < 3 or not row[0] or not row[1]:
            continue
        status = row[2].strip().upper()
        if status == RegStatus.CANCELLED:
            continue
        event_id = row[1].strip()
        waiver   = str(row[3]).strip() if len(row) > 3 else ""
        regs_by_event.setdefault(event_id, []).append((row[0].strip(), status, waiver))
    return regs_by_event


def open_sheet(client, url_or_id):
    """Open a spreadsheet by URL or bare spreadsheet ID."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_or_id)
    sheet_id = match.group(1) if match else url_or_id.strip()
    return client.open_by_key(sheet_id)


def create_event_spreadsheet(client, title):
    """Create a new spreadsheet in EVENTS_FOLDER_ID and return it."""
    if not EVENTS_FOLDER_ID:
        raise ValueError(
            "EVENTS_FOLDER_ID is not set in config.py.\n"
            "Create a folder in Google Drive, share it (Editor) with the service account, "
            "and paste the folder ID into config.py."
        )
    return client.create(title, folder_id=EVENTS_FOLDER_ID)


def setup_event_spreadsheet(ss):
    """Set up the 5 tabs in a freshly created event spreadsheet."""
    # Rename default Sheet1 to first tab
    ss.sheet1.update_title(EVENT_TABS[0])
    for tab_name in EVENT_TABS[1:]:
        ss.add_worksheet(title=tab_name, rows=500, cols=20)


def write_roster_tab(ws, regs, rider_info, flags):
    """
    Roster tab (R4a style): rusa, first, last, status — no contact info.
    Left section: all active non-W riders. Right section: Worker's Ride riders.
    RUSA# cell is color-flagged for membership issues.
    Total Riders / Total Workers are spreadsheet formulas (=COUNTA) so they
    stay accurate if rows are added or removed manually.
    """
    active = [(r, s, w) for r, s, w in regs if s != RegStatus.WORKERS]
    workers = [(r, s, w) for r, s, w in regs if s == RegStatus.WORKERS]

    header = ["RUSA#", "First", "Last", "Status", "Total Riders",
              "", "RUSA#", "First", "Last", "Total Workers"]

    rows = [header]
    for i in range(max(len(active), len(workers), 1)):
        row = []
        if i < len(active):
            r, s, _ = active[i]
            info = rider_info.get(r, {})
            # Formula in E2 only; blank for subsequent rows
            count = "=COUNTA(A2:A)" if i == 0 else ""
            row += [r, info.get("first", ""), info.get("last", ""), s, count]
        else:
            row += ["", "", "", "", ""]
        row += [""]
        if i < len(workers):
            r, s, _ = workers[i]
            info = rider_info.get(r, {})
            count = "=COUNTA(G2:G)" if i == 0 else ""
            row += [r, info.get("first", ""), info.get("last", ""), count]
        else:
            row += ["", "", "", ""]
        rows.append(row)

    ws.clear()
    ws.update(rows, "A1", value_input_option="USER_ENTERED")
    format_sheet_headers(ws, num_cols=len(header))
    apply_rusa_cell_flags(ws, active, flags, rusa_col_index=0)
    apply_rusa_cell_flags(ws, workers, flags, rusa_col_index=6)


def write_full_roster_tab(ws, regs, rider_info, flags):
    """Full Roster tab (R4b Roster): all riders with complete contact info.
    RUSA# cell is color-flagged for membership issues.
    Total Riders is a formula so it stays accurate after manual edits.
    """
    header = ["RUSA#", "First", "Last", "Address", "City", "State", "Zip",
              "Phone", "Backup", "Backup Phone", "Email", "Status", "Total Riders"]
    rows = [header]
    for i, (rusa_id, status, _) in enumerate(regs):
        info = rider_info.get(rusa_id, {})
        count = "=COUNTA(A2:A)" if i == 0 else ""
        rows.append([
            rusa_id, info.get("first", ""), info.get("last", ""),
            info.get("address", ""), info.get("city", ""), info.get("state", ""),
            info.get("zip", ""), info.get("phone", ""), info.get("backup", ""),
            info.get("backup_phone", ""), info.get("email", ""), status, count,
        ])

    ws.clear()
    ws.update(rows, "A1", value_input_option="USER_ENTERED")
    format_sheet_headers(ws, num_cols=len(header))
    apply_rusa_cell_flags(ws, regs, flags, rusa_col_index=0)


def write_workers_ride_tab(ws, regs, rider_info):
    """Worker's Ride tab: W-status riders only, with full contact info.
    Total Workers is a formula so it stays accurate after manual edits.
    """
    workers = [(r, s, w) for r, s, w in regs if s == RegStatus.WORKERS]
    header = ["RUSA#", "First", "Last", "Address", "City", "State", "Zip",
              "Phone", "Backup", "Backup Phone", "Email", "Status", "Total Workers"]
    rows = [header]
    for i, (rusa_id, status, _) in enumerate(workers):
        info = rider_info.get(rusa_id, {})
        count = "=COUNTA(A2:A)" if i == 0 else ""
        rows.append([
            rusa_id, info.get("first", ""), info.get("last", ""),
            info.get("address", ""), info.get("city", ""), info.get("state", ""),
            info.get("zip", ""), info.get("phone", ""), info.get("backup", ""),
            info.get("backup_phone", ""), info.get("email", ""), status, count,
        ])

    ws.clear()
    ws.update(rows, "A1", value_input_option="USER_ENTERED")
    format_sheet_headers(ws, num_cols=len(header))


def write_waiver_tab(ws, regs, rider_info):
    """Waiver Checklist tab: rusa, name, email, waiver submitted."""
    header = ["RUSA#", "First", "Last", "Email", "Waiver Submitted"]
    rows = [header]
    for rusa_id, _, waiver in regs:
        info = rider_info.get(rusa_id, {})
        waiver_val = "Y" if str(waiver).upper() in ("TRUE", "Y", "YES", "1") else ""
        rows.append([
            rusa_id, info.get("first", ""), info.get("last", ""),
            info.get("email", ""), waiver_val,
        ])

    ws.clear()
    ws.update(rows, "A1")
    format_sheet_headers(ws, num_cols=len(header))


def write_draft_results_tab(ws, regs, rider_info):
    """Draft Results tab: pre-populated rider list, blank result columns for Rob to fill."""
    header = ["RUSA#", "First", "Last", "Email", "Hours", "Minutes", "DNF",
              "Sent EPP", "Proof of Passage"]
    rows = [header]
    for rusa_id, _, _ in regs:
        info = rider_info.get(rusa_id, {})
        rows.append([
            rusa_id, info.get("first", ""), info.get("last", ""),
            info.get("email", ""), "", "", "", "", "",
        ])

    ws.clear()
    ws.update(rows, "A1")
    format_sheet_headers(ws, num_cols=len(header))


def generate_event_sheet(event, client, ws_events, rider_info, flags, regs_by_event):
    """
    Create or update the spreadsheet for a single event.

    rider_info, flags, and regs_by_event are pre-loaded once by main() and
    passed in to avoid per-event API calls that trigger 429 quota errors.

    Returns True on success, False if the event was skipped or failed.
    """
    regs = regs_by_event.get(event["event_id"], [])
    if not regs:
        print(f"  Skipping — no registrations")
        return False

    # Sort by last name
    regs = sorted(regs, key=lambda x: rider_info.get(x[0], {}).get("last", "").lower())

    if event["sheet_url"]:
        print(f"  Updating existing sheet...")
        ss = open_sheet(client, event["sheet_url"])
    else:
        print(f"  Creating new sheet...")
        ss = create_event_spreadsheet(client, event["event_id"])
        setup_event_spreadsheet(ss)
        ws_events.update([[ss.url]], f"H{event['sheet_row']}")
        print(f"    Created: {ss.url}")

    write_roster_tab(ss.worksheet("Roster"), regs, rider_info, flags)
    write_full_roster_tab(ss.worksheet("Full Roster"), regs, rider_info, flags)
    write_workers_ride_tab(ss.worksheet("Worker's Ride"), regs, rider_info)
    write_waiver_tab(ss.worksheet("Waiver Checklist"), regs, rider_info)
    write_draft_results_tab(ss.worksheet("Draft Results"), regs, rider_info)

    print(f"    {len(regs)} riders written across 5 tabs")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30,
                        help="Generate sheets for events within this many days (default: 30)")
    args = parser.parse_args()

    print("Connecting to spreadsheets...")
    try:
        client = get_client()
        annual_ss = client.open_by_key(ANNUAL_SPREADSHEET_ID)
        master_ss = client.open_by_key(MASTER_SPREADSHEET_ID)
    except Exception as e:
        print(f"ERROR: Could not connect to Google Sheets — {e}")
        sys.exit(1)

    print(f"Loading events in the next {args.days} days...")
    try:
        ws_events, upcoming = load_upcoming_events(annual_ss, args.days)
    except Exception as e:
        print(f"ERROR: Could not load events tab — {e}")
        sys.exit(1)
    print(f"  {len(upcoming)} upcoming events found")

    if not upcoming:
        print("Nothing to do.")
        return

    # Load shared data once — avoids one set of API calls per event (which causes 429s)
    print("Loading riders, memberships, and registrations...")
    try:
        rider_info    = load_riders(master_ss)
        flags         = load_memberships(master_ss)
        regs_by_event = load_all_registrations(annual_ss)
    except Exception as e:
        print(f"ERROR: Could not load shared data — {e}")
        sys.exit(1)
    print(f"  {len(rider_info)} riders, {len(regs_by_event)} events with registrations")

    errors = []
    for i, event in enumerate(upcoming):
        print(f"\n{event['event_id']} ({event['event_date']})")
        try:
            generate_event_sheet(event, client, ws_events, rider_info, flags, regs_by_event)
        except Exception as e:
            print(f"  ERROR: {e}")
            errors.append((event["event_id"], str(e)))
        # Throttle between events to stay well under the Sheets API write quota.
        # Each event sheet update makes ~10 write calls; 15s keeps us under the
        # 60-writes-per-minute limit even for back-to-back large events.
        if i < len(upcoming) - 1:
            time.sleep(15)

    print("\nDone.")
    if errors:
        print(f"\n{len(errors)} event(s) failed:")
        for event_id, msg in errors:
            print(f"  {event_id}: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
