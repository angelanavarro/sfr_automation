"""
Smoke tests: verify all scripts can be imported without error.
This catches broken imports like the ANNUAL_SPREADSHEET_ID → ANNUAL_SPREADSHEET_IDS rename.
"""


def test_import_config():
    import config  # noqa: F401


def test_import_utils():
    import utils  # noqa: F401


def test_import_ingest_registration():
    import scripts.ingest_registration  # noqa: F401


def test_import_ingest_membership():
    import scripts.ingest_membership  # noqa: F401


def test_import_generate_event_sheets():
    import scripts.generate_event_sheets  # noqa: F401


def test_import_create_annual():
    import scripts.create_annual  # noqa: F401


def test_import_create_master():
    import scripts.create_master  # noqa: F401


def test_import_create_event_sheets_oauth():
    import scripts.create_event_sheets_oauth  # noqa: F401


def test_import_check_sources():
    import scripts.check_sources  # noqa: F401
