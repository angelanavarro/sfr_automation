# SFR Data Model

**Status:** Discovery & Planning
**Last updated:** March 2026

---

## Design Principles

- **R1** (Jotform registration responses) is the source of truth for event registrations
- **M1** (Jotform membership responses) is the source of truth for rider/membership data
- Routes (named courses) are defined once and reused year after year
- Events are scheduled instances of a route in a given year
- Google Sheets remains the human-readable interface; the master spreadsheet is the canonical store
- Per-event sheets (R4a, R4b) are auto-generated views, not manually maintained
- Manual registration entry is supported (admin adds row directly to `registrations`)

---

## Schema

### `routes`
A reusable ride definition. Either a fixed course (same roads every year) or a recurring
event format with a variable course defined fresh each year (Fleche, DART, etc.).

| Column | Type | Notes |
|--------|------|-------|
| `route_id` | TEXT PK | Slug, e.g. `dillon-beach`, `fleche`, `dart` |
| `name` | TEXT | Full name, e.g. "Dillon Beach" |
| `distance_km` | INTEGER | Actual distance; e.g. Lucas Valley = 111, populaires = 100 |
| `fixed_course` | BOOLEAN | `true` = same roads every year; `false` = course varies (Fleche/DART/etc.) |
| `event_type` | TEXT | `brevet`, `populaire`, `fleche`, `dart` |
| `notes` | TEXT | |

### `events`
A scheduled instance of a route in a specific year. Rob populates this when planning the
calendar. `route_id` may be null when the route is TBD. Two events can share a date
(different routes, different volunteers — each gets its own R4a/R4b).

| Column | Type | Notes |
|--------|------|-------|
| `event_id` | TEXT PK | Format: `YYYY_MM_distKM_inc` e.g. `2026_01_200_1` |
| `route_id` | TEXT FK → routes | Nullable until Rob decides (TBD events) |
| `year` | INTEGER | |
| `event_date` | DATE | |
| `worker_ride_date` | DATE | Date when W-status riders do the route; null if no worker's ride |
| `registration_source` | TEXT | `jotform`, `manual`, `separate_flow` |
| `course_notes` | TEXT | For non-fixed-course events: describe that year's specific route |

### `riders`
Canonical record for each person. Sourced from M1 via ingest script.
Admins may also add/edit records directly.

| Column | Type | Notes |
|--------|------|-------|
| `rusa_id` | INTEGER PK | RUSA membership number |
| `first_name` | TEXT | |
| `last_name` | TEXT | |
| `email` | TEXT | |
| `phone` | TEXT | |
| `backup_contact` | TEXT | Emergency contact name |
| `backup_phone` | TEXT | Emergency contact phone |
| `address` | TEXT | |
| `city` | TEXT | |
| `state` | TEXT | |
| `zip` | TEXT | |
| `country` | TEXT | |

### `memberships`
SFR membership by year. One row per (rider, year).
Sourced from M1 column `SFR membership` (multi-year text field), transformed on ingest.

| Column | Type | Notes |
|--------|------|-------|
| `rusa_id` | INTEGER FK → riders | |
| `year` | INTEGER | |
| `status` | TEXT | `X` = paid; `Y` = free |
| PRIMARY KEY | (rusa_id, year) | |

### `rusa_memberships`
Snapshot of the national RUSA database. Imported once per year (or on demand).

| Column | Type | Notes |
|--------|------|-------|
| `rusa_id` | INTEGER FK → riders | |
| `expiration_date` | DATE | |
| `club` | TEXT | e.g. "San Francisco Randonneurs" |
| `snapshot_date` | DATE | When this dump was imported |
| PRIMARY KEY | (rusa_id, snapshot_date) | |

### `registrations`
One row per (rider, event). Replaces the wide-column format in R2/R3.

| Column | Type | Notes |
|--------|------|-------|
| `rusa_id` | INTEGER FK → riders | |
| `event_id` | TEXT FK → events | |
| `status` | TEXT | See status codes below |
| `waiver_submitted` | BOOLEAN | Default false |
| `submission_id` | TEXT | Jotform submission ID; null for manual entries |
| `registered_at` | TIMESTAMP | |
| `added_by` | TEXT | `jotform`, or admin name for manual entries |
| PRIMARY KEY | (rusa_id, event_id) | |

**Registration status codes:**

| Code | Meaning | Rides on event day? | Gets credit? |
|------|---------|---------------------|--------------|
| `X` | Paid registration | Yes | Yes |
| `Y` | Free registration (fee waived) | Yes | Yes |
| `V` | Volunteer registration — volunteering at event, fee waived, rides on event day | Yes | Yes |
| `W` | Worker's ride — volunteering on event day, rides the route on `worker_ride_date` instead | No | Yes |
| `C` | Cancelled | No | No |

R4a/R4b rosters have two sections:
- **Main roster** (event day): status X, Y, V
- **Worker's ride roster**: status W — rides on `events.worker_ride_date`

