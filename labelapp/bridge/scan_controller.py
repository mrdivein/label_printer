"""ScanController: scan-then-print (quick scan / instant print) and the Batch Scan queue.

Lookup and queue rules live in labelapp.core.scan; printing is delegated to PrintController.
"""
from PySide6.QtCore import Property, QObject, Signal, Slot

from ..core.binding import missing_fields
from ..core.scan import ADD_ROW, INCREASE_QTY, READY, ScanIndex, ScanQueue
from ..core.suggest import SuggestIndex
from .models import ScanQueueModel

BATCH_ACTION = "Batch Scan Queue"


def _product(row):
    row = row or {}
    return (str(row.get("Brand", row.get("Brand Name", "")) or ""), str(row.get("Model", row.get("SKU", "")) or ""),
            str(row.get("Price", "") or ""))


class ScanController(QObject):
    statusChanged = Signal()
    settingsChanged = Signal()
    queueChanged = Signal()
    message = Signal(str)
    error = Signal(str, str)

    def __init__(self, workspace, data, printing, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        self.data = data
        self.printing = printing
        self._index = None
        self._rows_ref = None
        self._sindex = None
        self._status = ''
        self._status_kind = 'info'          # info | ok | error
        self._qty = 1
        self._instant = bool(workspace.get('qt_instant_print', False))
        self._repeat_mode = workspace.get('qt_scan_repeat', INCREASE_QTY)
        self._remove_after = bool(workspace.get('qt_scan_remove_printed', False))
        self._last_index = None
        self._queue = ScanQueue()
        self._model = ScanQueueModel(self)
        data.dataChanged.connect(self._invalidate)
        printing.jobsPrinted.connect(self._jobs_printed)

    # ------------------------------------------------------------------ index
    def _invalidate(self):
        """dataChanged also fires for searches; only a different row list means a different data set."""
        if self._rows_ref is not self.data.ds.rows:
            self._rows_ref = self.data.ds.rows
            self._index = None
            self._sindex = None
            if self._queue.items:           # row indices of the old data set are meaningless now
                self._queue.clear()
                self._sync()

    def index(self):
        self._invalidate()
        if self._index is None:
            self._index = ScanIndex(self.data.ds.headers, self.data.ds.rows)
        return self._index

    def _get_info(self):
        if not self.data.hasData:
            return 'No data loaded'
        ix = self.index()
        lengths = sorted({len(c) for c in ix.lookup})
        return (f"Data: {len(self.data.ds.rows)} row(s) | Barcode keys: {len(ix.lookup)} | "
                f"Columns: {', '.join(map(str, ix.columns)) or 'NOT FOUND'} | Lengths: {lengths or '-'}")

    dataInfo = Property(str, _get_info, notify=queueChanged)

    def _get_min_len(self):
        return self.index().min_length if self.data.hasData else 8

    minLength = Property(int, _get_min_len, notify=queueChanged)

    @Slot()
    def refreshIndex(self):
        self._index = None
        self._sindex = None
        self.queueChanged.emit()

    # ------------------------------------------------------------------ quick-scan state
    def _set_status(self, text, kind):
        self._status, self._status_kind = text, kind
        self.statusChanged.emit()

    status = Property(str, lambda self: self._status, notify=statusChanged)
    statusKind = Property(str, lambda self: self._status_kind, notify=statusChanged)

    def _set_instant(self, v):
        if bool(v) != self._instant:
            self._instant = bool(v)
            self.workspace.set('qt_instant_print', self._instant)
            self.settingsChanged.emit()

    instantPrint = Property(bool, lambda self: self._instant, _set_instant, notify=settingsChanged)

    def _set_qty(self, v):
        v = max(1, min(999, int(v)))
        if v != self._qty:
            self._qty = v
            self.settingsChanged.emit()

    qty = Property(int, lambda self: self._qty, _set_qty, notify=settingsChanged)
    hasLast = Property(bool, lambda self: self._last_index is not None, notify=statusChanged)

    # ------------------------------------------------------------------ quick scan / instant print
    def _missing(self, row_index):
        """Empty data fields the current template needs for this row (Instant print refuses to print them)."""
        return missing_fields(self.printing.document.cfg, self.data.ds.rows[row_index])

    def _blocked_status(self, row_index, missing):
        brand, model, _p = _product(self.data.ds.rows[row_index])
        return (f"NOT PRINTED - missing data: {', '.join(missing)} | row {row_index + 2} {brand} {model}").rstrip()

    @Slot(str, result=bool)
    def quickScan(self, raw):
        """Resolve a scanned code, show its row and (with Instant print on) print it. True = clear the input."""
        raw = (raw or '').strip()
        if not raw:
            return False
        if not self.data.hasData:
            self._set_status('Load Excel / Google Sheet first.', 'error')
            return False
        ix = self.index()
        if not ix.columns:
            self._set_status('No UPC / EAN / Barcode column found.', 'error')
            return False
        status, codes = ix.resolve(raw)
        if status == 'duplicate':
            self._set_status(f"{codes[0]}: duplicate x{len(ix.lookup[codes[0]])}. Not printed.", 'error')
            return True
        if status == 'ambiguous':
            self._set_status('Ambiguous glued scan. Nothing printed.', 'error')
            return True
        if status != 'ok':
            self._set_status(f"NOT FOUND: {codes[0] if codes else raw}", 'error')
            return True
        if self._instant:                    # all-or-nothing: one incomplete row stops the whole scan, nothing printed
            for c in codes:
                idx = ix.lookup[c][0]
                miss = self._missing(idx)
                if miss:
                    self._last_index = idx
                    self.data.selectSource(idx)
                    self._set_status(self._blocked_status(idx, miss), 'error')
                    return True
        printed = 0
        try:
            for c in codes:
                idx = ix.lookup[c][0]
                self._last_index = idx
                self.data.selectSource(idx)
                if self._instant:
                    self.printing.print_row(idx, self._qty, 'Instant Scan Print')
                    printed += self._qty
        except Exception as e:
            self._set_status(f"PRINT ERROR: {e}", 'error')
            return True
        brand, model, _p = _product(self.data.ds.rows[self._last_index])
        tail = f"{codes[-1]} | {brand} {model}".rstrip()
        self._set_status(f"PRINTED {printed} label(s) | {tail}" if self._instant else f"FOUND | {tail}", 'ok')
        return True

    # ------------------------------------------------------------------ type-ahead (Instant print OFF)
    def _suggest_index(self):
        self._invalidate()
        if self._sindex is None:
            self._sindex = SuggestIndex(self.data.ds.headers, self.data.ds.rows)
        return self._sindex

    @Slot(str, result='QVariantList')
    def suggest(self, query, limit=8):
        """Best matches for a partial UPC / SKU / name / brand. Instant print needs exact codes, so no suggestions then."""
        if self._instant or not self.data.hasData:
            return []
        sx = self._suggest_index()
        return [sx.describe(i) for i in sx.search(query, limit)]

    @Slot(str, result=bool)
    def isExactCode(self, raw):
        """True when the text is complete scanner input (one or more whole barcodes of the loaded data)."""
        if not self.data.hasData:
            return False
        return self.index().resolve(raw)[0] in ('ok', 'duplicate')

    @Slot(int)
    def pick(self, row_index):
        """Choose a suggestion: show the row (and allow Print last) without printing."""
        if not (self.data.hasData and 0 <= row_index < len(self.data.ds.rows)):
            return
        self._last_index = row_index
        self.data.selectSource(row_index)
        brand, model, _p = _product(self.data.ds.rows[row_index])
        self._set_status(f"FOUND | {brand} {model}".rstrip(), 'ok')

    @Slot(str, int, result=bool)
    def submit(self, raw, picked_index):
        """Enter in the scan box. Instant print: exact scan + print. Otherwise a whole code is selected, else the
        highlighted (picked_index >= 0) or best suggestion. True = clear the input."""
        raw = (raw or '').strip()
        if self._instant or not raw:
            return self.quickScan(raw)
        if picked_index >= 0:
            self.pick(picked_index)
            return True
        if self.isExactCode(raw):
            return self.quickScan(raw)
        hits = self.suggest(raw, 1)
        if hits:
            self.pick(hits[0]['index'])
            return True
        self._set_status(f"NO MATCH: {raw}", 'error')
        return False

    @Slot()
    def printLast(self):
        if self._last_index is None or not self.data.hasData or self._last_index >= len(self.data.ds.rows):
            self.error.emit('Print last', 'No resolved scan yet.')
            return
        miss = self._missing(self._last_index)
        if miss:
            self._set_status(self._blocked_status(self._last_index, miss), 'error')
            return
        try:
            self.printing.print_row(self._last_index, self._qty, 'Instant Scan Print')
        except Exception as e:
            self.error.emit('Print last', str(e))
            return
        brand, model, _p = _product(self.data.ds.rows[self._last_index])
        self._set_status(f"PRINTED {self._qty} | {brand} {model}", 'ok')

    # ------------------------------------------------------------------ batch queue
    queueModel = Property(QObject, lambda self: self._model, constant=True)

    def _set_repeat(self, v):
        v = ADD_ROW if v == ADD_ROW else INCREASE_QTY
        if v != self._repeat_mode:
            self._repeat_mode = v
            self.workspace.set('qt_scan_repeat', v)
            self.settingsChanged.emit()

    repeatMode = Property(str, lambda self: self._repeat_mode, _set_repeat, notify=settingsChanged)

    def _set_remove(self, v):
        if bool(v) != self._remove_after:
            self._remove_after = bool(v)
            self.workspace.set('qt_scan_remove_printed', self._remove_after)
            self.settingsChanged.emit()

    removeAfterPrint = Property(bool, lambda self: self._remove_after, _set_remove, notify=settingsChanged)

    def _get_summary(self):
        s = self._queue.summary()
        return (f"Queue: {s['total']} | Ready: {s['ready']} | Checked: {s['checked']} | "
                f"Labels: {s['labels']} | Issues: {s['issues']}")

    summary = Property(str, _get_summary, notify=queueChanged)

    def _get_checked_labels(self):
        return self._queue.summary()['labels']

    checkedLabels = Property(int, _get_checked_labels, notify=queueChanged)

    def _sync(self):
        rows = []
        for it in self._queue.items:
            i = it['row_index']
            row = self.data.ds.rows[i] if i is not None and 0 <= i < len(self.data.ds.rows) else {}
            brand, model, price = _product(row)
            rows.append({'code': it['code'], 'brand': brand, 'model': model, 'price': price, 'qty': it['qty'],
                         'checked': it['checked'], 'status': it['status'], 'ready': it['status'] == READY})
        self._model.reset(rows)
        self.queueChanged.emit()

    @Slot(str)
    def process(self, raw):
        if not (raw or '').strip():
            return
        if not self.data.hasData or not self.index().lookup:
            self.error.emit('Batch Scan', 'No barcode index is available. Load Excel/Google Sheet first.')
            return
        self._queue.add_raw(self.index(), raw, self._repeat_mode)
        self._sync()

    @Slot(int)
    def toggle(self, pos):
        self._queue.toggle(pos)
        self._sync()

    @Slot(bool)
    def setAllChecked(self, checked):
        self._queue.set_all_checked(checked)
        self._sync()

    @Slot(int, int)
    def setQty(self, pos, qty):
        self._queue.set_qty(pos, qty)
        self._sync()

    @Slot(int)
    def remove(self, pos):
        self._queue.remove(pos)
        self._sync()

    @Slot()
    def clearQueue(self):
        self._queue.clear()
        self._sync()

    @Slot(int)
    def showInEditor(self, pos):
        if 0 <= pos < len(self._queue.items) and self._queue.items[pos]['row_index'] is not None:
            self.data.selectSource(self._queue.items[pos]['row_index'])

    @Slot(int, result='QVariantList')
    def candidates(self, pos):
        """Rows a DUPLICATE queue entry could mean."""
        if not 0 <= pos < len(self._queue.items):
            return []
        out = []
        for i in self._queue.items[pos]['candidates']:
            brand, model, price = _product(self.data.ds.rows[i])
            out.append({'index': i, 'sheetRow': i + 2, 'brand': brand, 'model': model, 'price': price})
        return out

    @Slot(int, int)
    def resolveDuplicate(self, pos, row_index):
        try:
            self._queue.resolve(pos, row_index)
        except Exception as e:
            self.error.emit('Resolve duplicate', str(e))
            return
        self._sync()

    @Slot(result='QVariantMap')
    def prepareBatch(self):
        out = {'ok': False, 'errors': [], 'warnings': []}
        items = self._queue.checked_ready()
        if not items:
            out['errors'] = ['No READY queue rows are checked for printing.']
            return out
        try:
            printer = self.printing._validated_printer()
        except Exception as e:
            out['errors'] = [str(e)]
            return out
        from ..core.binding import bind_row_to_template
        errors, warnings = [], []
        for it in items:
            cfg = bind_row_to_template(self.printing.document.cfg, self.data.ds.rows[it['row_index']])
            cfg['copies'] = it['qty']                        # scan Qty overrides the row's Copies column
            es, ws = self.printing.service.preflight(cfg)
            errors += [f"{it['code']}: " + '; '.join(es[:3])] if es else []
            warnings += [f"{it['code']}: {w}" for w in ws[:3]]
        out.update(ok=not errors, errors=errors[:12], warnings=warnings[:10], printer=printer, products=len(items),
                   labels=sum(it['qty'] for it in items))
        return out

    @Slot()
    def printChecked(self):
        items = self._queue.checked_ready()
        if items:
            self.printing.startJobs([(it['row_index'], it['qty']) for it in items], BATCH_ACTION, [it['id'] for it in items])

    def _jobs_printed(self, action, ids):
        if action != BATCH_ACTION:
            return
        if self._remove_after and ids:
            self._queue.remove_ids(ids)
            self._sync()
