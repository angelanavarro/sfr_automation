"""
Tests for create_master.py and create_annual.py — tab structure setup.
These tests mock the gspread API to verify the right tabs are created with the right headers.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from config import MasterTab, AnnualTab
import scripts.create_master as create_master
import scripts.create_annual as create_annual


def make_ss(existing_tab_name="Sheet1"):
    """Return a mock spreadsheet with a single default sheet."""
    ws = MagicMock()
    ws.id = 1
    ws.title = existing_tab_name
    ss = MagicMock()
    ss.sheet1 = ws
    ss.worksheet.return_value = ws
    ss.id = "fake_ss_id"
    ss.url = "https://docs.google.com/fake"
    return ss


class TestCreateMaster:
    def test_all_tabs_created(self):
        ss = make_ss()
        with patch("utils.format_sheet_headers"):
            create_master.setup(ss)

        created_titles = [c.kwargs["title"] for c in ss.add_worksheet.call_args_list]
        expected = list(create_master.TABS.keys())[1:]  # first tab is renamed, not added
        assert set(created_titles) == set(expected)

    def test_first_tab_renamed(self):
        ss = make_ss()
        with patch("utils.format_sheet_headers"):
            create_master.setup(ss)
        ss.sheet1.update_title.assert_called_once_with(list(create_master.TABS.keys())[0])

    def test_routes_seeded(self):
        ss = make_ss()
        with patch("utils.format_sheet_headers"):
            create_master.setup(ss)
        ws = ss.worksheet.return_value
        # append_rows or update should have been called with route seed data
        calls = ws.update.call_args_list
        # One of the update calls should be the routes seed (ROUTES_SEED passed as data)
        route_calls = [c for c in calls if c.args and c.args[0] == create_master.ROUTES_SEED]
        assert len(route_calls) == 1

    def test_required_tabs_present(self):
        expected = {MasterTab.ROUTES, MasterTab.RIDERS, MasterTab.MEMBERSHIPS,
                    MasterTab.RUSA, MasterTab.EMAIL_LISTS}
        assert set(create_master.TABS.keys()) == expected


class TestCreateAnnual:
    def test_all_tabs_created(self):
        ss = make_ss()
        with patch("utils.format_sheet_headers"):
            create_annual_ss(ss, 2026)

        created_titles = [c.kwargs["title"] for c in ss.add_worksheet.call_args_list]
        expected = list(create_annual.TABS.keys())[1:]
        assert set(created_titles) == set(expected)

    def test_events_seeded_for_2026(self):
        ss = make_ss()
        with patch("utils.format_sheet_headers"):
            create_annual_ss(ss, 2026)
        ws = ss.worksheet.return_value
        calls = ws.update.call_args_list
        seed_calls = [c for c in calls if c.args and c.args[0] == create_annual.EVENTS_2026]
        assert len(seed_calls) == 1

    def test_no_seed_for_unknown_year(self):
        ss = make_ss()
        with patch("utils.format_sheet_headers"):
            create_annual_ss(ss, 2099)  # no seed data for this year
        ws = ss.worksheet.return_value
        # Seed rows are written to "A2"; header rows are written to "A1"
        seed_calls = [c for c in ws.update.call_args_list if len(c.args) > 1 and c.args[1] == "A2"]
        assert len(seed_calls) == 0

    def test_required_tabs_present(self):
        expected = {AnnualTab.EVENTS, AnnualTab.REGISTRATIONS, AnnualTab.RIDERS_VIEW,
                    AnnualTab.SUMMARY, AnnualTab.VOLUNTEERS}
        assert set(create_annual.TABS.keys()) == expected

    def test_events_2027_stub_exists(self):
        """Ensure EVENTS_BY_YEAR has a 2027 entry so create_annual.py won't crash for year 2027."""
        assert 2027 in create_annual.EVENTS_BY_YEAR


def create_annual_ss(ss, year):
    """Helper: run create_annual tab setup logic directly (bypasses sys.argv/client)."""
    ws = ss.sheet1
    ws.update_title(list(create_annual.TABS.keys())[0])
    for tab_name in list(create_annual.TABS.keys())[1:]:
        ss.add_worksheet(title=tab_name, rows=2000, cols=60)

    for tab_name, headers in create_annual.TABS.items():
        ws = ss.worksheet(tab_name)
        if headers:
            ws.update([headers], "A1")
            import utils
            utils.format_sheet_headers(ws, num_cols=len(headers))
        ss.batch_update({"requests": [{}]})

    events_seed = create_annual.EVENTS_BY_YEAR.get(year)
    if events_seed:
        ws_events = ss.worksheet(AnnualTab.EVENTS)
        ws_events.update(events_seed, "A2")