All other views (waiver checklist, results, etc.) filter `WHERE status != 'C'`.

### `results`
Post-ride outcomes. Manually entered (currently done in R4b `Draft results` by Alan).

| Column | Type | Notes |
|--------|------|-------|
| `rusa_id` | INTEGER FK → riders | |
| `event_id` | TEXT FK → events | |
| `hours` | INTEGER | |
| `minutes` | INTEGER | |
| `dnf` | BOOLEAN | Did not finish |
| `start_time` | TIMESTAMP | |
| `finish_time` | TIMESTAMP | |
| `proof_of_passage` | BOOLEAN | EPP / brevet card received |
| PRIMARY KEY | (rusa_id, event_id) | |

### `volunteers`
Event staffing details. Currently in R6.
Note: `W` and `V` status in `registrations` indicate the rider is also volunteering —
`V` rides on event day with waived fee, `W` volunteers on event day and rides separately.
The registration status lives in `registrations`; shift details live here.

| Column | Type | Notes |
|--------|------|-------|
| `rusa_id` | INTEGER FK → riders | |
| `event_id` | TEXT FK → events | |
| `shift` | TEXT | |
| `is_lead` | BOOLEAN | |
| `notes` | TEXT | |
| PRIMARY KEY | (rusa_id, event_id) | |

### `email_lists`
Mailing lists (currently tabs in M3).

| Column | Type | Notes |
|--------|------|-------|
| `email` | TEXT | |
| `list_name` | TEXT | `announcements`, `volunteering` |
| PRIMARY KEY | (email, list_name) | |

---

## Routes: 2026 Season

### Fixed-course routes (`fixed_course = true`)

| route_id | name | dist_km | event_type |
|----------|------|---------|------------|
| `point-reyes-populaire` | January Point Reyes Populaire | 118 | populaire |
| `dillon-beach` | Dillon Beach | 200 | brevet |
| `del-puerto-canyon` | Del Puerto Canyon | 200 | brevet |
| `healdsburg` | Healdsburg | 300 | brevet |
| `two-rock-valley-ford` | Two Rock-Valley Ford | 200 | brevet |
| `womens-populaire` | SFR Women's Populaire | 108 | populaire |
| `russian-river` | Russian River | 200 | brevet |
| `hopland` | Hopland | 400 | brevet |
| `fault-line` | Fault Line | 200 | brevet |
| `marin-mountains` | Marin Mountains | 200 | brevet |
| `mendocino-coast` | Mendocino Coast | 600 | brevet |
| `laguna-lake` | Laguna Lake | 200 | brevet |
| `big-rock-tocaloma` | Big Rock-Tocaloma Populaire | 130 | populaire |
| `old-cazadero` | Old Cazadero | 300 | brevet |
| `freestone-breadrun` | Freestone Breadrun | 200 | brevet |
| `king-ridge` | King Ridge | 400 | brevet |
| `mt-hamilton` | Mt. Hamilton | 200 | brevet |
| `orr-springs` | Orr Springs | 600 | brevet |
| `lucas-valley` | Lucas Valley | 111 | populaire |
| `booneville-lollipop` | Booneville Lollipop | 300 | brevet |
| `sf-to-cloverdale` | SF to Cloverdale | 200 | brevet |
| `cloverdale-to-sf` | Cloverdale to SF | 200 | brevet |
| `coleman-valley` | Coleman Valley | 200 | brevet |
| `winters` | Winters | 200 | brevet |
| `estero-americano` | Estero Americano | 200 | brevet |
| `black-friday-populaire` | Metin's Black Friday Populaire | 100 | populaire |

### Variable-course event formats (`fixed_course = false`)

| route_id | name | dist_km | event_type |
|----------|------|---------|------------|
| `fleche` | Bruce Berg Fleche NorCal | 480 | fleche |
| `dart` | SFR Fall DART | 200 | dart |
| `dart-populaire` | SFR FALL DART Populaire | 100 | populaire |
| `nov-dart-populaire` | SFR November DART Populaire | 100 | populaire |

---

## Events: 2026 Calendar

`inc` disambiguates events sharing the same year/month/distance, ordered by date ascending.

