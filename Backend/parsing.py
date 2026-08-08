"""parsing.py — turns an uploaded CSV/Excel file into normalized records:
{item_id, stage, entry_time (ISO str), exit_time (ISO str), duration_seconds}

Column names are matched flexibly (case/space/underscore-insensitive),
so "Item ID", "item_id", "OrderNumber" etc. all work.
"""

import io
import pandas as pd

FIELD_ALIASES = {
    "item_id": ["itemid", "item", "orderid", "order", "ordernumber", "id", "ticketid", "ticket", "unitid"],
    "stage": ["stage", "step", "phase", "stagename", "process", "station"],
    "entry_time": ["entrytime", "start", "starttime", "in", "entry", "begin", "begintime"],
    "exit_time": ["exittime", "end", "endtime", "out", "exit", "finish", "finishtime"],
}


def _normalize(h: str) -> str:
    return str(h or "").lower().replace(" ", "").replace("_", "").replace("-", "")


def _map_headers(headers):
    normalized = [_normalize(h) for h in headers]
    mapping = {}
    for field, aliases in FIELD_ALIASES.items():
        for i, h in enumerate(normalized):
            if h in aliases or h == field.replace("_", ""):
                mapping[field] = headers[i]
                break
    return mapping


def _dataframe_to_records(df: pd.DataFrame):
    if df.empty:
        return [], ["File appears to be empty."]

    headers = list(df.columns)
    mapping = _map_headers(headers)
    missing = [f for f in ["item_id", "stage", "entry_time", "exit_time"] if f not in mapping]
    if missing:
        return [], [
            f"Could not find columns for: {', '.join(missing)}. "
            f"Detected headers: {', '.join(str(h) for h in headers)}. "
            f"Expected something like item_id, stage, entry_time, exit_time (flexible naming allowed)."
        ]

    records, errors = [], []
    for i, row in df.iterrows():
        item_id = str(row[mapping["item_id"]]).strip() if pd.notna(row[mapping["item_id"]]) else ""
        stage = str(row[mapping["stage"]]).strip() if pd.notna(row[mapping["stage"]]) else ""
        entry = pd.to_datetime(row[mapping["entry_time"]], errors="coerce")
        exit_ = pd.to_datetime(row[mapping["exit_time"]], errors="coerce")

        if not item_id or not stage or pd.isna(entry) or pd.isna(exit_):
            errors.append(f"Row {i + 2}: skipped (missing or unparseable value).")
            continue

        duration = (exit_ - entry).total_seconds()
        if duration < 0:
            errors.append(f"Row {i + 2}: skipped (exit_time is before entry_time).")
            continue

        records.append({
            "item_id": item_id,
            "stage": stage,
            "entry_time": entry.to_pydatetime().isoformat(),
            "exit_time": exit_.to_pydatetime().isoformat(),
            "duration_seconds": duration,
        })

    return records, errors


def parse_csv_bytes(raw: bytes):
    df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, na_values=[""])
    return _dataframe_to_records(df)


def parse_excel_bytes(raw: bytes):
    df = pd.read_excel(io.BytesIO(raw))
    return _dataframe_to_records(df)


def parse_google_sheet_csv_url(url: str) -> str:
    """Convert a normal Google Sheets share URL into its CSV export URL.
    (Simple, no-OAuth import path: the sheet must be shared as
    "Anyone with the link can view".)"""
    import re
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise ValueError("Could not find a spreadsheet ID in that URL.")
    sheet_id = match.group(1)
    gid_match = re.search(r"[?&#]gid=([0-9]+)", url)
    gid = gid_match.group(1) if gid_match else "0"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
