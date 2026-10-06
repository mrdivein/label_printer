"""Barcode / UPC lookup helpers used by scan-driven printing."""
import re

def normalize_barcode_value(v):
    """Normalize scanner/data barcode values without guessing their length."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).strip()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    # Scanner control characters / whitespace never belong to ECG UPC/EAN keys.
    s = re.sub(r"[\x00-\x20\x7f]+", "", s)
    return s


def detect_barcode_columns(headers):
    preferred = ["Barcode", "UPC/EAN", "UPC", "EAN", "EAN/UPC", "GTIN"]
    by_lower = {str(h).strip().lower(): h for h in headers}
    found = []
    for p in preferred:
        h = by_lower.get(p.lower())
        if h is not None and h not in found:
            found.append(h)
    for h in headers:
        low = str(h).strip().lower()
        if h not in found and any(k in low for k in ("barcode", "upc", "ean", "gtin")):
            found.append(h)
    return found


def build_barcode_lookup(headers, rows):
    columns = detect_barcode_columns(headers)
    lookup = {}
    row_primary = {}
    for i, row in enumerate(rows):
        seen = set()
        for col in columns:
            code = normalize_barcode_value(row.get(col, ""))
            if not code or code in seen:
                continue
            seen.add(code)
            lookup.setdefault(code, []).append(i)
            row_primary.setdefault(i, code)
    # Deduplicate row ids while preserving order.
    for code, ids in list(lookup.items()):
        lookup[code] = list(dict.fromkeys(ids))
    return columns, lookup, row_primary


def segment_concatenated_codes(raw, known_codes, max_solutions=2):
    """
    Split a glued scanner string ONLY by barcodes that exist in the loaded data.
    Returns (status, sequence):
      exact/unique -> list[str]
      ambiguous/not_found -> []
    It stops after max_solutions to avoid expensive ambiguity expansion.
    """
    s = normalize_barcode_value(raw)
    if not s:
        return "not_found", []
    if s in known_codes:
        return "exact", [s]

    lengths = sorted({len(c) for c in known_codes if c}, reverse=True)
    if not lengths:
        return "not_found", []

    # Practical guard against accidental huge clipboard contents.
    if len(s) > 1000:
        return "not_found", []

    memo = {}
    def solve(pos):
        if pos == len(s):
            return [[]]
        if pos in memo:
            return memo[pos]
        solutions = []
        for L in lengths:
            end = pos + L
            if end > len(s):
                continue
            part = s[pos:end]
            if part not in known_codes:
                continue
            for tail in solve(end):
                solutions.append([part] + tail)
                if len(solutions) >= max_solutions:
                    memo[pos] = solutions
                    return solutions
        memo[pos] = solutions
        return solutions

    sols = solve(0)
    # Remove duplicate sequences if equivalent paths occurred.
    unique = []
    seen = set()
    for seq in sols:
        k = tuple(seq)
        if k not in seen:
            seen.add(k)
            unique.append(seq)
        if len(unique) >= max_solutions:
            break

    if len(unique) == 1:
        return "unique", unique[0]
    if len(unique) > 1:
        return "ambiguous", []
    return "not_found", []
