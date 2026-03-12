# SFR Automation — Claude Context

## Project summary

Python automation for the San Francisco Randonneurs (SFR) cycling club. Syncs Jotform form responses into Google Sheets and auto-generates per-event roster spreadsheets. The human-readable interface is entirely Google Sheets — no database, no web app.

**Primary developer:** Angelita
**Events admin (non-technical end user):** Rob — cannot run Python scripts; interacts only via Google Sheets
**Current year:** 2026 (update `CURRENT_YEAR` in `config.py` each January)

---

## Repo layout

```
config.py                        # All IDs, tab/column names, status codes — start here
utils.py                         # Shared formatting: format_sheet_headers(), apply_membership_flags()

scripts/
  ingest_membership.py           # M1 → SFR_Master (riders, memberships tabs)
  ingest_registration.py         # R1 → SFR_2026 (registrations); regenerates riders_view + event_summary
  generate_event_sheets.py       # Creates/updates per-event Google Sheets
  create_event_sheets_oauth.py   # One-time OAuth script (Drive quota workaround for new sheets)
  create_master.py               # One-time: initialise SFR_Master spreadsheet
  create_annual.py               # One-time: initialise SFR_YYYY annual spreadsheet
  check_sources.py               # Diagnostic: verify M1/R1 access

docs/admin-guide.md              # Non-technical guide for the events admin
data_model.md                    # Full schema reference
.github/workflows/ingest.yml     # GitHub Actions cron (every 4 hours)
```

---

## Spreadsheet IDs (in config.py)

| Variable | Sheet | Notes |
|----------|-------|-------|
| `MASTER_SPREADSHEET_ID` | SFR_Master | Permanent; riders, memberships, routes |
| `ANNUAL_SPREADSHEET_ID` | SFR_2026 | Recreated each year |
| `M1_SPREADSHEET_ID` | Jotform membership sheet | Read-only source |
| `R1_SPREADSHEET_ID` | Jotform registration sheet | Read-only source |
| `EVENTS_FOLDER_ID` | Google Drive folder | Where per-event sheets live |

---

## Data flow

```
M1 (Jotform membership) ──► ingest_membership.py ──► SFR_Master: riders, memberships
                                                   └──► SFR_2026:  riders_view (refresh)

R1 (Jotform registration) ─► ingest_registration.py ─► SFR_2026:  registrations
                                                     └──► SFR_2026:  riders_view, event_summary

                              generate_event_sheets.py ─► Per-event Google Sheets
```

All ingest is **upsert/idempotent** — re-running never duplicates data.

---

## Tab structure

### SFR_Master
| Tab | Key | Description |
|-----|-----|-------------|
| `riders` | `rusa_id` | One row per rider |
| `memberships` | `rusa_id\|year` | SFR membership by year; status X=paid, Y=free |
| `memberships_view` | — | Auto-generated pivot: one row per rider, columns by year + sfr_member + rusa_member |
| `rusa_memberships` | `rusa_id` | Rob pastes fresh RUSA export here; columns: rusa_id, expiration_date, club, snapshot_date |
| `routes` | `route_id` | Reusable route definitions |
| `email_lists` | `email\|list_name` | Mailing lists (source TBD) |

### SFR_2026
| Tab | Key | Description |
|-----|-----|-------------|
| `events` | `event_id` | Calendar; Rob edits this to add events |
| `registrations` | `rusa_id\|event_id` | Normalized one-row-per-rider-per-event |
| `riders_view` | — | Auto-generated pivot: riders × events with membership flags |
| `event_summary` | — | Auto-generated: one row per event with count breakdowns |
| `volunteers` | `rusa_id\|event_id` | Volunteer shift details |

### Per-event sheets (one per event)
Created by `create_event_sheets_oauth.py` (first time), updated by `generate_event_sheets.py`.
Tabs: Roster, Full Roster, Worker's Ride, Waiver Checklist, Draft Results.

---

## Key constants and classes (config.py)

