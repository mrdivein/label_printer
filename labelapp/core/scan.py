"""Scanner-driven lookup and the Batch Scan queue (UI-free; used by the Qt ScanController).

Behaviour is the same as the original Tk quick-scan / Batch Scan dialog.
"""
import re

from .barcode_lookup import build_barcode_lookup, normalize_barcode_value, segment_concatenated_codes

READY = "READY"
INCREASE_QTY = "Increase Qty"
ADD_ROW = "Add Row"


class ScanIndex:
    """Barcode -> row indices for the loaded data."""

    def __init__(self, headers=(), rows=()):
        self.columns, self.lookup, _ = build_barcode_lookup(list(headers), list(rows))
        self.known = set(self.lookup)

    @property
    def min_length(self):
        return min((len(c) for c in self.lookup), default=8)

    def resolve(self, raw):
        """Quick scan of one scanner string. Returns (status, codes):
        'ok' (codes unique rows), 'duplicate' (codes = the offending code), 'ambiguous', 'not_found', 'empty'."""
        code = normalize_barcode_value(raw)
        if not code:
            return "empty", []
        status, seq = segment_concatenated_codes(code, self.known)
        if status in ("exact", "unique") and seq:
            for c in seq:
                if len(self.lookup.get(c, [])) != 1:
                    return "duplicate", [c]
            return "ok", seq
        return ("ambiguous" if status == "ambiguous" else "not_found"), [code]

    def tokens(self, raw):
        """Explicit separators first; each token may itself be glued."""
        toks = [t for t in re.split(r"[\s,;|]+", (raw or "").strip()) if t]
        return toks or ([raw.strip()] if raw and raw.strip() else [])


class ScanQueue:
    """Items: {id, code, row_index|None, candidates[list], qty, checked, status}."""

    def __init__(self):
        self.items = []
        self._next_id = 1

    def _new(self, code, row_index, candidates, checked, status):
        it = {"id": self._next_id, "code": code, "row_index": row_index, "candidates": list(candidates),
              "qty": 1, "checked": checked, "status": status}
        self._next_id += 1
        self.items.append(it)
        return it

    def add_code(self, index, code, repeat_mode=INCREASE_QTY):
        ids = index.lookup.get(code, [])
        if len(ids) == 1:
            if repeat_mode == INCREASE_QTY:
                for it in self.items:
                    if it["row_index"] == ids[0] and it["status"] == READY:
                        it["qty"] += 1
                        it["checked"] = True
                        return it
            return self._new(code, ids[0], ids, True, READY)
        if len(ids) > 1:
            return self._new(code, None, ids, False, f"DUPLICATE x{len(ids)}")
        return self._new(code, None, [], False, "NOT FOUND")

    def add_raw(self, index, raw, repeat_mode=INCREASE_QTY):
        """Process pasted/scanned text (may hold several codes). Returns number of queue entries touched."""
        n = 0
        for token in index.tokens(raw):
            code = normalize_barcode_value(token)
            if not code:
                continue
            if code in index.lookup:
                self.add_code(index, code, repeat_mode)
                n += 1
                continue
            status, seq = segment_concatenated_codes(code, index.known)
            if status == "unique" and seq:
                for c in seq:
                    self.add_code(index, c, repeat_mode)
                    n += 1
            else:
                self._new(code, None, [], False, "AMBIGUOUS SPLIT" if status == "ambiguous" else "NOT FOUND")
                n += 1
        return n

    # ---- edits (positions are queue positions)
    def toggle(self, pos):
        if 0 <= pos < len(self.items) and self.items[pos]["status"] == READY:
            self.items[pos]["checked"] = not self.items[pos]["checked"]

    def set_all_checked(self, checked):
        for it in self.items:
            it["checked"] = bool(checked) and it["status"] == READY

    def set_qty(self, pos, qty):
        if 0 <= pos < len(self.items) and self.items[pos]["status"] == READY:
            self.items[pos]["qty"] = max(1, min(999, int(qty)))

    def remove(self, pos):
        if 0 <= pos < len(self.items):
            self.items.pop(pos)

    def clear(self):
        self.items = []

    def resolve(self, pos, row_index):
        it = self.items[pos]
        if row_index not in it["candidates"]:
            raise ValueError("Row is not a candidate for this code.")
        it.update(row_index=row_index, candidates=[row_index], status=READY, checked=True)

    def remove_ids(self, ids):
        ids = set(ids)
        self.items = [it for it in self.items if it["id"] not in ids]

    # ---- queries
    def checked_ready(self):
        return [it for it in self.items if it["checked"] and it["status"] == READY and it["row_index"] is not None]

    def summary(self):
        ready = sum(1 for it in self.items if it["status"] == READY)
        chk = self.checked_ready()
        return {"total": len(self.items), "ready": ready, "checked": len(chk),
                "labels": sum(it["qty"] for it in chk), "issues": len(self.items) - ready}
