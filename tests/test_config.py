"""
Tests for config.py helpers.
"""
import pytest
from unittest.mock import patch


def test_get_active_annual_ids_single():
    """Normal case: only one year active."""
    ids = {"2026": "1Aq5JWZfNgOiKlX-Yn_Aflw85H6IMhuDstYaYkdlkS_4", "2027": ""}
    with patch("config.ANNUAL_SPREADSHEET_IDS", {2026: "abc123", 2027: ""}):
        from config import get_active_annual_ids
        result = get_active_annual_ids()
    assert result == [(2026, "abc123")]


def test_get_active_annual_ids_dual():
    """Transition window: both years active."""
    with patch("config.ANNUAL_SPREADSHEET_IDS", {2026: "abc123", 2027: "def456"}):
        from config import get_active_annual_ids
        result = get_active_annual_ids()
    assert result == [(2026, "abc123"), (2027, "def456")]


def test_get_active_annual_ids_none():
    """Edge case: no active sheets (should not happen in practice)."""
    with patch("config.ANNUAL_SPREADSHEET_IDS", {2026: "", 2027: ""}):
        from config import get_active_annual_ids
        result = get_active_annual_ids()
    assert result == []


def test_get_active_annual_ids_sorted():
    """Years are always returned in ascending order regardless of dict order."""
    with patch("config.ANNUAL_SPREADSHEET_IDS", {2027: "def456", 2026: "abc123"}):
        from config import get_active_annual_ids
        result = get_active_annual_ids()
    assert result == [(2026, "abc123"), (2027, "def456")]
