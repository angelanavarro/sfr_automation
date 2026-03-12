"""
Tests for ingest_registration.py — pure functions and mocked upsert logic.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from scripts.ingest_registration import (
    _year_from_event_id,
    parse_registrations,
    upsert_registrations,
    build_column_map,
)
from config import RegStatus, AnnualTab


# ---------------------------------------------------------------------------
# _year_from_event_id
# ---------------------------------------------------------------------------

class TestYearFromEventId:
    def test_normal(self):
        assert _year_from_event_id("2026_03_200_1") == 2026

    def test_next_year(self):
        assert _year_from_event_id("2027_01_118_1") == 2027

    def test_empty(self):
        assert _year_from_event_id("") is None

    def test_no_underscore(self):
        assert _year_from_event_id("notanid") is None

    def test_non_numeric_prefix(self):
        assert _year_from_event_id("abcd_01_200_1") is None


# ---------------------------------------------------------------------------
# parse_registrations
# ---------------------------------------------------------------------------

def make_r1_row(rusa_id, event_col_val, waiver="I agree", submission_id="SUB1"):
    """Build a minimal R1 row with rider info at expected column indices."""
    # R1Col: FIRST=38, LAST=39, EMAIL=40, RUSA=41, BACKUP=42, BACKUP_PHONE=43,
    #        WAIVER=48, SUBMISSION_ID=49
    row = [""] * 50
    row[0]  = event_col_val   # event column at index 0 (set by col_map)
    row[41] = rusa_id
    row[48] = waiver
    row[49] = submission_id
    return row


class TestParseRegistrations:
    def setup_method(self):
        self.col_map = {"January 200km": "2026_01_200_1"}
        self.headers = ["January 200km"] + [""] * 49

    def test_paid_status_code(self):
        row = make_r1_row("12345", "X")
        regs = parse_registrations(self.headers, [row], self.col_map)
        assert len(regs) == 1
        assert regs[0]["rusa_id"] == "12345"
        assert regs[0]["event_id"] == "2026_01_200_1"
        assert regs[0]["status"] == RegStatus.PAID

    def test_free_status_code(self):
        row = make_r1_row("12345", "Y")
        regs = parse_registrations(self.headers, [row], self.col_map)
        assert regs[0]["status"] == RegStatus.FREE

    def test_cancelled_status_code(self):
        row = make_r1_row("12345", "C")
        regs = parse_registrations(self.headers, [row], self.col_map)
        assert regs[0]["status"] == RegStatus.CANCELLED

    def test_jotform_event_name_normalized_to_paid(self):
        """R1 stores full event name + price when registered; should become PAID."""
        row = make_r1_row("12345", "Dillon Beach 200km $7.50")
        regs = parse_registrations(self.headers, [row], self.col_map)
        assert regs[0]["status"] == RegStatus.PAID

    def test_waiver_i_agree(self):
        row = make_r1_row("12345", "X", waiver="I agree")
        regs = parse_registrations(self.headers, [row], self.col_map)
        assert regs[0]["waiver_submitted"] is True

    def test_waiver_empty(self):
        row = make_r1_row("12345", "X", waiver="")
        regs = parse_registrations(self.headers, [row], self.col_map)
        assert regs[0]["waiver_submitted"] is False

    def test_empty_event_cell_skipped(self):
        row = make_r1_row("12345", "")
        regs = parse_registrations(self.headers, [row], self.col_map)
        assert len(regs) == 0

    def test_no_rusa_id_skipped(self):
        row = make_r1_row("", "X")
        regs = parse_registrations(self.headers, [row], self.col_map)
        assert len(regs) == 0

    def test_multiple_events(self):
        col_map = {
            "January 200km": "2026_01_200_1",
            "February 300km": "2026_02_300_1",
        }
        headers = ["January 200km", "February 300km"] + [""] * 48
        row = ["X", "Y"] + [""] * 39 + ["12345"] + [""] * 7 + ["I agree", "SUB1"]
        regs = parse_registrations(headers, [row], col_map)
        event_ids = {r["event_id"] for r in regs}
        assert event_ids == {"2026_01_200_1", "2026_02_300_1"}


# ---------------------------------------------------------------------------
# upsert_registrations
# ---------------------------------------------------------------------------

def make_ws():
    """Return a mock worksheet."""
    ws = MagicMock()
    return ws


class TestUpsertRegistrations:
    def _reg(self, rusa_id="12345", event_id="2026_01_200_1", status="X", waiver=True):
        return {
            "rusa_id": rusa_id, "event_id": event_id, "status": status,
            "waiver_submitted": waiver, "submission_id": "SUB1",
            "registered_at": "2026-01-01T00:00:00+00:00", "added_by": "jotform",
        }

    def test_insert_new(self):
        ws = make_ws()
        n_ins, n_upd = upsert_registrations(ws, {}, [self._reg()])
        assert n_ins == 1
        assert n_upd == 0
        ws.append_rows.assert_called_once()

    def test_no_update_when_unchanged(self):
        existing_row = ["12345", "2026_01_200_1", "X", "True", "SUB1", "", "jotform"]
        existing = {"12345|2026_01_200_1": (2, existing_row)}
        ws = make_ws()
        n_ins, n_upd = upsert_registrations(ws, existing, [self._reg()])
        assert n_ins == 0
        assert n_upd == 0
        ws.batch_update.assert_not_called()

    def test_update_when_status_changes(self):
        existing_row = ["12345", "2026_01_200_1", "X", "True", "SUB1", "", "jotform"]
        existing = {"12345|2026_01_200_1": (2, existing_row)}
        ws = make_ws()
        n_ins, n_upd = upsert_registrations(ws, existing, [self._reg(status="C")])
        assert n_ins == 0
        assert n_upd == 1
        ws.batch_update.assert_called_once()

    def test_update_when_waiver_changes(self):
        existing_row = ["12345", "2026_01_200_1", "X", "False", "SUB1", "", "jotform"]
        existing = {"12345|2026_01_200_1": (2, existing_row)}
        ws = make_ws()
        n_ins, n_upd = upsert_registrations(ws, existing, [self._reg(waiver=True)])
        assert n_upd == 1

    def test_no_duplicate_insert_same_run(self):
        """Two records with the same key in the same batch should insert only once."""
        ws = make_ws()
        regs = [self._reg(), self._reg()]  # same key twice
        n_ins, n_upd = upsert_registrations(ws, {}, regs)
        assert n_ins == 1


# ---------------------------------------------------------------------------
# build_column_map
# ---------------------------------------------------------------------------

def make_annual_ss(event_rows):
    """
    Build a mock annual spreadsheet whose events tab returns event_rows.
    event_rows: list of rows (each row is a list matching EventCol indices).
    """
    ws = MagicMock()
    ws.get_all_values.return_value = [
        # header row
        ["event_id", "route_id", "event_date", "worker_ride_date",
         "registration_source", "course_notes", "jotform_column_name", "sheet_url"],
    ] + event_rows
    ss = MagicMock()
    ss.worksheet.return_value = ws
    return ss


class TestBuildColumnMap:
    def _row(self, event_id, source, jotform_col):
        row = [""] * 8
        row[0] = event_id
        row[4] = source
        row[6] = jotform_col
        return row

    def test_single_sheet_maps_jotform_events(self):
        ss = make_annual_ss([
            self._row("2026_01_200_1", "jotform", "Dillon Beach 200km"),
            self._row("2026_04_480_1", "separate_flow", ""),
        ])
        col_map = build_column_map([(2026, ss)])
        assert col_map == {"Dillon Beach 200km": "2026_01_200_1"}

    def test_multi_sheet_merges_both_years(self):
        ss_2026 = make_annual_ss([self._row("2026_01_200_1", "jotform", "Jan 200km")])
        ss_2027 = make_annual_ss([self._row("2027_01_118_1", "jotform", "Jan Populaire")])
        col_map = build_column_map([(2026, ss_2026), (2027, ss_2027)])
        assert "Jan 200km" in col_map
        assert "Jan Populaire" in col_map
        assert col_map["Jan 200km"] == "2026_01_200_1"
        assert col_map["Jan Populaire"] == "2027_01_118_1"

    def test_separate_flow_excluded(self):
        ss = make_annual_ss([self._row("2026_04_480_1", "separate_flow", "")])
        col_map = build_column_map([(2026, ss)])
        assert col_map == {}

    def test_empty_events_tab(self):
        ss = make_annual_ss([])
        col_map = build_column_map([(2026, ss)])
        assert col_map == {}
