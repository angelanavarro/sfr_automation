"""
Sets up the SFR master spreadsheet (permanent, cross-year data).

Rather than creating a new spreadsheet (which would land in the service account's
Drive and hit quota limits), this script takes an existing blank spreadsheet ID
that you create in your own Google Drive and share with the service account.

Steps before running:
  1. Go to drive.google.com and create a new blank Google Sheet named "SFR_Master"
  2. Share it with the service account email (Editor access)
     The service account email is in credentials/service_account.json → "client_email"
  3. Copy the spreadsheet ID from its URL and pass it as an argument below

Usage:
    python scripts/create_master.py <spreadsheet_id>
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import gspread
from google.oauth2.service_account import Credentials
from config import CREDENTIALS_FILE, MasterTab
from utils import format_sheet_headers

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

TABS = {
    MasterTab.ROUTES: [
        "route_id", "name", "distance_km", "fixed_course", "event_type", "notes"
    ],
    MasterTab.RIDERS: [
        "rusa_id", "first_name", "last_name", "email", "phone",
        "backup_contact", "backup_phone", "address", "city", "state", "zip", "country"
    ],
    MasterTab.MEMBERSHIPS: [
        "rusa_id", "year", "status"
    ],
    MasterTab.RUSA: [
        "rusa_id", "expiration_date", "club", "snapshot_date"
    ],
    MasterTab.EMAIL_LISTS: [
        "email", "list_name"
    ],
}

ROUTES_SEED = [
    # route_id, name, distance_km, fixed_course, event_type, notes
    ["point-reyes-populaire",  "January Point Reyes Populaire", 118, True,  "populaire", ""],
    ["dillon-beach",           "Dillon Beach",                  200, True,  "brevet",    ""],
    ["del-puerto-canyon",      "Del Puerto Canyon",             200, True,  "brevet",    ""],
    ["healdsburg",             "Healdsburg",                    300, True,  "brevet",    ""],
    ["two-rock-valley-ford",   "Two Rock-Valley Ford",          200, True,  "brevet",    ""],
    ["womens-populaire",       "SFR Women's Populaire",         108, True,  "populaire", ""],
    ["russian-river",          "Russian River",                 200, True,  "brevet",    ""],
    ["hopland",                "Hopland",                       400, True,  "brevet",    ""],
    ["fault-line",             "Fault Line",                    200, True,  "brevet",    ""],
    ["marin-mountains",        "Marin Mountains",               200, True,  "brevet",    ""],
    ["mendocino-coast",        "Mendocino Coast",               600, True,  "brevet",    ""],
    ["laguna-lake",            "Laguna Lake",                   200, True,  "brevet",    ""],
    ["big-rock-tocaloma",      "Big Rock-Tocaloma Populaire",   130, True,  "populaire", ""],
    ["old-cazadero",           "Old Cazadero",                  300, True,  "brevet",    ""],
    ["freestone-breadrun",     "Freestone Breadrun",            200, True,  "brevet",    ""],
    ["king-ridge",             "King Ridge",                    400, True,  "brevet",    ""],
    ["mt-hamilton",            "Mt. Hamilton",                  200, True,  "brevet",    ""],
    ["orr-springs",            "Orr Springs",                   600, True,  "brevet",    ""],
    ["lucas-valley",           "Lucas Valley",                  111, True,  "populaire", ""],
    ["booneville-lollipop",    "Booneville Lollipop",           300, True,  "brevet",    ""],
    ["sf-to-cloverdale",       "SF to Cloverdale",              200, True,  "brevet",    ""],
    ["cloverdale-to-sf",       "Cloverdale to SF",              200, True,  "brevet",    ""],
    ["coleman-valley",         "Coleman Valley",                200, True,  "brevet",    ""],
    ["winters",                "Winters",                       200, True,  "brevet",    ""],
    ["estero-americano",       "Estero Americano",              200, True,  "brevet",    ""],
    ["black-friday-populaire", "Metin's Black Friday Populaire",100, True,  "populaire", ""],
    ["fleche",                 "Bruce Berg Fleche NorCal",      480, False, "fleche",    ""],
    ["dart",                   "SFR Fall DART",                 200, False, "dart",      ""],
    ["dart-populaire",         "SFR FALL DART Populaire",       100, False, "populaire", ""],
    ["nov-dart-populaire",     "SFR November DART Populaire",   100, False, "populaire", ""],
]


def get_client():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def setup(ss):
    tab_names = list(TABS.keys())

    # Rename the default Sheet1 to the first tab name
    first_ws = ss.sheet1
    first_ws.update_title(tab_names[0])

    # Add remaining tabs
    for tab_name in tab_names[1:]:
        ss.add_worksheet(title=tab_name, rows=2000, cols=26)

    # Write headers and freeze row 1
    for tab_name, headers in TABS.items():
        ws = ss.worksheet(tab_name)
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
        print(f"  {tab_name}: headers written")

    # Seed routes
    ws_routes = ss.worksheet(MasterTab.ROUTES)
    ws_routes.update(ROUTES_SEED, "A2")
    print(f"  routes: {len(ROUTES_SEED)} rows seeded")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_master.py <spreadsheet_id>")
        print()
        print("Steps:")
        print("  1. Create a blank Google Sheet in your Drive named 'SFR_Master'")
        print("  2. Share it (Editor) with the service account email in credentials/service_account.json")
        print("  3. Copy the spreadsheet ID from the URL and pass it here")
        sys.exit(1)

    spreadsheet_id = sys.argv[1]
    client = get_client()

    print(f"Opening spreadsheet {spreadsheet_id}...")
    ss = client.open_by_key(spreadsheet_id)
    print(f"  Found: '{ss.title}'")

    print("Setting up tabs and seeding data...")
    setup(ss)

    print("\n" + "=" * 60)
    print("SFR_Master set up successfully.")
    print(f"URL: {ss.url}")
    print(f"ID:  {ss.id}")
    print("\nNext: copy the ID into config.py → MASTER_SPREADSHEET_ID")
    print("Then: run scripts/create_annual.py <spreadsheet_id> for the current year.")
    print("=" * 60)


if __name__ == "__main__":
    main()
