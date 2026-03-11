"""
Shared utilities for SFR automation scripts.
"""

# Flag color: yellow (#FFFDE7) for riders missing SFR membership
FLAG_YELLOW = {"red": 1.0, "green": 0.992, "blue": 0.906}

# Header color scheme: dark blue-grey (#37474F) with white text
HEADER_BG    = {"red": 0.216, "green": 0.278, "blue": 0.310}
HEADER_FG    = {"red": 1.0,   "green": 1.0,   "blue": 1.0}

# Subheader color scheme: light blue-grey (#ECEFF1) with dark text
SUBHEADER_BG = {"red": 0.925, "green": 0.937, "blue": 0.945}
SUBHEADER_FG = {"red": 0.216, "green": 0.278, "blue": 0.310}


def format_sheet_headers(ws, num_cols, has_subheader=False):
    """
    Apply consistent header formatting to a worksheet.
    - Row 1: dark blue-grey background, white bold text
    - Row 2 (if has_subheader): light blue-grey background, dark bold text
    num_cols: number of columns to format
    """
    def col_letter(n):
        """Convert 1-based column number to letter(s), e.g. 1→A, 27→AA."""
        result = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result

    last_col = col_letter(num_cols)

    ws.format(f"A1:{last_col}1", {
        "backgroundColor": HEADER_BG,
        "textFormat": {
            "bold": True,
            "foregroundColor": HEADER_FG,
        },
    })

    if has_subheader:
        ws.format(f"A2:{last_col}2", {
            "backgroundColor": SUBHEADER_BG,
            "textFormat": {
                "bold": True,
                "foregroundColor": SUBHEADER_FG,
            },
        })


def apply_membership_flags(ss, ws, header_rows=2):
    """
    Apply conditional formatting to riders_view:
    - Yellow row: rider has no SFR membership for the current year (sfr_member column is blank)
    - Orange row: rider has no RUSA membership or it is expired (rusa_member column is blank or starts with 'expired')

    Clears all existing conditional format rules for the sheet before re-applying,
    so rules don't accumulate across ingest runs.

    sfr_member  = column E (index 4, 1-based col 5)
    rusa_member = column F (index 5, 1-based col 6)
    Data rows start at row header_rows+1.
    """
    sheet_id = ws.id
    first_data_row = header_rows + 1  # 1-based

    # Fetch existing conditional format rules for this sheet
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{ss.id}?fields=sheets(properties/sheetId,conditionalFormats)"
    response = ss.client.request("get", url)
    sheets_data = response.json().get("sheets", [])

    delete_requests = []
    for sheet in sheets_data:
        if sheet["properties"]["sheetId"] == sheet_id:
            num_rules = len(sheet.get("conditionalFormats", []))
            # Delete from last to first to avoid index shifting
            for i in range(num_rules - 1, -1, -1):
                delete_requests.append({
                    "deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}
                })
            break

    # Only color the rusa_id cell (column A), not the entire row
    data_range = {
        "sheetId": sheet_id,
        "startRowIndex": first_data_row - 1,  # 0-based
        "startColumnIndex": 0,
        "endColumnIndex": 1,
    }

    add_requests = [
        # Yellow: no SFR membership (sfr_member column E is blank)
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [data_range],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": f'=$E{first_data_row}=""'}],
                        },
                        "format": {"backgroundColor": FLAG_YELLOW},
                    },
                },
                "index": 0,
            }
        },
        # Orange: no RUSA membership or expired (rusa_member column F is blank or starts with 'expired')
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [data_range],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": f'=OR($F{first_data_row}="",LEFT($F{first_data_row},7)="expired")'}],
                        },
                        "format": {"backgroundColor": {"red": 1.0, "green": 0.8, "blue": 0.6}},
                    },
                },
                "index": 1,
            }
        },
    ]

    ss.batch_update({"requests": delete_requests + add_requests})
