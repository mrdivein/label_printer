"""Google Sheet / Excel data sources."""
import csv
import os
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
        headers={"User-Agent": "Mozilla/5.0 Label-Printer"}
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


# ----------------------------
# Loaded data set (rows + search + current row) shared by the UI
# ----------------------------
_PREFERRED_SEARCH_COLUMNS = ["Barcode", "UPC", "UPC/EAN", "EAN", "Model", "SKU", "Brand", "Brand Name"]


class DataSet:
    """Rows from an Excel sheet or a Google Sheet tab plus the filter / current-row state.

    Row dicts are keyed by (made-unique) header names exactly as the original application did, so templates and
    {{Column}} bindings behave identically.
    """

    def __init__(self):
        self.headers = []
        self.rows = []
        self.filtered = []          # indices into rows
        self.current = 0
        self.kind = ''              # 'excel' | 'google' | ''
        self.label = ''
        self.excel_path = ''
        self.sheet_names = []
        self.sheet = ''
        self._wb = None

    # -- loading
    def load_excel(self, path, sheet=None):
        from openpyxl import load_workbook
        self.close()
        wb = load_workbook(path, data_only=True, read_only=True)
        self._wb = wb
        self.kind = 'excel'
        self.excel_path = path
        self.sheet_names = list(wb.sheetnames)
        name = sheet if sheet in self.sheet_names else (self.sheet_names[0] if self.sheet_names else '')
        self.load_sheet(name)

    def load_sheet(self, name):
        if not self._wb:
            return
        self.sheet = name
        values = list(self._wb[name].iter_rows(values_only=True))
        self.label = f"{os.path.basename(self.excel_path)} · {name}" if name else os.path.basename(self.excel_path)
        if not values:
            self.headers, self.rows = [], []
        else:
            self.headers = make_unique_headers(values[0])
            self.rows = []
            for r in values[1:]:
                row = {}
                has_value = False
                for i, h in enumerate(self.headers):
                    v = r[i] if i < len(r) else None
                    row[h] = v
                    if v not in (None, ""):
                        has_value = True
                if has_value:
                    self.rows.append(row)
        self.reset_filter()

    def set_google(self, headers, rows, url, tab, name=None):
        self.close()
        self.kind = 'google'
        self.headers, self.rows = headers, rows
        self.sheet_names = [tab or 'Google Sheet']
        self.sheet = self.sheet_names[0]
        self.label = name or f"Google Sheet · {tab or ''}".strip(' ·')
        self.reset_filter()

    def close(self):
        if self._wb is not None:
            try:
                self._wb.close()
            except Exception:
                pass
        self._wb = None

    # -- filtering / navigation
    def reset_filter(self):
        self.filtered = list(range(len(self.rows)))
        self.current = self.filtered[0] if self.filtered else 0

    def search(self, query):
        q = normalize_search_text(query)
        if not q:
            self.filtered = list(range(len(self.rows)))
        else:
            matches = []
            for i, row in enumerate(self.rows):
                values = []
                seen = set()
                for c in _PREFERRED_SEARCH_COLUMNS:
                    if c in row:
                        values.append(normalize_search_text(row.get(c)))
                        seen.add(c)
                for c, v in row.items():
                    if c not in seen:
                        values.append(normalize_search_text(v))
                if any(q in v for v in values):
                    matches.append(i)
            self.filtered = matches
        if self.filtered and self.current not in self.filtered:
            self.current = self.filtered[0]

    def best_match(self, query):
        """Row index for Enter in the search box: exact barcode match wins, else the first filtered row."""
        if not self.filtered:
            return None
        q = normalize_search_text(query)
        for i in self.filtered:
            row = self.rows[i]
            for c in ("Barcode", "UPC", "UPC/EAN", "EAN"):
                if c in row and normalize_search_text(row.get(c)) == q:
                    return i
        return self.filtered[0]

    @property
    def current_row(self):
        if self.rows and 0 <= self.current < len(self.rows):
            return self.rows[self.current]
        return None
