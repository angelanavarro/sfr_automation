# SFR Club Membership Automation Project

## Onboarding Document for Claude Code Agent

**Date:** March 2026  
**Status:** Discovery & Planning Phase

---

## Project Overview

The San Francisco Randonneurs (SFR) is a cycling club that organizes long-distance brevet rides. They need to automate their membership and event registration workflows, which currently involve significant manual data processing between Google Sheets.

**Goal:** Automate the manual copy/paste and data transformation steps while keeping the existing Google Sheets infrastructure.

---

## Spreadsheet Inventory

### Membership Flow (M-series)

| Sheet | URL | Purpose |
|-------|-----|---------|
| **M1** | [Link](https://docs.google.com/spreadsheets/d/1edosDQLm4_LuEUO6k8IgsvTxOdgXuNwxflA6KO5cZZk/edit?gid=1926865723#gid=1926865723) | Raw Jotform membership submissions |
| **M2** | [Link](https://docs.google.com/spreadsheets/d/1QDL_1cVeMUF04Qr13_NzaTIZWoygT-GhQBJUpFGVH5A/edit?gid=0#gid=0) | Takes relevant fields from M1, rearranges them, converts membership year into "X". Rob tracks processed rows by highlighting RUSA number in yellow. |
| **M3** | [Link](https://docs.google.com/spreadsheets/d/1kwci4HsHIGyuFjYHOU5XPd5XqFgZ0tHB0kho5HFk11Q/edit?gid=959766403#gid=959766403) | Master membership list. Rob copies from M2: overwrites columns A-K, then separately pastes year columns. Used to validate R-series registrations. Has multiple tabs for projects like email list reconciliation and expiration reminders. |

### Registration Flow (R-series)

| Sheet | URL | Purpose |
|-------|-----|---------|
| **R1** | [Link](https://docs.google.com/spreadsheets/d/1-7FlT-vctfFPZ3xqJJi7iZkd8jfI_LfuvVvaDaU4c4A/edit?gid=1492590668#gid=1492590668) | Raw Jotform event registration submissions |
| **R2** | [Link](https://docs.google.com/spreadsheets/d/1njq4yCt4sGpGurunMhpeL_X1wjHLL34NhzWXjs126mM/edit?usp=sharing) | Takes raw rows from R1, rearranges data, AND pulls data from M3 for validation. Formulas show alternate text if registrant is not a member. When a row is finished, Rob copies it to R3. |
| **R3** | [Link](https://docs.google.com/spreadsheets/d/1_aJsV8388ZgyIqRVic-5-9nGt8E6SVZM86IY6XhzsJI/edit?gid=727249310#gid=727249310) | Per-year master registration list |
| **R4a.1** | [Link](https://docs.google.com/spreadsheets/d/1ldNLRC_eJgiZLR0cngEUYnGFF8L-nauwf0JzMC2qRAc/edit?usp=sharing) | Per-event roster for specific event (e.g., 1_100_2026 = January 100km 2026). Pulls from R3. No contact info — used by R5 volunteer spreadsheet. |
| **R4b** | [Link](https://docs.google.com/spreadsheets/d/18M9fXxqB4OwiKwUuRr7izUw8Aj6wdYr6rCFsxr3_fko/edit?usp=sharing) | Contact info for results processing, waivers, and Card-o-matic export |
| **R5a.1** | ❌ **Not yet provided** | Volunteer spreadsheet per event. R4a.1 feeds into R5a.1. Keeps volunteer sheet up to date automatically. |
| **R6.1** | [Link](https://docs.google.com/spreadsheets/d/1REsdBQILIt8YbQFi-zlSrAiX9txi2h7v0vX6Ezwr1t8/edit?usp=sharing) | Weekend roster. Pulls data from R5a.1. Can merge data from multiple upstream spreadsheets when there are two or more events on a weekend. |

---