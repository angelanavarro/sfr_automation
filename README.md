# SFR Automation

Automation system for the [San Francisco Randonneurs](https://www.sfrandonneurs.org/) (SFR) cycling club. Eliminates manual copy/paste between Google Sheets by syncing Jotform submissions into a structured master spreadsheet and auto-generating per-event roster sheets.

---

## What it does

Every 4 hours (via GitHub Actions), the system:

1. Reads new membership sign-ups from the Jotform membership form → upserts into **SFR_Master** (`riders`, `memberships` tabs)
2. Reads new event registrations from the Jotform registration form → upserts into **SFR_2026** (`registrations` tab)
3. Regenerates the **riders_view** pivot (one row per rider, one column per event, membership flags)
4. Regenerates the **event_summary** tab (registration counts and membership flag tallies per event)
5. Updates all existing per-event roster sheets; creates new ones for events within the next 30 days

---

## Architecture

### Spreadsheets

| Spreadsheet | Purpose |
|-------------|---------|
| **SFR_Master** | Permanent cross-year data: riders, SFR memberships, RUSA memberships, routes |
| **SFR_2026** | Annual data: events calendar, registrations, riders_view, event_summary |
| **Per-event sheets** | Auto-generated per ride: Roster, Full Roster, Worker's Ride, Waiver Checklist, Draft Results |
| **M1** (Jotform) | Membership form responses — read-only source |
| **R1** (Jotform) | Registration form responses — read-only source |

### Data flow

```
M1 (Jotform membership) ──► ingest_membership.py ──► SFR_Master: riders, memberships
                                                   └──► SFR_2026:  riders_view (refresh)

R1 (Jotform registration) ─► ingest_registration.py ─► SFR_2026:  registrations
                                                     └──► SFR_2026:  riders_view, event_summary

                              generate_event_sheets.py ─► Per-event Google Sheets
```

### Registration status codes

| Code | Meaning |
|------|---------|
| `X` | Paid registration |
| `Y` | Free registration |
| `V` | Volunteer — rides on event day, fee waived |
| `W` | Worker's ride — volunteers on event day, rides the route on `worker_ride_date` |
| `C` | Cancelled — excluded from all rosters |

### Membership flags (color-coded in sheets)

| Color | Meaning |
|-------|---------|
| Yellow RUSA# cell | Rider has no SFR membership for the current year |
| Orange RUSA# cell | Rider has no current RUSA membership (or it has expired) |

---

## Repository layout

```
config.py                        # All IDs, tab names, column indices, status codes
utils.py                         # Shared formatting helpers (headers, conditional formatting)

scripts/
  ingest_membership.py           # M1 → SFR_Master riders + memberships
  ingest_registration.py         # R1 → SFR_2026 registrations; regenerates riders_view + event_summary
  generate_event_sheets.py       # Creates/updates per-event Google Sheets
  create_event_sheets_oauth.py   # One-time OAuth script to create event sheets (Drive quota workaround)
  create_master.py               # One-time setup: initialise SFR_Master
  create_annual.py               # One-time setup: initialise SFR_YYYY annual sheet
  check_sources.py               # Diagnostic: verify M1/R1 are accessible

docs/
  admin-guide.md                 # Non-technical guide for the events admin

data_model.md                    # Full schema reference
.github/workflows/ingest.yml     # GitHub Actions cron (every 4 hours)
requirements.txt
```

---

## Setup (first time)

### Prerequisites

- Python 3.11+
- A Google Cloud project with the Sheets API and Drive API enabled
- A service account with a downloaded JSON key → save as `credentials/service_account.json`
- The service account email shared (Editor) on SFR_Master, SFR_2026, and the Events Drive folder

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Google Sheets setup (one time per year)

```bash
# 1. Create SFR_Master (share it with the service account first)
python scripts/create_master.py <spreadsheet_id>
# → copy printed ID into config.py → MASTER_SPREADSHEET_ID

# 2. Create SFR_YYYY annual sheet (share it with the service account first)
python scripts/create_annual.py <spreadsheet_id> 2026
# → copy printed ID into config.py → ANNUAL_SPREADSHEET_ID

# 3. Share M1 and R1 Jotform sheets with the service account (Viewer)
# → verify access
python scripts/check_sources.py
```

### GitHub Actions setup

1. Push this repo to GitHub
2. Go to **Settings → Secrets → Actions** and add:
   - `SERVICE_ACCOUNT_JSON` — paste the full contents of `credentials/service_account.json`
3. The workflow (`.github/workflows/ingest.yml`) runs automatically every 4 hours, or trigger it manually from the Actions tab

### Creating per-event sheets (first time or new events)

The service account cannot create files in Google Drive due to quota limits. Use the OAuth script once to create sheets for upcoming events:

```bash
# Requires credentials/oauth_client.json — create OAuth 2.0 Desktop credentials
# in Google Cloud Console → APIs & Services → Credentials
python scripts/create_event_sheets_oauth.py --days 180
```

After initial creation, `generate_event_sheets.py` will keep existing sheets updated automatically.

---

## Running manually

```bash
source venv/bin/activate

python scripts/ingest_membership.py      # sync membership data
python scripts/ingest_registration.py    # sync registrations + refresh pivot views
python scripts/generate_event_sheets.py  # update event roster sheets (default: 14-day window)
python scripts/generate_event_sheets.py --days 60  # wider window, e.g. for new-season setup
```

---

## Configuration (`config.py`)

| Constant | Description |
|----------|-------------|
| `MASTER_SPREADSHEET_ID` | SFR_Master Google Sheet ID |
| `ANNUAL_SPREADSHEET_ID` | Current year's annual sheet ID |
| `CURRENT_YEAR` | Update each January |
| `M1_SPREADSHEET_ID` | Jotform membership responses sheet |
| `R1_SPREADSHEET_ID` | Jotform registration responses sheet |
| `EVENTS_FOLDER_ID` | Google Drive folder ID for per-event sheets |

---

## Key design decisions

- **Google Sheets is the UI** — all data lives in Sheets; the scripts are invisible plumbing
- **Read-only sources** — M1 and R1 are never written to; only SFR_Master, SFR_2026, and event sheets are modified
- **Upsert pattern** — all ingest is idempotent; re-running never duplicates data
- **Batch API calls** — all writes use `batch_update` / `append_rows` to stay under Sheets API quota
- **15-second throttle** between event sheet updates to avoid 429 errors
- **Service account Drive quota workaround** — event sheets must be created by a user account (OAuth); the service account can update them once they exist
- **Auto-generated views** — `riders_view`, `event_summary`, `memberships_view` are cleared and rewritten on every run; do not edit them manually

---

## Year-start checklist

1. Update `CURRENT_YEAR` in `config.py`
2. Create a new blank Google Sheet named `SFR_YYYY`, share with service account
3. Run `python scripts/create_annual.py <id> YYYY` and update `ANNUAL_SPREADSHEET_ID` in `config.py`
4. Run `python scripts/create_event_sheets_oauth.py --days 365` to pre-create event sheets
5. Update the `SERVICE_ACCOUNT_JSON` secret if credentials were rotated
