"""Google Sheet / Excel data sources."""
import csv
import re
import urllib.parse
import urllib.request

def extract_google_sheet_id(url_or_id):
    s = str(url_or_id).strip()
    if not s:
        raise ValueError("Google Sheet URL/ID is empty.")
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", s):
        return s
    raise ValueError("Could not detect Google Sheet ID.")

def google_sheet_csv_url(url_or_id, sheet_name=None):
    sid = extract_google_sheet_id(url_or_id)
    url = f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv"
    if sheet_name:
        url += "&sheet=" + urllib.parse.quote(str(sheet_name))
    return url

def make_unique_headers(raw_headers):
    """Keep every source column addressable, including blanks and duplicate names."""
    out = []
    seen = {}
    for i, v in enumerate(raw_headers):
        base = str(v).strip() if v is not None else ""
        if not base:
            base = f"Column_{i+1}"
        key = base.casefold()
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            base = f"{base} ({seen[key]})"
        out.append(base)
    return out

def fetch_google_sheet_rows(url_or_id, sheet_name=None):
    req = urllib.request.Request(
        google_sheet_csv_url(url_or_id, sheet_name),
        headers={"User-Agent": "Mozilla/5.0 ECG-Label-Tool"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
    except Exception as e:
        raise RuntimeError("Cannot read Google Sheet. Share it as 'Anyone with the link - Viewer' or use Excel.\n\n" + str(e))
    rows = list(csv.reader(raw.decode("utf-8-sig", errors="replace").splitlines()))
    if not rows:
        return [], []
    headers = make_unique_headers(rows[0])
    data = []
    for r in rows[1:]:
        if not any(str(v).strip() for v in r):
            continue
        row = {}
        for i, h in enumerate(headers):
            row[h] = r[i] if i < len(r) else ""
        data.append(row)
    return headers, data

def normalize_search_text(v):
    return "" if v is None else str(v).strip().lower()
