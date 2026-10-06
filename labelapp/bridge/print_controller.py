"""PrintController: printer selection and every way of sending labels out (current label, queue, PDF proof/export).

All rendering/printing is delegated to labelapp.services.print_service / printer_service (the unchanged pipeline).
"""
import os

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from ..core.binding import bind_row_to_template
from ..services.print_service import PrintService, describe_route
from ..services.printer_service import enum_printers, is_virtual_printer_name, preferred_printer, printer_info, status_text
from .models import QueueModel
from .tasks import run_async


def _local(path_or_url):
    s = str(path_or_url)
    return QUrl(s).toLocalFile() if s.startswith('file:') else s


class PrintController(QObject):
    printersChanged = Signal()
    printerChanged = Signal()
    copiesChanged = Signal()
    busyChanged = Signal()
    progressChanged = Signal()
    queueChanged = Signal()
    message = Signal(str)
    error = Signal(str, str)                # title, text
    batchError = Signal(int, str)           # 1-based row number, message
    batchFinished = Signal(str)

    def __init__(self, workspace, document, data, service: PrintService, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        self.document = document
        self.data = data
        self.service = service
        self._printers = []
        self._printer = workspace.get('last_printer', '') or ''
        self._printers_loading = False
        self._copies = 1
        self._busy = False
        self._progress = 0.0
        self._progress_text = ''
        self._queue = QueueModel(self)
        self._queue_title = 'Print queue'
        self._batch = None
        self._batch_timer = QTimer(self)
        self._batch_timer.setSingleShot(True)
        self._batch_timer.timeout.connect(self._batch_step)
        document.committed.connect(self.sync_copies)
        data.rowChanged.connect(self.sync_copies)
        document.templateChanged.connect(self.sync_copies)

    # ------------------------------------------------------------------ properties
    def _get_printers(self):
        return self._printers

    printers = Property('QStringList', _get_printers, notify=printersChanged)

    def _get_printers_loading(self):
        return self._printers_loading

    printersLoading = Property(bool, _get_printers_loading, notify=printersChanged)

    def _get_printer(self):
        return self._printer

    def _set_printer(self, name):
        if name != self._printer:
            self._printer = name or ''
            self.workspace.set('last_printer', self._printer)
            self.printerChanged.emit()

    printer = Property(str, _get_printer, _set_printer, notify=printerChanged)

    def _get_route(self):
        return describe_route(self._printer) if self._printer else ''

    route = Property(str, _get_route, notify=printerChanged)

    def _get_virtual(self):
        return bool(self._printer) and is_virtual_printer_name(self._printer)

    isVirtualPrinter = Property(bool, _get_virtual, notify=printerChanged)

    def _get_copies(self):
        return self._copies

    def _set_copies(self, n):
        n = max(1, min(999, int(n)))
        if n != self._copies:
            self._copies = n
            self.copiesChanged.emit()

    copies = Property(int, _get_copies, _set_copies, notify=copiesChanged)

    def _get_busy(self):
        return self._busy

    busy = Property(bool, _get_busy, notify=busyChanged)

    def _get_progress(self):
        return self._progress

    progress = Property(float, _get_progress, notify=progressChanged)

    def _get_progress_text(self):
        return self._progress_text

    progressText = Property(str, _get_progress_text, notify=progressChanged)

    def _get_queue(self):
        return self._queue

    queueModel = Property(QObject, _get_queue, constant=True)

    def _get_queue_title(self):
        return self._queue_title

    queueTitle = Property(str, _get_queue_title, notify=queueChanged)

    def _get_queue_summary(self):
        items = self._queue.items
        return f"{len(items)} rows  ·  {sum(i['qty'] for i in items)} labels"

    queueSummary = Property(str, _get_queue_summary, notify=queueChanged)

    # ------------------------------------------------------------------ printers
    @Slot()
    def refreshPrinters(self):
        self._printers_loading = True
        self.printersChanged.emit()

        def done(printers):
            self._printers_loading = False
            self._printers = printers
            if self._printer not in printers:
                pref = preferred_printer(printers)
                if pref:
                    self._printer = pref
                    self.printerChanged.emit()
            self.printersChanged.emit()
            self.message.emit(f"Printers found: {len(printers)}" if printers else "No printers found by Windows.")

        def failed(msg):
            self._printers_loading = False
            self.printersChanged.emit()
            self.message.emit(f'Printer discovery failed: {msg}')

        run_async(enum_printers, done, failed)

    @Slot(result=str)
    def printerSummary(self):
        try:
            info = printer_info(self._validated_printer())
        except Exception as e:
            return f'Error: {e}'
        lines = [f"Printer: {info['name']}", f"Driver: {info['driver']}", f"Port: {info['port']}",
                 f"Status: {status_text(info['status'])}"]
        if info.get("paper_width_mm"): lines.append(f"Driver paper width: {info['paper_width_mm']} mm")
        if info.get("paper_length_mm"): lines.append(f"Driver paper length: {info['paper_length_mm']} mm")
        if info.get("orientation"): lines.append(f"Driver orientation: {info['orientation']}")
        lines += ["", "Windows cannot report the actual physical skew of the loaded paper."]
        return "\n".join(lines)

    def _validated_printer(self):
        if not self._printer:
            raise RuntimeError("No Windows printer is selected. Select a physical or virtual printer first.")
        return self._printer

    # ------------------------------------------------------------------ copies
    @Slot()
    def sync_copies(self):
        """Show the copy count the current label will really print with (template value or the row's Copies)."""
        try:
            n = int(self.document.bound_cfg().get('copies', 1))
        except Exception:
            n = 1
        if n != self._copies:
            self._copies = max(1, n)
            self.copiesChanged.emit()

    def _current_cfg(self):
        cfg = self.document.bound_cfg()
        cfg['copies'] = self._copies
        return cfg

    # ------------------------------------------------------------------ print current
    @Slot(result='QVariantMap')
    def preparePrint(self):
        """Checks before the confirmation dialog: printer, preflight. Never prints."""
        out = {'ok': False, 'errors': [], 'warnings': [], 'printer': self._printer}
        try:
            printer = self._validated_printer()
            cfg = self._current_cfg()
            errors, warnings = self.service.preflight(cfg)
        except Exception as e:
            out['errors'] = [str(e)]
            return out
        out.update(ok=not errors, errors=errors, warnings=warnings[:12], printer=printer, copies=cfg.get('copies', 1),
                   paper=f"{cfg.get('width_mm')} × {cfg.get('height_mm')} mm", dpi=cfg.get('dpi'), route=describe_route(printer))
        return out

    @Slot()
    def printCurrent(self):
        try:
            printer = self._validated_printer()
            cfg = self._current_cfg()
            row = self.data.current_row_dict()
            self.service.print_cfg(cfg, printer, row)
            self.service.record_history(cfg, printer, row, "Print Current", self.document.templateName)
            self.message.emit(f"Printed current label to {printer}")
        except Exception as e:
            self.error.emit('Print error', str(e))

    @Slot()
    def printViaDriver(self):
        try:
            printer = self._validated_printer()
            cfg = self._current_cfg()
            row = self.data.current_row_dict()
            self.service.print_via_driver(cfg, printer, row)
            self.service.record_history(cfg, printer, row, "Print via Driver/Virtual", self.document.templateName)
            self.message.emit(f"Vector PDF sent via Windows driver to {printer}")
        except Exception as e:
            self.error.emit('Driver / virtual print error', str(e))

    @Slot()
    def pdfProof(self):
        try:
            cfg = self._current_cfg()
            errors, _w = self.service.preflight(cfg)
            if errors:
                raise RuntimeError('\n'.join(errors))
            path, report = self.service.make_proof(cfg, self.data.current_row_dict())
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            self.message.emit(f'PDF proof created: {os.path.basename(path)}')
            self.error.emit('PDF proof created',
                            f"Vector 1:1 proof saved:\n{path}\n\n{report}\n\nNothing was printed.")
        except Exception as e:
            self.error.emit('PDF proof error', str(e))

    # ------------------------------------------------------------------ queue
    @Slot(str, result=bool)
    def openQueue(self, scope):
        """Build the queue from the selected rows or all (filtered) rows. False when there is nothing to queue."""
        if not self.data.hasData:
            self.error.emit('Print', 'Load an Excel file or Google Sheet first.')
            return False
        idxs = self.data.selected_source_indices() if scope == 'selected' else self.data.all_source_indices()
        if scope == 'selected' and not idxs:
            self.error.emit('Print selected', 'Select one or more rows in the Data tab first.')
            return False
        base = self.document.cfg
        copies_col = (base.get('data_bindings') or {}).get('Copies', 'Copies')
        headers = self.data.ds.headers[:6]
        items = []
        for i in idxs:
            row = self.data.ds.rows[i]
            try:
                q = int(float(row.get(copies_col) or 1))
            except Exception:
                q = 1
            items.append({'row': i, 'qty': max(1, q), 'cells': ["" if row.get(h) is None else str(row.get(h)) for h in headers]})
        self._queue_title = 'Print selected' if scope == 'selected' else 'Print all'
        self._queue.reset(items)
        self.queueChanged.emit()
        return True

    def _get_queue_columns(self):
        return self.data.ds.headers[:6]

    queueColumns = Property('QStringList', _get_queue_columns, notify=queueChanged)

    @Slot(int, int)
    def setQty(self, pos, qty):
        if 0 <= pos < len(self._queue.items):
            self._queue.items[pos]['qty'] = max(1, min(999, int(qty)))
            self._queue.touch()
            self.queueChanged.emit()

    @Slot(int)
    def setAllQty(self, qty):
        for it in self._queue.items:
            it['qty'] = max(1, min(999, int(qty)))
        self._queue.touch()
        self.queueChanged.emit()

    @Slot(int)
    def removeFromQueue(self, pos):
        if 0 <= pos < len(self._queue.items):
            items = list(self._queue.items)
            items.pop(pos)
            self._queue.reset(items)
            self.queueChanged.emit()

    @Slot(str, result=str)
    def exportQueuePdf(self, dest):
        items = self._queue.items
        if not items:
            return 'The queue is empty.'
        path = _local(dest)
        try:
            self.service.export_jobs_pdf(self.document.cfg, self.data.ds.rows, [(i['row'], i['qty']) for i in items], path)
        except Exception as e:
            return str(e)
        self.message.emit(f'PDF exported: {path}')
        return ''

    @Slot(result='QVariantMap')
    def prepareQueuePrint(self):
        out = {'ok': False, 'errors': [], 'warnings': []}
        items = self._queue.items
        if not items:
            out['errors'] = ['The queue is empty.']
            return out
        try:
            printer = self._validated_printer()
            first = bind_row_to_template(self.document.cfg, self.data.ds.rows[items[0]['row']])
            errors, warnings = self.service.preflight(first)
        except Exception as e:
            out['errors'] = [str(e)]
            return out
        out.update(ok=not errors, errors=errors, warnings=warnings[:12], printer=printer,
                   rows=len(items), labels=sum(i['qty'] for i in items))
        return out

    # ------------------------------------------------------------------ batch run (one job per event-loop tick)
    @Slot()
    def startQueue(self):
        """Print queued rows one per UI tick, with progress, cancel, and skip/retry/stop on errors."""
        if self._batch is not None:
            return
        try:
            printer = self._validated_printer()
        except Exception as e:
            self.error.emit('Print', str(e))
            return
        self._batch = {'jobs': [(i['row'], i['qty']) for i in self._queue.items], 'n': 0, 'failed': 0, 'cancel': False,
                       'waiting': False, 'printer': printer, 'base': self.document.cfg, 'action': self._queue_title}
        self._busy = True
        self._progress = 0.0
        self._progress_text = 'Starting…'
        self.busyChanged.emit()
        self.progressChanged.emit()
        self._batch_timer.start(50)

    def _finish_batch(self, text):
        self._batch = None
        self._busy = False
        self.busyChanged.emit()
        self.message.emit(text)
        self.batchFinished.emit(text)

    @Slot()
    def cancelBatch(self):
        if self._batch is not None:
            self._batch['cancel'] = True
            if self._batch['waiting']:
                self.batchDecision('stop')

    @Slot(str)
    def batchDecision(self, decision):
        b = self._batch
        if b is None or not b['waiting']:
            return
        b['waiting'] = False
        if decision == 'stop':
            self._finish_batch(f"{b['action']}: stopped at row {b['n'] + 1}.")
            return
        if decision == 'skip':
            b['failed'] += 1
            b['n'] += 1
            self._progress = b['n'] / max(1, len(b['jobs']))
            self.progressChanged.emit()
        self._batch_timer.start(5)

    def _batch_step(self):
        b = self._batch
        if b is None or b['waiting']:
            return
        jobs = b['jobs']
        if b['cancel']:
            self._finish_batch(f"{b['action']}: cancelled after {b['n']}/{len(jobs)} rows.")
            return
        if b['n'] >= len(jobs):
            tail = f" ({b['failed']} skipped)" if b['failed'] else ""
            self._finish_batch(f"{b['action']}: printed {len(jobs) - b['failed']} rows{tail}.")
            return
        i, q = jobs[b['n']]
        self._progress_text = f"Row {b['n'] + 1} of {len(jobs)}  ·  {q} label(s)"
        self.progressChanged.emit()
        try:
            row = self.data.ds.rows[i]
            cfg = bind_row_to_template(b['base'], row)
            cfg['copies'] = max(1, int(q))
            self.service.print_cfg(cfg, b['printer'], row)
            self.service.record_history(cfg, b['printer'], row, b['action'], self.document.templateName)
        except Exception as ex:
            b['waiting'] = True
            self.batchError.emit(i + 1, str(ex))
            return
        b['n'] += 1
        self._progress = b['n'] / max(1, len(jobs))
        self.progressChanged.emit()
        self._batch_timer.start(5)
