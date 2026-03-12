# SFR Automation — Admin Guide

This document explains how the new system works and answers common questions.
The goal is simple: **less copy/paste, and the data stays up to date automatically.**

---

## What happens automatically

Every 4 hours, the system runs automatically and:

1. Reads new membership sign-ups from the Jotform membership form
2. Reads new event registrations from the Jotform registration form
3. Updates the master spreadsheet (SFR_Master) with new/updated rider and membership data
4. Updates the annual spreadsheet (SFR_2026) with new/updated registrations
5. Refreshes the **riders_view** tab so you can see who is signed up for what
6. Updates event sheets for rides within the past 7 days and the next 14 days; creates new event sheets for upcoming rides that don't have one yet

You don't need to do anything. If a rider signs up or updates their info, it will appear in the sheets within 4 hours.

---

## Your spreadsheets

| Spreadsheet | What it's for |
|-------------|---------------|
| **SFR_Master** | Permanent data: all riders, membership history, routes |
| **SFR_2026** | This year's data: events, registrations, riders_view, event_summary |
| **Per-event sheets** | One sheet per upcoming event with roster, waivers, results |

### SFR_Master tabs at a glance

| Tab | What it contains |
|-----|-----------------|
| **riders** | One row per rider — name, email, phone, emergency contact, address |
| **memberships** | SFR membership by year — one row per rider per year |
| **memberships_view** | Auto-generated: full membership history at a glance, one row per rider |
| **rusa_memberships** | Paste fresh RUSA export here to update RUSA membership status |
| **routes** | Reusable route definitions — add new routes here |

### SFR_2026 tabs at a glance

| Tab | What it contains |
|-----|-----------------|
| **events** | One row per event — add new events here |
| **registrations** | Backend table — do not edit directly (except to add manual registrations) |
| **riders_view** | Pivot: one row per rider, one column per event — for checking sign-ups at a glance |
| **event_summary** | One row per event with count breakdowns — use this for at-a-glance event stats |
| **volunteers** | Volunteer shift assignments |

### Per-event sheet tabs at a glance

Each event gets its own spreadsheet with these tabs:

| Tab | What it contains |
|-----|-----------------|
| **Roster** | RUSA#, name, status — no contact info; main section + worker's ride section |
| **Full Roster** | Complete contact info for all registered riders |
| **Worker's Ride** | Contact info for W-status riders only (volunteer on event day, rides separately) |
| **Waiver Checklist** | Who has and hasn't submitted their waiver |
| **Draft Results** | Pre-populated rider list with blank columns for finish times |

---

## Frequently Asked Questions

### What happens when a new event is added?

1. Add a row to the **events** tab in SFR_2026 with the event details
2. Fill in the `jotform_column_name` field with the exact column header text from the registration form
3. That's it — the next automatic run will start picking up registrations for that event

If the event doesn't use Jotform (like the Fleche or DART), set `registration_source` to `separate_flow` and leave `jotform_column_name` blank.

---

### What happens when a mid-week ride is added?

Same as above — add a row to the events tab once you decide the ride is happening and have added it to Jotform. The system will pick up registrations automatically.

---

### How do I add a new route to SFR_Master?

Open **SFR_Master** and go to the **routes** tab. Add a new row at the bottom with these columns:

| Column | What to enter |
|--------|--------------|
| route_id | A short, unique slug in lowercase with hyphens (e.g. `mt-tam-populaire`). This is what you'll put in the `route_id` column of the events tab when you schedule a ride on this route. |
| name | Full display name (e.g. `Mt. Tam Populaire`) |
| distance_km | Distance in kilometers |
| fixed_course | `TRUE` if the route is fixed (same every time), `FALSE` for variable formats like Fleche or DART |
| event_type | One of: `brevet`, `populaire`, `fleche`, `dart` |
| notes | Any notes (optional) |

After adding the route, use its `route_id` when filling in the events tab for any ride that uses it.

---

### How do I manually register a rider for an event?

Go to the **registrations** tab in SFR_2026 and add a new row at the bottom:

