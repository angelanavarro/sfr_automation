"""
Reads new event registrations from the Jotform registration spreadsheet (R1)
and upserts into the annual spreadsheet's `registrations` tab.
Then regenerates the `riders_view` pivot tab.

Reads from:
  R1 (Jotform registration sheet) — Sheets API, Viewer access, never written to.
  SFR_Master riders tab           — to populate riders_view with name/email.

Writes to (annual SFR_YYYY spreadsheet, Editor access):
  registrations tab — one row per (rusa_id, event_id) pair
                      columns: rusa_id, event_id, status, waiver_submitted,
                               submission_id, registered_at, added_by
                      key: rusa_id|event_id composite
                      status values: X=paid, Y=free, V=volunteer, W=worker's ride, C=cancelled
  riders_view tab   — auto-generated pivot (cleared and rewritten each run)
                      rows: one per rider with any registration this year
                      cols: rusa_id, first_name, last_name, email, then one col per event (sorted by date)

The column→event mapping is built dynamically from the annual events tab
(jotform_column_name field), so new events added mid-year are picked up automatically.

Normalizes R1's wide format (one column per event) into one row per (rider, event).

Usage:
    python scripts/ingest_registration.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date, datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

from utils import format_sheet_headers, apply_membership_flags
from config import (
    CREDENTIALS_FILE, MASTER_SPREADSHEET_ID, ANNUAL_SPREADSHEET_ID,
    R1_SPREADSHEET_ID, R1_SHEET_NAME,
    AnnualTab, MasterTab, RegStatus, EventCol, CURRENT_YEAR,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# R1 column indices (0-based) for rider info
class R1Col:
    FIRST_NAME    = 38  # AM
    LAST_NAME     = 39  # AN
    EMAIL         = 40  # AO
    RUSA_ID       = 41  # AP
    BACKUP        = 42  # AQ
    BACKUP_PHONE  = 43  # AR
    WAIVER        = 48  # AW
    SUBMISSION_ID = 49  # AX


def get_client():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def fetch_sheet_rows(client, spreadsheet_id, sheet_name):
    """Fetch all rows from a spreadsheet via authenticated Sheets API."""
    ss = client.open_by_key(spreadsheet_id)
    ws = ss.worksheet(sheet_name)
    rows = ws.get_all_values()
    return rows[0], rows[1:]


def build_column_map(annual_ss):
    """
    Read the events tab and build a mapping of:
        r1_header_text → event_id
    for all jotform events. Warns about events with no jotform_column_name.
    """
    ws = annual_ss.worksheet(AnnualTab.EVENTS)
    rows = ws.get_all_values()
    col_map = {}
    for row in rows[1:]:
        if len(row) <= EventCol.JOTFORM_COLUMN_NAME:
            continue
        event_id = row[EventCol.EVENT_ID].strip()
        jotform_col_name = row[EventCol.JOTFORM_COLUMN_NAME].strip()
        source = row[EventCol.REGISTRATION_SOURCE].strip()
        if source == "jotform" and jotform_col_name:
            col_map[jotform_col_name] = event_id
        elif source == "jotform" and not jotform_col_name:
            print(f"  Warning: event {event_id} has registration_source=jotform but no jotform_column_name")
    return col_map


# R1 columns that are not events and should be silently ignored
R1_NON_EVENT_COLS = {"Prelim", "Subtotal"}


def parse_registrations(r1_headers, r1_rows, col_map):
    """
    Convert wide R1 rows into normalized registration records.
    col_map: {r1_header_text → event_id}
    """
    # Build index lookup: col_index → event_id
    index_to_event = {}
    unrecognized_cols = []
    for i, header in enumerate(r1_headers):
        header = header.strip()
        if header in col_map:
            index_to_event[i] = col_map[header]
        elif i > 0 and i < R1Col.FIRST_NAME and header and header not in R1_NON_EVENT_COLS:
            # Non-empty column in the event range that we don't recognize
            unrecognized_cols.append(header)

    if unrecognized_cols:
        print(f"  Warning: unrecognized Jotform columns (add to events tab): {unrecognized_cols}")

    registrations = []
    for row in r1_rows:
        def col(i, default=""):
            return row[i].strip() if i < len(row) else default

        rusa_id = col(R1Col.RUSA_ID)
        if not rusa_id:
            continue

        submission_id   = col(R1Col.SUBMISSION_ID)
        waiver_raw      = col(R1Col.WAIVER).lower()
        waiver_submitted = waiver_raw in ("yes", "true", "1", "x", "i agree")

        for col_idx, event_id in index_to_event.items():
            status = col(col_idx).strip().upper()
            if not status:
                continue
            if status not in RegStatus.ACTIVE and status != RegStatus.CANCELLED:
                # R1 cells contain the event name + price when registered (e.g.
                # "DILLON BEACH 200KM (SAT 1/24) $7.50") rather than a status code.
                # Any non-empty, unrecognized value means paid registration.
                status = RegStatus.PAID

            registrations.append({
                "rusa_id":          rusa_id,
                "event_id":         event_id,
                "status":           status,
                "waiver_submitted": waiver_submitted,
                "submission_id":    submission_id,
                "registered_at":    datetime.now(timezone.utc).isoformat(),
                "added_by":         "jotform",
            })

    return registrations


def load_existing_registrations(ws):
    """Load existing registrations keyed by 'rusa_id|event_id'."""
    existing = {}
    for i, row in enumerate(ws.get_all_values()[1:], start=2):
        if len(row) >= 2 and row[0] and row[1]:
            k = f"{row[0].strip()}|{row[1].strip()}"
            existing[k] = (i, row)
    return existing


def upsert_registrations(ws, existing, registrations):
    inserts, updates = [], []
    for reg in registrations:
        k = f"{reg['rusa_id']}|{reg['event_id']}"
        row = [
            reg["rusa_id"], reg["event_id"], reg["status"],
            reg["waiver_submitted"], reg["submission_id"],
            reg["registered_at"], reg["added_by"],
        ]
        if k in existing:
            sheet_row, existing_row = existing[k]
            existing_status  = existing_row[2] if len(existing_row) > 2 else ""
            existing_waiver  = str(existing_row[3]) if len(existing_row) > 3 else ""
            if existing_status != reg["status"] or existing_waiver != str(reg["waiver_submitted"]):
                updates.append((sheet_row, row))
        else:
            inserts.append(row)
            existing[k] = (None, row)

    if updates:
        ws.batch_update([
            {"range": f"A{sheet_row}", "values": [row]}
            for sheet_row, row in updates
        ])
    if inserts:
        ws.append_rows(inserts, value_input_option="USER_ENTERED")

    return len(inserts), len(updates)


def _load_annual_data(annual_ss, master_ss):
    """
    Load all data needed by both regenerate_riders_view and regenerate_summary_tab.

    Returns a dict with:
      events          — list of {event_id, event_date, sheet_url}, sorted by date
      reg_by_rider    — {rusa_id: {event_id: status}} (all statuses, including cancelled)
      reg_by_event    — {event_id: [{rusa_id, status, waiver}]} (all statuses)
      rider_info      — {rusa_id: {first_name, last_name, email}}
      sfr_membership  — {rusa_id: status} for CURRENT_YEAR (present = has membership)
      rusa_membership — {rusa_id: "X" if current, "" if expired/missing}
    """
    today = date.today().isoformat()

    ws_events = annual_ss.worksheet(AnnualTab.EVENTS)
    event_rows = ws_events.get_all_values()[1:]
    events = [
        {
            "event_id":   r[EventCol.EVENT_ID],
            "route_id":   r[EventCol.ROUTE_ID],
            "event_date": r[EventCol.EVENT_DATE],
            "sheet_url":  r[EventCol.SHEET_URL] if len(r) > EventCol.SHEET_URL else "",
        }
        for r in event_rows if r[EventCol.EVENT_ID]
    ]
    events.sort(key=lambda e: e["event_date"])

    reg_by_rider = {}
    reg_by_event = {}
    ws_reg = annual_ss.worksheet(AnnualTab.REGISTRATIONS)
    for row in ws_reg.get_all_values()[1:]:
        if len(row) < 3 or not row[0]:
            continue
        rusa_id  = row[0].strip()
        event_id = row[1].strip()
        status   = row[2].strip()
        waiver   = str(row[3]).strip() if len(row) > 3 else ""
        reg_by_rider.setdefault(rusa_id, {})[event_id] = status
        reg_by_event.setdefault(event_id, []).append(
            {"rusa_id": rusa_id, "status": status, "waiver": waiver}
        )

    ws_riders = master_ss.worksheet(MasterTab.RIDERS)
    rider_info = {}
    for row in ws_riders.get_all_values()[1:]:
        if row and row[0]:
            rider_info[row[0].strip()] = {
                "first_name": row[1] if len(row) > 1 else "",
                "last_name":  row[2] if len(row) > 2 else "",
                "email":      row[3] if len(row) > 3 else "",
            }

    ws_memb = master_ss.worksheet(MasterTab.MEMBERSHIPS)
    sfr_membership = {}
    for row in ws_memb.get_all_values()[1:]:
        if len(row) >= 3 and row[0] and row[1]:
            try:
                if int(row[1].strip()) == CURRENT_YEAR:
                    sfr_membership[row[0].strip()] = row[2].strip()
            except ValueError:
                pass

    ws_rusa = master_ss.worksheet(MasterTab.RUSA)
    rusa_membership = {}
    for row in ws_rusa.get_all_values()[1:]:
        if len(row) >= 2 and row[0] and row[1]:
            rusa_id  = row[0].strip()
            exp_date = row[1].strip()
            rusa_membership[rusa_id] = "X" if exp_date >= today else ""

    return {
        "events":          events,
        "reg_by_rider":    reg_by_rider,
        "reg_by_event":    reg_by_event,
        "rider_info":      rider_info,
        "sfr_membership":  sfr_membership,
        "rusa_membership": rusa_membership,
    }


def regenerate_riders_view(annual_ss, master_ss, data=None):
    """
    Build and write the riders_view pivot tab in the annual spreadsheet.

    Layout:
      Row 1 (header):    fixed labels + one event_date per event (sorted)
      Row 2 (subheader): blanks       + one event_id per event
      Data rows:         one per rider with at least one registration this year

    Fixed columns: rusa_id, first_name, last_name, email, sfr_member, rusa_member
      sfr_member:  status for CURRENT_YEAR (X/Y or blank)
      rusa_member: X if RUSA expiration_date >= today, blank otherwise

    Pass `data` (from _load_annual_data) to avoid redundant API calls when
    calling both regenerate_riders_view and regenerate_summary_tab in the same run.
    The tab is cleared and fully rewritten on each call.
    """
    print("Regenerating riders_view...")

    if data is None:
        data = _load_annual_data(annual_ss, master_ss)

    events         = data["events"]
    reg_by_rider   = data["reg_by_rider"]
    rider_info     = data["rider_info"]
    sfr_membership = data["sfr_membership"]
    rusa_membership = data["rusa_membership"]

    event_ids   = [e["event_id"] for e in events]
    event_dates = [e["event_date"] for e in events]
    fixed_headers = ["rusa_id", "first_name", "last_name", "email", "sfr_member", "rusa_member"]
    header    = fixed_headers + event_dates
    subheader = [""] * len(fixed_headers) + event_ids

    data_rows = []
    for rusa_id, regs in sorted(reg_by_rider.items()):
        info = rider_info.get(rusa_id, {"first_name": "", "last_name": "", "email": ""})
        data_rows.append([
            rusa_id,
            info["first_name"],
            info["last_name"],
            info["email"],
            sfr_membership.get(rusa_id, ""),
            rusa_membership.get(rusa_id, ""),
        ] + [regs.get(eid, "") for eid in event_ids])

    ws_view = annual_ss.worksheet(AnnualTab.RIDERS_VIEW)
    ws_view.clear()
    ws_view.update([header, subheader] + data_rows, "A1")
    format_sheet_headers(ws_view, num_cols=len(header), has_subheader=True)
    apply_membership_flags(annual_ss, ws_view, header_rows=2)

    annual_ss.batch_update({"requests": [{
        "updateSheetProperties": {
            "properties": {
                "sheetId": ws_view.id,
                "gridProperties": {"frozenRowCount": 2, "frozenColumnCount": 6}
            },
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"
        }
    }]})

    print(f"  riders_view: {len(data_rows)} riders, {len(event_ids)} events")


def regenerate_summary_tab(annual_ss, master_ss, data=None):
    """
    Build and write the event_summary tab in the annual spreadsheet.

    One row per event (all events in the events tab, sorted by date).
    Columns:
      event_id        — event identifier
      event_date      — ISO date
      total           — all active (non-cancelled) registrations
      paid            — X status count
      free            — Y status count
      volunteer       — V status count
      workers_ride    — W status count
      cancelled       — C status count
      waiver_submitted — count of riders who submitted a waiver
      no_sfr_member   — active riders with no SFR membership for CURRENT_YEAR
      no_rusa_member  — active riders with no current RUSA membership
      sheet_url       — link to the per-event roster sheet (blank if not yet created)

    Pass `data` (from _load_annual_data) to avoid redundant API calls.
    The tab is cleared and fully rewritten on each call.
    Creates the tab if it doesn't already exist.
    """
    print("Regenerating event_summary...")

    if data is None:
        data = _load_annual_data(annual_ss, master_ss)

    events          = data["events"]
    reg_by_event    = data["reg_by_event"]
    sfr_membership  = data["sfr_membership"]
    rusa_membership = data["rusa_membership"]

    header = [
        "event_id", "event_date", "route_id",
        "total", "paid", "free", "volunteer", "workers_ride", "cancelled",
        "waiver_submitted", "no_sfr_member", "no_rusa_member", "sheet_url",
    ]

    data_rows = []
    for event in events:
        eid  = event["event_id"]
        regs = reg_by_event.get(eid, [])

        counts = {s: 0 for s in (RegStatus.PAID, RegStatus.FREE,
                                  RegStatus.VOLUNTEER, RegStatus.WORKERS,
                                  RegStatus.CANCELLED)}
        waiver_count = 0
        no_sfr = 0
        no_rusa = 0

        for r in regs:
            s = r["status"]
            counts[s] = counts.get(s, 0) + 1

            if s in RegStatus.ACTIVE:
                if r["waiver"].upper() in ("TRUE", "Y", "YES", "1"):
                    waiver_count += 1
                if not sfr_membership.get(r["rusa_id"]):
                    no_sfr += 1
                if not rusa_membership.get(r["rusa_id"]):
                    no_rusa += 1

        total_active = sum(counts[s] for s in RegStatus.ACTIVE)

        data_rows.append([
            eid,
            event["event_date"],
            event["route_id"],
            total_active,
            counts[RegStatus.PAID],
            counts[RegStatus.FREE],
            counts[RegStatus.VOLUNTEER],
            counts[RegStatus.WORKERS],
            counts[RegStatus.CANCELLED],
            waiver_count,
            no_sfr,
            no_rusa,
            event["sheet_url"],
        ])

    try:
        ws = annual_ss.worksheet(AnnualTab.SUMMARY)
    except Exception:
        ws = annual_ss.add_worksheet(title=AnnualTab.SUMMARY, rows=200, cols=len(header) + 2)

    ws.clear()
    ws.update([header] + data_rows, "A1")
    format_sheet_headers(ws, num_cols=len(header))

    annual_ss.batch_update({"requests": [{
        "updateSheetProperties": {
            "properties": {
                "sheetId": ws.id,
                "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 2}
            },
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"
        }
    }]})

    print(f"  event_summary: {len(data_rows)} events")


def main():
    print("Connecting to spreadsheets...")
    try:
        client = get_client()
        annual_ss = client.open_by_key(ANNUAL_SPREADSHEET_ID)
        master_ss = client.open_by_key(MASTER_SPREADSHEET_ID)
    except Exception as e:
        print(f"ERROR: Could not connect to Google Sheets — {e}")
        sys.exit(1)

    print("Fetching registration form data...")
    try:
        r1_headers, r1_rows = fetch_sheet_rows(client, R1_SPREADSHEET_ID, R1_SHEET_NAME)
    except Exception as e:
        print(f"ERROR: Could not read R1 registration sheet — {e}")
        sys.exit(1)
    print(f"  {len(r1_rows)} submission rows found")

    print("Building event→column map from events tab...")
    col_map = build_column_map(annual_ss)
    print(f"  {len(col_map)} jotform events mapped")

    print("Parsing registrations...")
    registrations = parse_registrations(r1_headers, r1_rows, col_map)
    print(f"  {len(registrations)} (rider, event) records parsed")

    ws_reg = annual_ss.worksheet(AnnualTab.REGISTRATIONS)
    existing = load_existing_registrations(ws_reg)

    print("Upserting registrations...")
    n_ins, n_upd = upsert_registrations(ws_reg, existing, registrations)
    print(f"  {n_ins} inserted, {n_upd} updated")

    # Load shared data once for both regeneration passes (avoids duplicate API calls)
    data = _load_annual_data(annual_ss, master_ss)
    regenerate_riders_view(annual_ss, master_ss, data=data)
    regenerate_summary_tab(annual_ss, master_ss, data=data)
    print("Done.")


if __name__ == "__main__":
    main()
