"""DataController: Excel / Google Sheet data rows, search, current row and saved sources."""
import os

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from ..paths import to_local_path
from ..core.binding import format_binding_value, resolve_row_value
from ..services.datasource_service import DataSet, fetch_google_sheet_rows
from ..services.settings_service import (load_sources, remember_excel_source, remember_google_source, save_sources)
from ..services.workspace_service import Workspace
from .models import RowsTableModel
from .tasks import run_async


def _local(path_or_url):
    return to_local_path(path_or_url)


class DataController(QObject):
    dataChanged = Signal()          # a different data set / sheet / filter
    rowChanged = Signal()           # current row changed (debounced) -> previews refresh
    currentChanged = Signal()       # current row index changed (immediate)
    sourcesChanged = Signal()
    loadingChanged = Signal()
    message = Signal(str)
    error = Signal(str, str)        # title, text

    def __init__(self, workspace: Workspace, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        self.ds = DataSet()
        self._model = RowsTableModel(self)
        self._loading = False
        self._query = ''
        self._selected_view_rows = []
        self._row_timer = QTimer(self)
        self._row_timer.setSingleShot(True)
        self._row_timer.setInterval(120)       # holding an arrow key must not re-render for every row
        self._row_timer.timeout.connect(self.rowChanged)

    # ------------------------------------------------------------------ python API
    def current_row_dict(self):
        return self.ds.current_row

    def rows_for(self, indices):
        return [self.ds.rows[i] for i in indices]

    # ------------------------------------------------------------------ properties
    def _get_model(self):
        return self._model

    rowsModel = Property(QObject, _get_model, constant=True)

    def _get_headers(self):
        return list(self.ds.headers)

    headers = Property('QStringList', _get_headers, notify=dataChanged)

    def _get_has_data(self):
        return bool(self.ds.rows)

    hasData = Property(bool, _get_has_data, notify=dataChanged)

    def _get_row_count(self):
        return len(self.ds.rows)

    rowCount = Property(int, _get_row_count, notify=dataChanged)

    def _get_filtered_count(self):
        return len(self.ds.filtered)

    filteredCount = Property(int, _get_filtered_count, notify=dataChanged)

    def _get_current(self):
        return self.ds.current

    currentIndex = Property(int, _get_current, notify=currentChanged)

    def _get_current_view_row(self):
        return self._model.viewRowOf(self.ds.current)

    currentViewRow = Property(int, _get_current_view_row, notify=currentChanged)

    def _get_row_label(self):
        return f"Row {self.ds.current + 1} / {len(self.ds.rows)}" if self.ds.rows else "No data rows"

    rowLabel = Property(str, _get_row_label, notify=currentChanged)

    def _get_source_label(self):
        return self.ds.label or 'No data loaded'

    sourceLabel = Property(str, _get_source_label, notify=dataChanged)

    def _get_sheet_names(self):
        return list(self.ds.sheet_names)

    sheetNames = Property('QStringList', _get_sheet_names, notify=dataChanged)

    def _get_sheet(self):
        return self.ds.sheet

    sheet = Property(str, _get_sheet, notify=dataChanged)

    def _get_loading(self):
        return self._loading

    loading = Property(bool, _get_loading, notify=loadingChanged)

    def _get_saved_sheets(self):
        return load_sources()['sheets']

    savedSheets = Property('QVariantList', _get_saved_sheets, notify=sourcesChanged)

    def _get_recent_excel(self):
        return [{'path': p, 'name': os.path.basename(p)} for p in load_sources()['excel'] if os.path.exists(p)]

    recentExcel = Property('QVariantList', _get_recent_excel, notify=sourcesChanged)

    def _get_google_defaults(self):
        return {'url': self.workspace.get('google_sheet_url', ''), 'tab': self.workspace.get('google_sheet_tab', 'LABEL DATA')}

    googleDefaults = Property('QVariant', _get_google_defaults, notify=sourcesChanged)

    # ------------------------------------------------------------------ internals
    def _set_loading(self, v):
        self._loading = v
        self.loadingChanged.emit()

    def _install(self, ds, note):
        self.ds.close()
        self.ds = ds
        self._query = ''
        self._selected_view_rows = []
        self._push_model()
        self.dataChanged.emit()
        self.currentChanged.emit()
        self.rowChanged.emit()
        self.sourcesChanged.emit()
        self.message.emit(note)

    def _push_model(self):
        self._model.set_data(self.ds.headers, self.ds.rows, self.ds.filtered)

    def _fail(self, title):
        def cb(msg):
            self._set_loading(False)
            self.error.emit(title, msg)
        return cb

    # ------------------------------------------------------------------ loading
    @Slot(str)
    def loadExcel(self, path_or_url):
        path = _local(path_or_url)
        self._set_loading(True)
        self.message.emit(f'Đang mở {os.path.basename(path)}…')

        def work():
            ds = DataSet()
            ds.load_excel(path, self.workspace.get('last_sheet') if self.workspace.get('last_excel_path') == path else None)
            return ds

        def done(ds):
            self._set_loading(False)
            remember_excel_source(path)
            self.workspace.update(last_excel_path=path, data_source='excel', last_sheet=ds.sheet)
            self._install(ds, f'Excel loaded: {os.path.basename(path)} — {len(ds.rows)} rows')

        run_async(work, done, self._fail('Excel error'))

    @Slot(str)
    def selectSheet(self, name):
        if self.ds.kind != 'excel' or name == self.ds.sheet:
            return
        old = self.ds
        self._set_loading(True)

        def work():
            tmp = DataSet()
            tmp.__dict__.update(old.__dict__)       # shares the open workbook; attributes are re-assigned on tmp only
            tmp.load_sheet(name)
            return tmp

        def done(ds):
            self._set_loading(False)
            self.ds = ds
            self.workspace.set('last_sheet', name)
            self._query = ''
            self._push_model()
            self.dataChanged.emit()
            self.currentChanged.emit()
            self.rowChanged.emit()
            self.message.emit(f'Trang tính: {name} — {len(ds.rows)} dòng')

        run_async(work, done, self._fail('Excel error'))

    @Slot(str, str, str)
    def loadGoogle(self, url, tab, name=''):
        url = (url or '').strip()
        tab = (tab or '').strip()
        self._set_loading(True)
        self.message.emit('Đang tải Google Sheet…')

        def work():
            headers, rows = fetch_google_sheet_rows(url, tab or None)
            if not headers:
                raise RuntimeError('No data found in the Google Sheet.')
            return headers, rows

        def done(res):
            self._set_loading(False)
            headers, rows = res
            entry = remember_google_source(url, tab or 'LABEL DATA', name or None)
            self.workspace.update(google_sheet_url=url, google_sheet_tab=tab or 'LABEL DATA', data_source='google')
            ds = DataSet()
            ds.set_google(headers, rows, url, tab or None, entry.get('name'))
            self._install(ds, f'Google Sheet loaded: {len(rows)} rows, {len(headers)} fields')

        run_async(work, done, self._fail('Google Sheet error'))

    @Slot(int)
    def loadSavedGoogle(self, i):
        sheets = load_sources()['sheets']
        if 0 <= i < len(sheets):
            it = sheets[i]
            self.loadGoogle(it['url'], it.get('tab') or '', it.get('name') or '')

    @Slot(int)
    def removeSavedGoogle(self, i):
        data = load_sources()
        if 0 <= i < len(data['sheets']):
            data['sheets'].pop(i)
            save_sources(data)
            self.sourcesChanged.emit()

    @Slot()
    def reload(self):
        src = self.workspace.get('data_source')
        if src == 'google' and self.workspace.get('google_sheet_url'):
            self.loadGoogle(self.workspace.get('google_sheet_url'), self.workspace.get('google_sheet_tab', ''), '')
        elif self.workspace.get('last_excel_path') and os.path.exists(self.workspace.get('last_excel_path')):
            self.loadExcel(self.workspace.get('last_excel_path'))
        else:
            self.error.emit('Reload Data', 'No saved data source. Load an Excel file or Google Sheet first.')

    def restore_last(self):
        """Quietly bring back the data source of the previous session."""
        src = self.workspace.get('data_source')
        p = self.workspace.get('last_excel_path')
        if src == 'google' and self.workspace.get('google_sheet_url'):
            self.reload()
        elif p and os.path.exists(p):
            self.loadExcel(p)

    # ------------------------------------------------------------------ navigation / search
    @Slot(str)
    def search(self, query):
        self._query = query
        self.ds.search(query)
        self._push_model()
        self.dataChanged.emit()
        self.currentChanged.emit()
        self._row_timer.start()

    @Slot(str)
    def searchEnter(self, query):
        idx = self.ds.best_match(query)
        if idx is not None:
            self._set_current(idx)

    def _set_current(self, source_index):
        if source_index == self.ds.current:
            self.currentChanged.emit()
            return
        self.ds.current = source_index
        self.currentChanged.emit()
        self._row_timer.start()

    def selectSource(self, source_index):
        """Make a data row current by its source index, clearing the search filter if it hides that row."""
        if source_index not in self.ds.filtered:
            self._query = ''
            self.ds.search('')
            self._push_model()
            self.dataChanged.emit()
        self._set_current(source_index)

    @Slot(int)
    def selectViewRow(self, view_row):
        i = self._model.sourceIndex(view_row)
        if i >= 0:
            self._set_current(i)

    @Slot(int)
    def step(self, delta):
        if not self.ds.filtered:
            return
        try:
            pos = self.ds.filtered.index(self.ds.current)
        except ValueError:
            pos = 0
        pos = max(0, min(len(self.ds.filtered) - 1, pos + delta))
        self._set_current(self.ds.filtered[pos])

    @Slot('QVariantList')
    def setSelectedViewRows(self, rows):
        self._selected_view_rows = sorted({int(r) for r in rows})

    def selected_source_indices(self):
        out = [self._model.sourceIndex(r) for r in self._selected_view_rows]
        return [i for i in out if i >= 0]

    def all_source_indices(self):
        return list(self.ds.filtered)

    # ------------------------------------------------------------------ field picker
    @Slot(str, result='QVariantList')
    def fieldSamples(self, query):
        q = (query or '').strip().casefold()
        row = self.ds.current_row or {}
        out = []
        for h in self.ds.headers:
            sample = format_binding_value(str(h), resolve_row_value(row, h)) if row else ''
            if q and q not in str(h).casefold() and q not in str(sample).casefold():
                continue
            out.append({'field': h, 'sample': sample})
        return out
