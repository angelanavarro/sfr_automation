"""
Tests whether a set of credentials can create a new Google Sheet in EVENTS_FOLDER_ID.

Tries both credential types in order:
  1. Service account:  credentials/workspace_service_account.json  (if it exists)
  2. Service account:  credentials/service_account.json            (fallback)
  3. OAuth user token: credentials/oauth_token.json                (if --oauth flag given)

On success the test sheet is immediately deleted.
On failure (403) it prints the quota error message.

Usage:
    python scripts/test_drive_quota.py                   # test service account
    python scripts/test_drive_quota.py --oauth           # test OAuth user account
    python scripts/test_drive_quota.py --creds path.json # test specific credentials file
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse

import gspread
from google.oauth2.service_account import Credentials as SACredentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import EVENTS_FOLDER_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

WORKSPACE_SA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials", "workspace_service_account.json")
DEFAULT_SA_FILE   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials", "service_account.json")
OAUTH_TOKEN_FILE  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials", "oauth_token.json")


def get_service_account_client(creds_file):
    creds = SACredentials.from_service_account_file(creds_file, scopes=SCOPES)
    return gspread.authorize(creds), build("drive", "v3", credentials=creds), creds.service_account_email


def get_oauth_client():
    creds = OAuthCredentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return gspread.authorize(creds), build("drive", "v3", credentials=creds), "(OAuth user)"


def test_create(client, drive_service, identity):
    print(f"\nIdentity: {identity}")

    # Test 1: create a sheet via Drive API with supportsAllDrives=True
    print("Test 1: creating a test sheet (supportsAllDrives=True)...")
    try:
        metadata = {
            "name": "__sfr_quota_test__",
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
        if EVENTS_FOLDER_ID:
            metadata["parents"] = [EVENTS_FOLDER_ID]
        file = drive_service.files().create(
            body=metadata,
            supportsAllDrives=True,
            fields="id,webViewLink",
        ).execute()
        ss_id  = file["id"]
        ss_url = file.get("webViewLink", f"https://docs.google.com/spreadsheets/d/{ss_id}")
        print(f"  OK — created: {ss_url}")
    except Exception as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        print(f"  FAILED (HTTP {status}): {e}")
        if status == "403":
            print("  -> Still failing. Make sure EVENTS_FOLDER_ID is a Shared Drive")
            print("     and the service account is a member (Content Manager or above).")
        return

    # Test 2: delete the test sheet
    print("Test 2: deleting test sheet...")
    try:
        drive_service.files().delete(fileId=ss_id, supportsAllDrives=True).execute()
        print("  OK — deleted.")
    except Exception as e:
        print(f"  Could not delete test sheet (delete manually): {e}")
        print(f"  Sheet URL: {ss_url}")

    print("\nResult: this account CAN create Google Sheets in the Shared Drive.")
    print("Next step: confirm EVENTS_FOLDER_ID in config.py is set to the Shared Drive ID.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--oauth", action="store_true", help="Test OAuth user token instead of service account")
    parser.add_argument("--creds", help="Path to a specific service account JSON file to test")
    args = parser.parse_args()

    if args.oauth:
        if not os.path.exists(OAUTH_TOKEN_FILE):
            print(f"ERROR: {OAUTH_TOKEN_FILE} not found. Run create_event_sheets_oauth.py first to authenticate.")
            sys.exit(1)
        client, drive_service, identity = get_oauth_client()
    else:
        if args.creds:
            creds_file = args.creds
        elif os.path.exists(WORKSPACE_SA_FILE):
            creds_file = WORKSPACE_SA_FILE
            print(f"Using Workspace service account: {WORKSPACE_SA_FILE}")
        else:
            creds_file = DEFAULT_SA_FILE
            print(f"Using default service account: {DEFAULT_SA_FILE}")

        try:
            client, drive_service, identity = get_service_account_client(creds_file)
        except Exception as e:
            print(f"ERROR loading credentials: {e}")
            sys.exit(1)

    test_create(client, drive_service, identity)


if __name__ == "__main__":
    main()
