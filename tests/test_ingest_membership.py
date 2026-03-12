"""
Tests for ingest_membership.py — pure functions.
"""
import pytest
from scripts.ingest_membership import parse_membership_years, build_rider_row
from config import M1Col


class TestParseMembershipYears:
    def test_single_year(self):
        result = parse_membership_years("2026")
        assert result == [(2026, "X")]

    def test_newline_separated(self):
        result = parse_membership_years("2024\n2025\n2026")
        years = {y for y, _ in result}
        assert years == {2024, 2025, 2026}

    def test_comma_separated(self):
        result = parse_membership_years("2024, 2025")
        years = {y for y, _ in result}
        assert years == {2024, 2025}

    def test_empty_string(self):
        assert parse_membership_years("") == []

    def test_no_duplicates(self):
        result = parse_membership_years("2026\n2026")
        assert len(result) == 1

    def test_all_statuses_are_paid(self):
        result = parse_membership_years("2026")
        assert all(status == "X" for _, status in result)


class TestBuildRiderRow:
    def _make_row(self, rusa_id="12345", first="Jane", last="Doe",
                  email="jane@example.com", phone="555-1234"):
        row = [""] * 17
        row[M1Col.RUSA_ID]    = rusa_id
        row[M1Col.FIRST_NAME] = first
        row[M1Col.LAST_NAME]  = last
        row[M1Col.EMAIL]      = email
        row[M1Col.PHONE]      = phone
        return row

    def test_basic_fields(self):
        row = self._make_row()
        result = build_rider_row(row)
        assert result[0] == "12345"   # rusa_id
        assert result[1] == "Jane"    # first_name
        assert result[2] == "Doe"     # last_name
        assert result[3] == "jane@example.com"

    def test_backup_fields_blank(self):
        row = self._make_row()
        result = build_rider_row(row)
        assert result[5] == ""  # backup_contact
        assert result[6] == ""  # backup_phone

    def test_country_blank(self):
        row = self._make_row()
        result = build_rider_row(row)
        assert result[11] == ""  # country
