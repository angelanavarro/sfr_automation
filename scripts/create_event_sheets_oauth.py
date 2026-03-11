"""
ONE-TIME SCRIPT — creates per-event spreadsheets owned by your Google account
for all events in the next 6 months, then shares each with the service account.

Use this instead of generate_event_sheets.py until the service account Drive
quota issue is resolved.

Prerequisites:
  1. pip install google-auth-oauthlib google-api-python-client
  2. Create OAuth 2.0 Desktop credentials in Google Cloud Console
     (APIs & Services → Credentials → Create → OAuth 2.0 Client ID → Desktop App)
  3. Download JSON → save as credentials/oauth_client.json
  4. Run this script — a browser window will open for login on first run.
     Your token is cached in credentials/oauth_token.json for future runs.

Usage:
    python scripts/create_event_sheets_oauth.py [--days 180]
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import argparse
from datetime import date, timedelta

import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials as SACredentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import (
    CREDENTIALS_FILE, MASTER_SPREADSHEET_ID, ANNUAL_SPREADSHEET_ID,
    EVENTS_FOLDER_ID, AnnualTab, EventCol,
)
from scripts.generate_event_sheets import (
    setup_event_spreadsheet, load_riders, load_all_registrations, load_memberships,
    write_roster_tab, write_full_roster_tab, write_workers_ride_tab,
    write_waiver_tab, write_draft_results_tab,
)

OAUTH_CLIENT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials", "oauth_client.json")
OAUTH_TOKEN_FILE  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials", "oauth_token.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_oauth_client():
    """Authenticate as the user via OAuth, caching the token for future runs."""
    creds = None

    if os.path.exists(OAUTH_TOKEN_FILE):
        creds = OAuthCredentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CLIENT_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(OAUTH_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("  OAuth token saved to credentials/oauth_token.json")

    return gspread.authorize(creds), build("drive", "v3", credentials=creds)


def get_service_account_client():
    """Authenticated service account client for reading SFR_2026 and SFR_Master."""
    creds = SACredentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return gspread.authorize(creds)


def get_service_account_email():
    with open(CREDENTIALS_FILE) as f:
        return json.load(f)["client_email"]


def load_upcoming_events(annual_ss, days):
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
        if today <= event_date <= cutoff:
            upcoming.append({
                "sheet_row":        i,
                "event_id":         row[EventCol.EVENT_ID],
                "event_date":       row[EventCol.EVENT_DATE],
                "sheet_url":        row[EventCol.SHEET_URL] if len(row) > EventCol.SHEET_URL else "",
            })
    return ws, upcoming


def share_with_service_account(drive_client, file_id, sa_email):
    """Grant the service account Editor access to a file."""
    drive_client.permissions().create(
        fileId=file_id,
        body={"type": "user", "role": "writer", "emailAddress": sa_email},
        fields="id",
    ).execute()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=180,
                        help="Create sheets for events within this many days (default: 180)")
    args = parser.parse_args()

    print("Authenticating with your Google account...")
    oauth_client, drive_client = get_oauth_client()

    print("Connecting to SFR spreadsheets (service account)...")
    sa_client  = get_service_account_client()
    sa_email   = get_service_account_email()
    annual_ss  = sa_client.open_by_key(ANNUAL_SPREADSHEET_ID)
    master_ss  = sa_client.open_by_key(MASTER_SPREADSHEET_ID)

    print(f"Loading events in the next {args.days} days...")
    ws_events, upcoming = load_upcoming_events(annual_ss, args.days)
    print(f"  {len(upcoming)} upcoming events found")

    print("Loading riders, memberships, and registrations...")
    rider_info    = load_riders(master_ss)
    flags         = load_memberships(master_ss)
    regs_by_event = load_all_registrations(annual_ss)

    for event in upcoming:
        print(f"\n{event['event_id']} ({event['event_date']})")

        regs = regs_by_event.get(event["event_id"], [])
        if not regs:
            print(f"  Skipping — no registrations yet")
            continue

        regs = sorted(regs, key=lambda x: rider_info.get(x[0], {}).get("last", "").lower())

        if event["sheet_url"]:
            print(f"  Sheet already exists, skipping creation")
            continue

        title = event["event_id"]
        print(f"  Creating '{title}'...")
        folder_id = EVENTS_FOLDER_ID if EVENTS_FOLDER_ID else None
        ss = oauth_client.create(title, folder_id=folder_id)
        setup_event_spreadsheet(ss)

        write_roster_tab(ss.worksheet("Roster"), regs, rider_info, flags)
        write_full_roster_tab(ss.worksheet("Full Roster"), regs, rider_info, flags)
        write_workers_ride_tab(ss.worksheet("Worker's Ride"), regs, rider_info)
        write_waiver_tab(ss.worksheet("Waiver Checklist"), regs, rider_info)
        write_draft_results_tab(ss.worksheet("Draft Results"), regs, rider_info)

        share_with_service_account(drive_client, ss.id, sa_email)
        print(f"  Shared with service account ({sa_email})")

        # Store sheet URL back in events tab (using service account which has Editor access)
        ws_events.update([[ss.url]], f"H{event['sheet_row']}")
        print(f"  Saved sheet_url → events tab row {event['sheet_row']}")
        print(f"  URL: {ss.url}")

    print("\nDone.")


if __name__ == "__main__":
    main()
