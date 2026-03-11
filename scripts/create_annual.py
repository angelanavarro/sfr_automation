"""
Sets up the annual SFR spreadsheet for a given year (events, registrations,
riders_view, volunteers). Run once per year at the start of the season.

Like create_master.py, this script operates on an existing blank spreadsheet
that you create in your own Google Drive and share with the service account (Editor).

After running, copy the printed spreadsheet ID into config.py → ANNUAL_SPREADSHEET_ID.

The events tab is pre-seeded with the known calendar for that year.
Rob can add new events to the events tab at any time during the year —
the ingest scripts will pick them up automatically on the next run.

Usage:
    python scripts/create_annual.py <spreadsheet_id> [year]
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import gspread
from google.oauth2.service_account import Credentials
from config import CREDENTIALS_FILE, AnnualTab, CURRENT_YEAR, EventCol
from utils import format_sheet_headers

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

TABS = {
    AnnualTab.EVENTS: [
        "event_id", "route_id", "event_date", "worker_ride_date",
        "registration_source", "course_notes", "jotform_column_name", "sheet_url"
    ],
    AnnualTab.REGISTRATIONS: [
        # Backend table — do not edit manually except to add manual registrations.
        # Use riders_view to see a rider's full schedule.
        # Use event sheets (R4a/R4b) to see a single event's roster.
        "rusa_id", "event_id", "status", "waiver_submitted",
        "submission_id", "registered_at", "added_by"
    ],
    AnnualTab.RIDERS_VIEW: [
        # Auto-generated pivot — do not edit. Regenerated on every ingest run.
        # Columns: rusa_id, first_name, last_name, email, then one column per event.
    ],
    AnnualTab.SUMMARY: [
        # Auto-generated — do not edit. Regenerated on every ingest run.
        # One row per event with registration counts and membership flag tallies.
        "event_id", "event_date",
        "total", "paid", "free", "volunteer", "workers_ride", "cancelled",
        "waiver_submitted", "no_sfr_member", "no_rusa_member", "sheet_url",
    ],
    AnnualTab.VOLUNTEERS: [
        "rusa_id", "event_id", "shift", "is_lead", "notes"
    ],
}

# 2026 events seed data
# Fields: event_id, route_id, year, event_date, worker_ride_date,
#         registration_source, course_notes, jotform_column_name
EVENTS_2026 = [
    # event_id, route_id, event_date, worker_ride_date, registration_source, course_notes, jotform_column_name
    ["2026_01_118_1", "point-reyes-populaire",  "2026-01-11", "", "jotform",       "", "January Point Reyes Populaire 118km"],
    ["2026_01_200_1", "dillon-beach",           "2026-01-24", "", "jotform",       "", "Dillon Beach 200km"],
    ["2026_02_200_1", "del-puerto-canyon",      "2026-02-14", "", "jotform",       "", "Spring Del Puerto Canyon 200km"],
    ["2026_02_300_1", "healdsburg",             "2026-02-28", "", "jotform",       "", "Healdsburg 300km"],
    ["2026_02_200_2", "two-rock-valley-ford",   "2026-02-28", "", "jotform",       "", "Two Rock-Valley Ford 200km"],
    ["2026_03_108_1", "womens-populaire",       "2026-03-08", "", "jotform",       "", "Women's Populaire 108km"],
    ["2026_03_200_1", "russian-river",          "2026-03-28", "", "jotform",       "", "Russian River 200km"],
    ["2026_04_480_1", "fleche",                 "2026-04-03", "", "separate_flow", "", ""],
    ["2026_04_400_1", "hopland",                "2026-04-11", "", "jotform",       "", "Hopland 400km"],
    ["2026_04_200_1", "fault-line",             "2026-04-11", "", "jotform",       "", "Faultline 200km"],
    ["2026_04_200_2", "marin-mountains",        "2026-04-19", "", "jotform",       "", "Marin Mountains 200km"],
    ["2026_05_600_1", "mendocino-coast",        "2026-05-02", "", "jotform",       "", "Mendocino Coast 600km"],
    ["2026_05_200_1", "laguna-lake",            "2026-05-03", "", "jotform",       "", "May Laguna Lake 200km"],
    ["2026_05_130_1", "big-rock-tocaloma",      "2026-05-03", "", "jotform",       "", "Big Rock-Tocaloma Populaire 130km"],
    ["2026_05_300_1", "old-cazadero",           "2026-05-16", "", "jotform",       "", "Old Caz 300km"],
    ["2026_05_200_2", "freestone-breadrun",     "2026-05-16", "", "jotform",       "", "Freestone Breadrun 200km"],
    ["2026_06_400_1", "king-ridge",             "2026-06-06", "", "jotform",       "", "King Ridge 400km"],
    ["2026_06_200_1", "mt-hamilton",            "2026-06-13", "", "jotform",       "", "Mt. Hamilton 200km"],
    ["2026_06_600_1", "orr-springs",            "2026-06-27", "", "jotform",       "", "Orr Springs 600km"],
    ["2026_06_200_2", "laguna-lake",            "2026-06-28", "", "jotform",       "", "June Laguna Lake 200km"],
    ["2026_06_111_1", "lucas-valley",           "2026-06-28", "", "jotform",       "", "Lucas Valley 111 km"],
    ["2026_07_300_1", "booneville-lollipop",    "2026-07-11", "", "jotform",       "", "Booneville Lollipop 300km"],
    ["2026_07_200_1", "sf-to-cloverdale",       "2026-07-11", "", "jotform",       "", "SF to Cloverdale 200km"],
    ["2026_07_200_2", "cloverdale-to-sf",       "2026-07-12", "", "jotform",       "", "Cloverdale to SF 200km"],
    ["2026_08_200_1", "laguna-lake",            "2026-08-29", "", "jotform",       "", "August Laguna Lake 200km"],
    ["2026_09_200_1", "coleman-valley",         "2026-09-06", "", "jotform",       "", "Coleman Valley 200km"],
    ["2026_10_100_1", "dart-populaire",         "2026-10-03", "", "separate_flow", "", ""],
    ["2026_10_200_1", "dart",                   "2026-10-03", "", "separate_flow", "", ""],
    ["2026_10_200_2", "winters",                "2026-10-17", "", "jotform",       "", "Winters 200km"],
    ["2026_11_200_1", "del-puerto-canyon",      "2026-11-07", "", "jotform",       "", "Fall Del Puerto Canyon 200km"],
    ["2026_11_100_1", "nov-dart-populaire",     "2026-11-14", "", "separate_flow", "", ""],
    ["2026_11_100_2", "black-friday-populaire", "2026-11-27", "", "jotform",       "", "Black Friday Populaire"],
    ["2026_12_200_1", "estero-americano",       "2026-12-05", "", "jotform",       "", "Estero Americano 200km"],
]

EVENTS_BY_YEAR = {
    2026: EVENTS_2026,
}


def get_client():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_annual.py <spreadsheet_id> [year]")
        print()
        print("Steps:")
        print("  1. Create a blank Google Sheet in your Drive named e.g. 'SFR_2026'")
        print("  2. Share it (Editor) with the service account email in credentials/service_account.json")
        print("  3. Pass the spreadsheet ID here")
        sys.exit(1)

    spreadsheet_id = sys.argv[1]
    year = int(sys.argv[2]) if len(sys.argv) > 2 else CURRENT_YEAR

    client = get_client()

    print(f"Opening spreadsheet {spreadsheet_id} for year {year}...")
    ss = client.open_by_key(spreadsheet_id)
    print(f"  Found: '{ss.title}'")

    ws = ss.sheet1
    ws.update_title(list(TABS.keys())[0])
    for tab_name in list(TABS.keys())[1:]:
        ss.add_worksheet(title=tab_name, rows=2000, cols=60)

    print("Setting up tabs...")

    for tab_name, headers in TABS.items():
        ws = ss.worksheet(tab_name)
        if headers:
            ws.update([headers], "A1")
            format_sheet_headers(ws, num_cols=len(headers))
        ss.batch_update({"requests": [{
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws.id,
                    "gridProperties": {"frozenRowCount": 1}
                },
                "fields": "gridProperties.frozenRowCount"
            }
        }]})

        # Add notes to tabs with special edit rules
        if tab_name == AnnualTab.REGISTRATIONS:
            ws.insert_note("A1",
                "Backend table. Do not edit existing rows.\n"
                "To manually register a rider: append a new row with rusa_id, "
                "event_id, status (X/Y/V/W), waiver_submitted (TRUE/FALSE), "
                "leave submission_id blank, and set added_by to your name.")
        elif tab_name == AnnualTab.RIDERS_VIEW:
            ws.update([["Auto-generated — do not edit. Regenerated on every ingest run."]], "A1")
        elif tab_name == AnnualTab.SUMMARY:
            ws.insert_note("A1", "Auto-generated — do not edit. Regenerated on every ingest run.")

        print(f"  {tab_name}: created")

    # Seed events for this year
    events_seed = EVENTS_BY_YEAR.get(year)
    if events_seed:
        ws_events = ss.worksheet(AnnualTab.EVENTS)
        ws_events.update(events_seed, "A2")
        print(f"  events: {len(events_seed)} rows seeded")
    else:
        print(f"  events: no seed data for {year} — add events manually")

    print("\n" + "=" * 60)
    print(f"SFR_{year} set up successfully.")
    print(f"URL: {ss.url}")
    print(f"ID:  {ss.id}")
    print(f"\nNext: copy the ID into config.py → ANNUAL_SPREADSHEET_ID")
    print(f"Then: run scripts/ingest_membership.py and scripts/ingest_registration.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
