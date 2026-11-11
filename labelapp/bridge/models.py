"""Qt item models exposed to QML."""
import os

from PySide6.QtCore import QAbstractListModel, QAbstractTableModel, QModelIndex, Qt, Slot


class ElementListModel(QAbstractListModel):
    IndexRole, TypeRole, SummaryRole, LockedRole, SelectedRole, PrintedRole = (Qt.ItemDataRole.UserRole + i for i in range(1, 7))

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    def roleNames(self):
        return {self.IndexRole: b"index_", self.TypeRole: b"etype", self.SummaryRole: b"summary",
                self.LockedRole: b"locked", self.SelectedRole: b"selected", self.PrintedRole: b"printed"}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        r = self._rows[index.row()]
        return {self.IndexRole: r['index'], self.TypeRole: r['type'], self.SummaryRole: r['summary'],
                self.LockedRole: r['locked'], self.SelectedRole: r['selected'], self.PrintedRole: r['printed']}.get(role)

    @staticmethod
    def describe(e):
        txt = str(e.get('text', e.get('value', os.path.basename(str(e.get('path', '')))))).replace('\n', ' ')[:40]
        try:
            ang = float(e.get('angle', 0) or 0)
        except (TypeError, ValueError):
            ang = 0.0
        if not txt.strip():
            txt = ElementListModel._geometry(e)
        group = f"[{e['group_id']}] " if e.get('group_id') else ""
        return group + txt + (f"  ↻{ang:g}°" if abs(ang) > 1e-4 else "")

    @staticmethod
    def _geometry(e):
        """Shapes have no text: describe them by size (lines by length and direction) so list rows are distinguishable."""
        def num(k, d=0.0):
            try:
                return round(float(e.get(k, d) or 0), 2)
            except (TypeError, ValueError):
                return 0.0
        try:
            if str(e.get('type', '')).lower() == 'line':
                x, y = num('x'), num('y')
                dx, dy = num('x2', x + num('w')) - x, num('y2', y) - y
                if abs(dy) < 1e-6:
                    return f"— {abs(dx):g} mm  tại y {y:g}"
                if abs(dx) < 1e-6:
                    return f"| {abs(dy):g} mm  tại x {x:g}"
                return f"{round((dx * dx + dy * dy) ** 0.5, 2):g} mm  từ {x:g}, {y:g}"
            if 'w' in e or 'h' in e:
                return f"{num('w'):g} × {num('h'):g} mm  tại {num('x'):g}, {num('y'):g}"
        except Exception:
            pass
        return ''

    def sync(self, elements, selected):
        """Cheap incremental update: full reset only if the element count changes."""
        rows = [{'index': i, 'type': str(e.get('type', '?')), 'summary': self.describe(e),
                 'locked': bool(e.get('locked')), 'selected': i in selected,
                 'printed': e.get('print', True) is not False} for i, e in enumerate(elements)]
        if len(rows) != len(self._rows):
            self.beginResetModel()
            self._rows = rows
            self.endResetModel()
            return
        changed = [i for i, (a, b) in enumerate(zip(self._rows, rows)) if a != b]
        self._rows = rows
        for i in changed:
            ix = self.index(i)
            self.dataChanged.emit(ix, ix)


class RowsTableModel(QAbstractTableModel):
    """Filtered data rows. Column count follows the loaded headers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = []
        self._rows = []
        self._filtered = []

    def set_data(self, headers, rows, filtered):
        self.beginResetModel()
        self._headers, self._rows, self._filtered = list(headers), rows, list(filtered)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._filtered)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or not index.isValid():
            return None
        v = self._rows[self._filtered[index.row()]].get(self._headers[index.column()])
        return "" if v is None else (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v))

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._headers):
                return self._headers[section]
            if orientation == Qt.Orientation.Vertical:
                return section + 1
        return None

    @Slot(int, result=int)
    def sourceIndex(self, view_row):
        return self._filtered[view_row] if 0 <= view_row < len(self._filtered) else -1

    @Slot(int, result=int)
    def viewRowOf(self, source_index):
        try:
            return self._filtered.index(source_index)
        except ValueError:
            return -1


class QueueModel(QAbstractListModel):
    """Print queue: (row index, quantity) with a few columns of context for display."""
    RowRole, CellsRole, QtyRole, NumberRole = (Qt.ItemDataRole.UserRole + i for i in range(1, 5))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []         # dicts: row, cells, qty

    def roleNames(self):
        return {self.RowRole: b"row_", self.CellsRole: b"cells", self.QtyRole: b"qty", self.NumberRole: b"number"}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def data(self, index, role):
        if not index.isValid():
            return None
        it = self.items[index.row()]
        return {self.RowRole: it['row'], self.CellsRole: it['cells'], self.QtyRole: it['qty'],
                self.NumberRole: index.row() + 1}.get(role)

    def reset(self, items):
        self.beginResetModel()
        self.items = items
        self.endResetModel()

    def touch(self):
        if self.items:
            self.dataChanged.emit(self.index(0), self.index(len(self.items) - 1))


class ScanQueueModel(QAbstractListModel):
    """Batch Scan queue rows (scanned code, product summary, qty, checked, status)."""
    KEYS = ("code", "brand", "model", "price", "qty", "checked", "status", "ready")
    ROLES = {Qt.ItemDataRole.UserRole + 1 + i: k.encode() for i, k in enumerate(KEYS)}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def roleNames(self):
        return dict(self.ROLES)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role):
        key = self.ROLES.get(role)
        if not index.isValid() or key is None:
            return None
        return self.rows[index.row()].get(key.decode())

    def reset(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class InspectorModel(QAbstractListModel):
    """Property rows for the current selection. Updated in place while the field set is unchanged, so editors
    keep keyboard focus while values commit."""
    KEYS = ("key", "label", "kind", "group", "unit", "choices", "choice_labels", "value", "mixed")
    ROLES = {Qt.ItemDataRole.UserRole + 1 + i: k.encode() for i, k in enumerate(KEYS)}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    def roleNames(self):
        return dict(self.ROLES)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role):
        if not index.isValid():
            return None
        key = self.ROLES.get(role)
        if key is None:
            return None
        return self._rows[index.row()].get(key.decode(), '' if key != b'mixed' else False)

    def sync(self, fields):
        rows = [{k: f.get(k, '') for k in self.KEYS} for f in fields]
        if [r['key'] for r in rows] != [r['key'] for r in self._rows]:
            self.beginResetModel()
            self._rows = rows
            self.endResetModel()
            return
        for i, (a, b) in enumerate(zip(self._rows, rows)):
            if a != b:
                self._rows[i] = b
                ix = self.index(i)
                self.dataChanged.emit(ix, ix)
