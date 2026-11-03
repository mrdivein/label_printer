"""Type-ahead suggestions over the loaded data (UI-free; used by the Qt ScanController).

Used by the scan box when Instant print is OFF: instead of requiring an exact UPC the operator can type part of a
UPC, SKU / model, product name or brand. Every whitespace-separated token must match somewhere in the row.
"""
import re

from .barcode_lookup import detect_barcode_columns, normalize_barcode_value

_SKU_NAMES = {"sku", "model", "item", "item #", "item no", "item number", "mpn", "part", "part #", "part number",
              "style", "ref", "reference", "code"}
_NAME_NAMES = {"name", "product", "product name", "title", "description", "item name", "desc"}


def _norm(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip().casefold()


def _classify(headers):
    codes = detect_barcode_columns(headers)
    skus, brands, names = [], [], []
    for h in headers:
        low = str(h).strip().casefold()
        if h in codes:
            continue
        if "brand" in low or "manufacturer" in low:
            brands.append(h)
        elif low in _SKU_NAMES or "sku" in low:
            skus.append(h)
        elif low in _NAME_NAMES or "name" in low or "description" in low:
            names.append(h)
    return codes, skus, brands, names


class SuggestIndex:
    """Lower-cased copy of the searchable cells, built once per data set."""

    def __init__(self, headers=(), rows=()):
        self.headers = list(headers)
        self.rows = rows
        self.codes, self.skus, self.brands, self.names = _classify(self.headers)
        key = set(self.codes) | set(self.skus) | set(self.brands) | set(self.names)
        self.other = [h for h in self.headers if h not in key]
        # per row: (code values, sku values, brand+name values, everything else)
        self._cells = []
        for row in rows:
            self._cells.append((
                [normalize_barcode_value(row.get(h)).casefold() for h in self.codes],
                [_norm(row.get(h)) for h in self.skus],
                [_norm(row.get(h)) for h in self.brands + self.names],
                [_norm(row.get(h)) for h in self.other],
            ))

    @staticmethod
    def _token_score(tok, cells):
        """Lower is better; None = token not found in this row."""
        codes, skus, names, other = cells
        best = None

        def hit(score):
            nonlocal best
            if best is None or score < best:
                best = score

        for v in codes:
            if v == tok:
                hit(0)
            elif v.startswith(tok):
                hit(1)
            elif tok in v:
                hit(3)
        for v in skus:
            if v == tok:
                hit(0)
            elif v.startswith(tok):
                hit(1)
            elif tok in v:
                hit(3)
        for v in names:
            if v == tok:
                hit(1)
            elif v.startswith(tok) or any(w.startswith(tok) for w in re.split(r"\W+", v)):
                hit(2)
            elif tok in v:
                hit(4)
        if best is None:
            for v in other:
                if tok in v:
                    hit(5)
                    break
        return best

    def search(self, query, limit=8):
        """Row indices best-first (score, then sheet order). Empty query -> []."""
        toks = [t for t in re.split(r"\s+", normalize_barcode_value_keep(query)) if t]
        if not toks:
            return []
        scored = []
        for i, cells in enumerate(self._cells):
            total = 0
            for t in toks:
                s = self._token_score(t, cells)
                if s is None:
                    break
                total += s
            else:
                scored.append((total, i))
        scored.sort()
        return [i for _s, i in scored[:limit]]

    def describe(self, i):
        """Display fields for a suggestion row."""
        row = self.rows[i]

        def first(cols, default=''):
            for h in cols:
                v = row.get(h)
                if v not in (None, ''):
                    return normalize_barcode_value(v) if cols is self.codes else str(v).strip()
            return default

        return {'index': i, 'sheetRow': i + 2, 'upc': first(self.codes), 'sku': first(self.skus),
                'brand': first(self.brands), 'name': first(self.names), 'price': str(row.get('Price', '') or '')}


def normalize_barcode_value_keep(q):
    """Collapse scanner control characters but keep spaces between search words."""
    return re.sub(r"[\x00-\x08\x0a-\x1f\x7f]+", " ", (q or "")).strip().casefold()
