"""
Central configuration for SFR automation scripts.
"""

import os

# Path to Google service account credentials JSON
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials", "service_account.json")

# Source spreadsheet IDs — Jotform writes to these, our scripts only read them.
# Share these with the service account as Viewer.
M1_SPREADSHEET_ID = "1edosDQLm4_LuEUO6k8IgsvTxOdgXuNwxflA6KO5cZZk"
M1_SHEET_NAME     = "sheet1"

R1_SPREADSHEET_ID = "1-7FlT-vctfFPZ3xqJJi7iZkd8jfI_LfuvVvaDaU4c4A"
R1_SHEET_NAME     = "Form responses"


# Master spreadsheet ID (permanent, cross-year) — set after create_master.py is run
MASTER_SPREADSHEET_ID = "1j7lJrE6JqKyVdZ1HxZeE-HKQsnlibeneyqQvJEoDfQQ"

# Annual spreadsheet IDs (one per year) — keyed by year.
# During the December transition window, both the current and next year can be active simultaneously.
# Set to "" for years that don't have a sheet yet; get_active_annual_ids() skips empty entries.
ANNUAL_SPREADSHEET_IDS = {
    2026: "1Aq5JWZfNgOiKlX-Yn_Aflw85H6IMhuDstYaYkdlkS_4",  # SFR_2026
    2027: "",  # populate after running create_annual.py in November
}
CURRENT_YEAR = 2026


def get_active_annual_ids():
    """Return [(year, sheet_id)] for all non-empty annual IDs, sorted by year."""
    return [(year, sid) for year, sid in sorted(ANNUAL_SPREADSHEET_IDS.items()) if sid]


# Google Drive folder ID where per-event sheets are created.
# Create a folder in your Drive, share it (Editor) with the service account, paste the ID here.
EVENTS_FOLDER_ID = "10lQaSIVukVqCuPGNhd4-GUioigJQeovv"

# Master spreadsheet tab names (permanent data)
class MasterTab:
    ROUTES           = "routes"
    RIDERS           = "riders"
    MEMBERSHIPS      = "memberships"
    MEMBERSHIPS_VIEW = "memberships_view"
    RUSA             = "rusa_memberships"
    EMAIL_LISTS      = "email_lists"

# Annual spreadsheet tab names (per-year data)
class AnnualTab:
    EVENTS        = "events"
    REGISTRATIONS = "registrations"
    RIDERS_VIEW   = "riders_view"
    SUMMARY       = "event_summary"   # auto-generated stats per event
    VOLUNTEERS    = "volunteers"

# M1 column indices (0-based) for membership ingest
class M1Col:
    FIRST_NAME     = 0   # A: First Name
    LAST_NAME      = 1   # B: Last Name
    ADDRESS        = 2   # C: Street Address
    CITY           = 3   # D: City
    STATE          = 4   # E: State
    ZIP            = 5   # F: Postal/Zip Code
    PHONE          = 6   # G: Phone Number
    EMAIL          = 7   # H: E-mail
    RUSA_ID        = 8   # I: RUSA Number
    SFR_MEMBERSHIP = 11  # L: SFR membership (multi-year text field)
    SUBMISSION_ID  = 16  # Q: Submission ID

# Registration status codes
class RegStatus:
    PAID      = "X"  # Paid registration
    FREE      = "Y"  # Free registration
    VOLUNTEER = "V"  # Volunteer registration (rides on event day, fee waived)
    WORKERS   = "W"  # Worker's ride (volunteers on event day, rides on worker_ride_date)
    CANCELLED = "C"  # Cancelled — excluded from all rosters
    ACTIVE    = {"X", "Y", "V", "W"}  # any of these = rider is participating

# Column indices (0-based) for the annual events tab
class EventCol:
    EVENT_ID             = 0
    ROUTE_ID             = 1
    EVENT_DATE           = 2
    WORKER_RIDE_DATE     = 3
    REGISTRATION_SOURCE  = 4
    COURSE_NOTES         = 5
    JOTFORM_COLUMN_NAME  = 6  # exact header text in R1; empty for separate_flow events
    SHEET_URL            = 7  # URL of the generated per-event sheet (populated by generate_event_sheets.py)
