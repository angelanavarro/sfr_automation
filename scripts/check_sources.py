"""
Quick diagnostic to verify M1 and R1 are accessible and have the expected structure.
Run after updating config.py with the real spreadsheet IDs.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import gspread
from google.oauth2.service_account import Credentials
from config import CREDENTIALS_FILE, M1_SPREADSHEET_ID, M1_SHEET_NAME, R1_SPREADSHEET_ID, R1_SHEET_NAME, M1Col
from scripts.ingest_registration import R1Col

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def check(label, ss_id, sheet_name, expected_cols):
    print(f"\n--- {label} ---")
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        ws = client.open_by_key(ss_id).worksheet(sheet_name)
        rows = ws.get_all_values()
        headers = rows[0] if rows else []
        data_rows = rows[1:] if len(rows) > 1 else []
        print(f"  OK: {len(data_rows)} data rows, {len(headers)} columns")
        print(f"  Sheet: '{ws.title}'")
        for name, idx in expected_cols.items():
            val = headers[idx] if idx < len(headers) else "(out of range)"
            print(f"  col[{idx}] {name}: {repr(val)}")
    except Exception as e:
        print(f"  ERROR: {e}")

check("M1 (membership form)", M1_SPREADSHEET_ID, M1_SHEET_NAME, {
    "FIRST_NAME":     M1Col.FIRST_NAME,
    "LAST_NAME":      M1Col.LAST_NAME,
    "EMAIL":          M1Col.EMAIL,
    "RUSA_ID":        M1Col.RUSA_ID,
    "SFR_MEMBERSHIP": M1Col.SFR_MEMBERSHIP,
    "SUBMISSION_ID":  M1Col.SUBMISSION_ID,
})

check("R1 (registration form)", R1_SPREADSHEET_ID, R1_SHEET_NAME, {
    "FIRST_NAME":    R1Col.FIRST_NAME,
    "LAST_NAME":     R1Col.LAST_NAME,
    "EMAIL":         R1Col.EMAIL,
    "RUSA_ID":       R1Col.RUSA_ID,
    "WAIVER":        R1Col.WAIVER,
    "SUBMISSION_ID": R1Col.SUBMISSION_ID,
})