```python
class RegStatus:
    PAID      = "X"   # paid registration
    FREE      = "Y"   # free
    VOLUNTEER = "V"   # rides on event day, fee waived
    WORKERS   = "W"   # volunteers on event day, rides on worker_ride_date
    CANCELLED = "C"   # excluded from all rosters
    ACTIVE    = {"X", "Y", "V", "W"}

class EventCol:        # 0-based column indices for events tab
    EVENT_ID = 0; ROUTE_ID = 1; EVENT_DATE = 2; WORKER_RIDE_DATE = 3
    REGISTRATION_SOURCE = 4; COURSE_NOTES = 5; JOTFORM_COLUMN_NAME = 6; SHEET_URL = 7

class M1Col:           # 0-based column indices for Jotform membership sheet
    RUSA_ID = 8; SFR_MEMBERSHIP = 11  # (and others)

class R1Col:           # defined in ingest_registration.py
    RUSA_ID = 41; WAIVER = 48; SUBMISSION_ID = 49  # (and others)
```

---

## Shared utilities (utils.py)

- `format_sheet_headers(ws, num_cols, has_subheader=False)` — dark blue-grey header row, optional light subheader row
- `apply_membership_flags(ss, ws, header_rows=2)` — conditional formatting on column A (rusa_id): yellow = no SFR membership, orange = no/expired RUSA membership
- Color constants: `FLAG_YELLOW`, `HEADER_BG`, `HEADER_FG`, `SUBHEADER_BG`, `SUBHEADER_FG`

---

## Shared data loading pattern (ingest_registration.py)

`_load_annual_data(annual_ss, master_ss)` loads all heavy data once and returns a dict with `events`, `reg_by_rider`, `reg_by_event`, `rider_info`, `sfr_membership`, `rusa_membership`. Pass this dict to `regenerate_riders_view(..., data=data)` and `regenerate_summary_tab(..., data=data)` to avoid duplicate API calls.

---

## Known issues / constraints

- **Service account Drive quota**: The service account cannot create new Google Sheets files (Drive storage quota = 0). Workaround: `create_event_sheets_oauth.py` uses OAuth to create files as the user. Once created, the service account can update them. New events mid-year need this OAuth script run manually.
- **Sheets API write quota**: 60 writes/min. `generate_event_sheets.py` sleeps 15 seconds between events. Each event sheet update makes ~10 write calls.
- **Sheets API read quota**: 60 reads/min. `generate_event_sheets.py` only processes events within a 7-day lookback + 60-day lookahead window. Previously it updated ALL existing sheets (even months-old ones), causing 429 read errors. Do not change this back to "always update all sheets".
- **event_summary columns**: `event_id`, `event_date`, `route_id`, then counts (total/paid/free/volunteer/workers_ride/cancelled/waiver_submitted/no_sfr_member/no_rusa_member), then `sheet_url`.
- **R1 format**: Event cells contain full event name + price strings (e.g. `"Dillon Beach 200km $7.50"`), not status codes. Any non-empty, unrecognized cell value is normalized to `RegStatus.PAID`.
- **Waiver field**: R1 waiver column contains `"I agree"` (not `"yes"`/`"true"`). Handled in `parse_registrations()`.

---

## GitHub Actions

Workflow: `.github/workflows/ingest.yml`
Trigger: every 4 hours (`0 */4 * * *`) + manual `workflow_dispatch`
Secret required: `SERVICE_ACCOUNT_JSON` (full JSON content of `credentials/service_account.json`)

All three steps run independently with `continue-on-error: true`; a final `Report failures` step fails the job if any script exited non-zero (so GitHub sends failure notifications).

---

## Pending work

- [ ] Activate GitHub Actions: push repo, add `SERVICE_ACCOUNT_JSON` secret
- [ ] Verify M1/R1 are shared with the service account: run `python scripts/check_sources.py`
- [ ] Investigate/fix service account Drive quota so `generate_event_sheets.py` can create new sheets without the OAuth workaround
- [ ] Determine source for `email_lists` tab in SFR_Master
- [ ] Share `docs/admin-guide.md` with the events admin