| Column | What to enter |
|--------|--------------|
| rusa_id | Rider's RUSA number |
| event_id | The event ID (e.g. `2026_03_200_1`) |
| status | `X` = paid, `Y` = free, `V` = volunteer, `W` = worker's ride |
| waiver_submitted | `TRUE` or `FALSE` |
| submission_id | Leave blank |
| registered_at | Today's date |
| added_by | Your name |

The riders_view will update on the next automatic run (within 4 hours).

---

### How do I cancel a registration?

Find the rider's row in the **registrations** tab and change their `status` to `C`. They will be removed from event rosters on the next run.

---

### How do I create an event sheet manually?

Event sheets are created automatically for rides in the next 14 days. If you need one sooner:

1. Create a blank Google Sheet in your Drive and name it after the event (e.g. `2026_05_300_1`)
2. Share it (Editor) with the service account email — ask Angela for that address
3. Copy the sheet URL and paste it into the **sheet_url** column for that event in the **events** tab of SFR_2026
4. The next automatic run (within 4 hours) will populate all tabs with the current roster

If you need it right away, ask Angela to trigger a manual run.

---

### A rider's information changed (new phone number, email, etc.). What do I do?

Nothing — if the rider resubmits the Jotform membership form with updated info, the system will update their record automatically. If you need to update it immediately, find their row in the **riders** tab of SFR_Master and edit it directly.

---

### How do I check if a rider is a current SFR member?

Open **riders_view** in SFR_2026. The `sfr_member` column shows their membership status for this year:
- `X` = paid member
- `Y` = free membership
- blank = no membership on record for 2026

You can also check **memberships_view** in SFR_Master (tab is right after the riders tab) to see a rider's full membership history by year.

Riders missing an SFR membership for the current year are highlighted **yellow** in the RUSA# cell in riders_view and on all event sheets.

---

### How do I check if a rider's RUSA membership is current?

The `rusa_member` column in **riders_view** (and **memberships_view** in SFR_Master) shows:
- `X` = RUSA membership is current
- blank = no RUSA membership on record, or it has expired

Riders with a blank `rusa_member` are highlighted **orange** in the RUSA# cell in riders_view.

---

### A rider paid their SFR membership but is still showing yellow. How do I fix it?

If the rider hasn't resubmitted the Jotform membership form, their record won't update automatically. You can add it manually:

1. Open **SFR_Master** and go to the **memberships** tab
2. Add a new row at the bottom:

| Column | What to enter |
|--------|--------------|
| rusa_id | Rider's RUSA number |
| year | Current year (e.g. `2026`) |
| status | `X` = paid, `Y` = free |

3. The yellow highlight will clear on the next automatic run (within 4 hours)

---

### A rider's RUSA membership is current but they're showing orange. How do I fix it?

The RUSA data only updates when you paste a fresh export into the **rusa_memberships** tab. If a rider renewed recently, their record won't reflect it until then.

If you need to clear the orange flag for a specific rider right away, you can add a row for them manually:

1. Open **SFR_Master** and go to the **rusa_memberships** tab
2. Add a new row:

| Column | What to enter |
|--------|--------------|
| rusa_id | Rider's RUSA number |
| expiration_date | Their expiration date (YYYY-MM-DD) |
| club | `San Francisco Randonneurs` |
| snapshot_date | Today's date |

3. The orange highlight will clear on the next automatic run (within 4 hours)

---

### The data looks wrong or out of date. What do I do?

The system syncs every 4 hours. If something looks wrong after that window, contact Angela — she can check the automation logs and re-run the sync manually.

---

### What is the event_summary tab?

It's a quick overview of every event's registration counts. Columns are:

| Column | Meaning |
|--------|---------|
| event_id, event_date, route_id | Which event and which route |
| total | Active (non-cancelled) registrations |
| paid | X status riders |
| free | Y status riders |
| volunteer | V status riders (rides on event day, fee waived) |
| workers_ride | W status riders (volunteers on event day) |
| cancelled | C status riders |
| waiver_submitted | How many active riders have submitted their waiver |
| no_sfr_member | Active riders with no SFR membership for this year |
| no_rusa_member | Active riders with no current RUSA membership |
| sheet_url | Link to the per-event roster sheet |

It's read-only and regenerated automatically — don't edit it directly.

---

### What is the riders_view tab?