| event_id | route_id | event_date | reg_source |
|----------|---------|------------|------------|
| `2026_01_118_1` | `point-reyes-populaire` | 2026-01-11 | jotform |
| `2026_01_200_1` | `dillon-beach` | 2026-01-24 | jotform |
| `2026_02_200_1` | `del-puerto-canyon` | 2026-02-14 | jotform |
| `2026_02_300_1` | `healdsburg` | 2026-02-28 | jotform |
| `2026_02_200_2` | `two-rock-valley-ford` | 2026-02-28 | jotform |
| `2026_03_108_1` | `womens-populaire` | 2026-03-08 | jotform |
| `2026_03_200_1` | `russian-river` | 2026-03-28 | jotform |
| `2026_04_480_1` | `fleche` | 2026-04-03 | separate_flow |
| `2026_04_400_1` | `hopland` | 2026-04-11 | jotform |
| `2026_04_200_1` | `fault-line` | 2026-04-11 | jotform |
| `2026_04_200_2` | `marin-mountains` | 2026-04-19 | jotform |
| `2026_05_600_1` | `mendocino-coast` | 2026-05-02 | jotform |
| `2026_05_200_1` | `laguna-lake` | 2026-05-03 | jotform |
| `2026_05_130_1` | `big-rock-tocaloma` | 2026-05-03 | jotform |
| `2026_05_300_1` | `old-cazadero` | 2026-05-16 | jotform |
| `2026_05_200_2` | `freestone-breadrun` | 2026-05-16 | jotform |
| `2026_06_400_1` | `king-ridge` | 2026-06-06 | jotform |
| `2026_06_200_1` | `mt-hamilton` | 2026-06-13 | jotform |
| `2026_06_600_1` | `orr-springs` | 2026-06-27 | jotform |
| `2026_06_200_2` | `laguna-lake` | 2026-06-28 | jotform |
| `2026_06_111_1` | `lucas-valley` | 2026-06-28 | jotform |
| `2026_07_300_1` | `booneville-lollipop` | 2026-07-11 | jotform |
| `2026_07_200_1` | `sf-to-cloverdale` | 2026-07-11 | jotform |
| `2026_07_200_2` | `cloverdale-to-sf` | 2026-07-12 | jotform |
| `2026_08_200_1` | `laguna-lake` | 2026-08-29 | jotform |
| `2026_09_200_1` | `coleman-valley` | 2026-09-06 | jotform |
| `2026_10_100_1` | `dart-populaire` | 2026-10-03 | separate_flow |
| `2026_10_200_1` | `dart` | 2026-10-03 | separate_flow |
| `2026_10_200_2` | `winters` | 2026-10-17 | jotform |
| `2026_11_200_1` | `del-puerto-canyon` | 2026-11-07 | jotform |
| `2026_11_100_1` | `nov-dart-populaire` | 2026-11-14 | separate_flow |
| `2026_11_100_2` | `black-friday-populaire` | 2026-11-27 | jotform |
| `2026_12_200_1` | `estero-americano` | 2026-12-05 | jotform |

---

## Views (replacing current sheets)

| View | Replaces | Definition |
|------|---------|------------|
| Member list | M3 `membership registrations` | `riders` + `memberships` pivoted by year |
| Expiring RUSA | M3 `members with exp rusa` | JOIN `memberships` + `rusa_memberships` WHERE SFR active + RUSA expiring |
| Announce match | M3 `memb match wannounce` | `memberships` LEFT JOIN `email_lists` WHERE list=`announcements` |
| Volunteer match | M3 `memb match volunteering` | `memberships` LEFT JOIN `email_lists` WHERE list=`volunteering` |
| Registration master | R2/R3 | `riders` + `registrations` WHERE status != 'C', pivoted by event for current year |
| Per-event roster (no contact) | R4a | `registrations` WHERE event_id=X AND status != 'C', no address/phone |
| Per-event roster (with contact) | R4b `Roster` | Same + full contact info from `riders` |
| Waiver checklist | R4b `waiver check list` | `registrations` WHERE event_id=X AND status != 'C' AND waiver_submitted=false |
| Weekend volunteer sheet | R6 | `volunteers` JOIN `riders` for a given event/weekend; merges multiple same-day events |

---

## Automation Pipeline

```
M1 (Jotform membership) ──► ingest_membership.py ──► riders + memberships
R1 (Jotform registration) ─► ingest_registration.py ─► registrations
                                (normalizes wide columns → one row per rider/event)

Triggers:
  - On new M1 row → ingest_membership (upsert rider, upsert membership years)
  - On new R1 row → ingest_registration (upsert registrations for all checked events)
  - On demand: "Generate event sheets" → creates/refreshes R4a + R4b per event
  - Scheduled (end of year): expiration reminder emails

Manual entry points:
  - `events` tab: Rob adds/edits calendar entries and routes
  - `registrations` tab: admin adds a row to register someone manually
  - `results` tab: Alan enters finish times after each event
  - `routes` tab: add a new route when a new course is introduced
```

---

## Deferred

- **R5 (volunteer sheet per event)** — not yet provided; will be a view derived from
  `volunteers` + `riders` for a given event; defer until admin clarifies format
- **Fleche, DART, DARTP, NOVDARTPOP registration flow** — how registrations are collected
  for `separate_flow` events is TBD; defer until admin clarifies
- **Mid-week event handling** — defer until admin clarifies whether mid-week rides share
  a route record with the weekend version or get their own
- **email_lists source** — currently tabs in M3; source sheet ID TBD
- **Jotform form generation from calendar** — long-term: admin adds to `events` tab,
  script syncs to Jotform. Phase 2 after core system is working.
- **Card-o-matic export** — keep identical to current R4b `Roster` column format