It's an overview of all riders registered for any event this year. Columns are:
- Rider info: RUSA#, name, email
- Membership status: SFR and RUSA
- One column per event date — shows their registration status (X/Y/V/W) or blank if not registered

It's read-only and regenerated automatically — don't edit it directly.

---

### What do the registration status codes mean?

| Code | Meaning |
|------|---------|
| X | Paid registration |
| Y | Free registration |
| V | Volunteer — rides on event day, fee waived |
| W | Worker's ride — volunteers on event day, rides on the worker ride date |
| C | Cancelled — excluded from all rosters |

---

### What do the colored cells on event sheets mean?

On each event sheet (Roster, Full Roster), the **RUSA# cell** for a rider may be highlighted:

| Color | Meaning |
|-------|---------|
| Yellow | Rider has no SFR membership for 2026 |
| Orange | Rider has no RUSA membership, or it has expired |

These colors are refreshed automatically every time the event sheet is updated (every 4 hours for events in the next 14 days). The "Total Riders" and "Total Workers" counts shown in the sheet are live spreadsheet formulas — they will automatically adjust if you manually add or remove a rider from the sheet.

---

### What is the difference between SFR_Master and SFR_2026?

- **SFR_Master** is permanent. It has every rider who has ever registered, their full membership history, and the list of routes. It carries over year to year.
- **SFR_2026** is for this year only. It has this year's events, registrations, and roster views. A new annual spreadsheet is created each January.

---

### How do I update the RUSA membership data?

When you receive a fresh export from RUSA, paste it directly into the **rusa_memberships** tab in SFR_Master (replacing the existing data). The columns are:

| Column | What to paste |
|--------|--------------|
| rusa_id | RUSA number |
| expiration_date | Expiration date (YYYY-MM-DD) |
| club | Club name |
| snapshot_date | Today's date |

The system will pick it up on the next automatic run and update the `rusa_member` column in riders_view and in each event sheet.

> **Future improvement:** This step could be fully automated if RUSA provides a data export link or API. Noted as a future enhancement.

---

### What happens at the start of a new year?

Angela runs a setup script that creates the new annual spreadsheet (e.g. SFR_2027), seeds it with the event calendar, and updates the configuration. SFR_Master carries over automatically — no data is lost.

---

## Year-end transition (December–January)

Around December 16, the 14-day lookahead window starts reaching into January of the following year. The system handles this automatically — both the current year (SFR_2026) and next year (SFR_2027) can be active at the same time during this window.

### What Angela does (by December 1)

1. Fill in the 2027 event calendar in `create_annual.py` (`EVENTS_2027 = [...]`)
2. Create a blank Google Sheet named `SFR_2027` in Google Drive
3. Share it (Editor) with the service account email (from `credentials/service_account.json` → `client_email`)
4. Run: `python scripts/create_annual.py <new_sheet_id> 2027`
5. Verify the 5 tabs exist in the new sheet (events, registrations, riders_view, event_summary, volunteers)
6. Copy the sheet ID into `config.py` → `ANNUAL_SPREADSHEET_IDS[2027]`
7. Commit and push — automation picks up both sheets on the next run (within 4 hours)
8. Confirm riders_view and event_summary populate in SFR_2027 after the next run
9. **In January:** Update `CURRENT_YEAR = 2027` in `config.py` — this controls which year's SFR membership is shown in riders_view and event sheets
10. **In February:** Set `ANNUAL_SPREADSHEET_IDS[2026]` back to `""` once all December 2026 events are more than 7 days in the past

### What Rob does

Nothing — January 2027 event sheets appear automatically once registrations exist for those events.

### Notes

- **SFR membership flags in December:** If a rider has a 2027 SFR membership but not 2026, they will show yellow on January 2027 event sheets until `CURRENT_YEAR` is updated to 2027 in January. This is expected and resolves automatically.
- **API quota:** Having two active sheets roughly doubles the number of API calls per run, but this is still well within the 60 reads/min limit.
- **Removing SFR_2026 from config:** Wait until February 2027, once all December 2026 events are past the 7-day lookback window. Set `ANNUAL_SPREADSHEET_IDS[2026] = ""` to stop processing it.
