"""DocumentController: the label being designed.

Owns a LabelEditor (all editing rules live in labelapp.core.editor) and exposes its state to QML:
paper settings, element list, selection, inspector schema/values, canvas overlay geometry and the rendered
workspace image. QML only forwards user intent (pointer positions in millimetres, property edits, commands).
"""
import copy

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ..core.binding import bind_row_to_template
from ..core.designer_geometry import render_workspace
from ..core.editor import DOC_CHOICE_KEYS, DOC_NUMBER_KEYS, TYPE_LABELS, LabelEditor
from ..core.designer_geometry import virtual_area
from ..core.models import is_printed, normalize_cfg
from ..services.template_service import TemplateService
from ..services.workspace_service import Workspace
from .models import ElementListModel, InspectorModel
from .preview_provider import PREVIEW_TRANSPARENT, pil_to_qimage
from .tasks import run_async

RENDER_SCALE = 2                # preview supersampling relative to printer DPI (same as the Tk designer)
DOC_KEYS = DOC_NUMBER_KEYS + tuple(DOC_CHOICE_KEYS)

# The editor's status notes are short English keys (tests and the Tk app use them); the Qt UI shows Vietnamese.
NOTES_VI = {
    'Undo': 'Đã hoàn tác', 'Redo': 'Đã làm lại', 'Printer profile loaded': 'Đã nạp hồ sơ máy in',
    'Paper settings changed': 'Đã đổi cài đặt khổ tem', 'Free text added': 'Đã thêm chữ',
    'Dynamic field(s) added': 'Đã thêm trường dữ liệu', 'Element added': 'Đã thêm phần tử', 'Shape added': 'Đã thêm hình',
    'Element(s) deleted': 'Đã xoá phần tử', 'Duplicated': 'Đã nhân bản', 'Pasted': 'Đã dán', 'Centered': 'Đã căn giữa',
    'Aligned': 'Đã căn chỉnh', 'Moved': 'Đã di chuyển', 'Layer order changed': 'Đã đổi thứ tự lớp', 'Rotated': 'Đã xoay',
    'Font size changed': 'Đã đổi cỡ chữ', 'Locked': 'Đã khoá', 'Unlocked': 'Đã mở khoá',
    'All elements unlocked': 'Đã mở khoá tất cả', 'Virtual area visible': 'Đã hiện vùng in', 'Fold region added': 'Đã thêm vùng gập',
    'Fold moved': 'Đã dời đường gập', 'Resized': 'Đã đổi kích thước', 'Print area resized': 'Đã đổi vùng in',
    'Changed': 'Đã thay đổi', 'Grouped': 'Đã nhóm', 'Ungrouped': 'Đã bỏ nhóm',
    'Print on': 'Đã bật in phần tử', 'Print off': 'Đã tắt in phần tử (vẫn giữ trên tem)',
}


def note_vi(note):
    if note in NOTES_VI:
        return NOTES_VI[note]
    if note.endswith(' changed'):
        return 'Đã đổi ' + note[:-len(' changed')].lower()
    if note.startswith('Copied '):
        return 'Đã sao chép ' + note[len('Copied '):].replace(' element(s)', ' phần tử')
    return note


class DocumentController(QObject):
    templateChanged = Signal()
    templateLoaded = Signal()      # a different template (or reload) replaced the document
    docChanged = Signal()
    selectionChanged = Signal()
    overlayChanged = Signal()
    previewChanged = Signal()
    ghostChanged = Signal()
    historyChanged = Signal()
    viewOptionsChanged = Signal()
    message = Signal(str)
    committed = Signal()        # any change to the document (used by other controllers)

    def __init__(self, templates: TemplateService, workspace: Workspace, provider, parent=None):
        super().__init__(parent)
        self.templates = templates
        self.workspace = workspace
        self.provider = provider
        self.editor = LabelEditor()
        self.row_provider = lambda: None           # set by the composition root: current data row
        self._template_name = ''
        self._elements_model = ElementListModel(self)
        self._inspector_model = InspectorModel(self)
        self._preview_version = 0
        self._workspace_rect = {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0}
        self._preview_error = ''
        self._ghost = {}
        self._overlay = {}
        self._show_guides = True
        self._show_fold = True
        self._dirty = False
        self._render_busy = False
        self._render_again = False
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(0)
        self._render_timer.timeout.connect(self._render)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._write_working_copy)

    # ------------------------------------------------------------------ plain-python helpers
    @property
    def cfg(self):
        return self.editor.cfg

    def bound_cfg(self):
        """Template with the current data row applied (what is previewed and printed)."""
        row = self.row_provider()
        return bind_row_to_template(self.cfg, row) if row else normalize_cfg(copy.deepcopy(self.cfg))

    def set_snap(self, mm):
        self.editor.snap_mm = float(mm)

    def load_cfg(self, cfg, name, dirty=False):
        self._template_name = name
        self.editor.load(cfg)
        self._dirty = dirty
        self._refresh_all()
        self.templateChanged.emit()
        self.historyChanged.emit()
        self.templateLoaded.emit()

    # ------------------------------------------------------------------ properties
    def _get_template_name(self):
        return self._template_name

    templateName = Property(str, _get_template_name, notify=templateChanged)

    def _get_dirty(self):
        return self._dirty

    dirty = Property(bool, _get_dirty, notify=templateChanged)

    def _get_doc(self):
        c = self.cfg
        d = {k: c.get(k) for k in DOC_KEYS}
        d['virtual_area_show'] = bool(virtual_area(c).get('show', True))
        return d

    doc = Property('QVariant', _get_doc, notify=docChanged)

    def _get_workspace(self):
        return self._workspace_rect

    workspaceRect = Property('QVariant', _get_workspace, notify=previewChanged)

    def _get_preview_source(self):
        return f"image://preview/workspace?v={self._preview_version}"

    previewSource = Property(str, _get_preview_source, notify=previewChanged)

    def _get_preview_error(self):
        return self._preview_error

    previewError = Property(str, _get_preview_error, notify=previewChanged)

    def _get_overlay(self):
        return self._overlay

    overlay = Property('QVariant', _get_overlay, notify=overlayChanged)

    def _get_ghost(self):
        return self._ghost

    ghost = Property('QVariant', _get_ghost, notify=ghostChanged)

    def _get_inspector_model(self):
        return self._inspector_model

    inspectorModel = Property(QObject, _get_inspector_model, constant=True)

    def _get_selection_title(self):
        n = len(self.editor.selected)
        if n == 0:
            return ''
        if n > 1:
            return f'Nhóm · {n} phần tử' if self.editor.selection_is_group else f'{n} phần tử'
        e = self.cfg['elements'][next(iter(self.editor.selected))]
        return (self.typeLabel(str(e.get('type', ''))) + (' — đã khoá' if e.get('locked') else '')
                + ('' if is_printed(e) else ' — không in'))

    selectionTitle = Property(str, _get_selection_title, notify=selectionChanged)

    def _get_selection(self):
        return sorted(self.editor.selected)

    selection = Property('QVariantList', _get_selection, notify=selectionChanged)

    def _get_selection_count(self):
        return len(self.editor.selected)

    selectionCount = Property(int, _get_selection_count, notify=selectionChanged)

    def _get_sel_locked(self):
        return bool(self.editor.selected) and all(self.cfg['elements'][i].get('locked') for i in self.editor.selected)

    selectionLocked = Property(bool, _get_sel_locked, notify=selectionChanged)

    def _get_sel_printed(self):
        """False only when every selected element is switched off for printing."""
        return not self.editor.selected or any(is_printed(self.cfg['elements'][i]) for i in self.editor.selected)

    selectionPrinted = Property(bool, _get_sel_printed, notify=selectionChanged)

    def _get_can_group(self):
        return self.editor.can_group

    canGroup = Property(bool, _get_can_group, notify=selectionChanged)

    def _get_can_ungroup(self):
        return self.editor.can_ungroup

    canUngroup = Property(bool, _get_can_ungroup, notify=selectionChanged)

    def _get_selection_is_group(self):
        return self.editor.selection_is_group

    selectionIsGroup = Property(bool, _get_selection_is_group, notify=selectionChanged)

    def _get_elements_model(self):
        return self._elements_model

    elementsModel = Property(QObject, _get_elements_model, constant=True)

    def _get_can_undo(self):
        return self.editor.can_undo

    canUndo = Property(bool, _get_can_undo, notify=historyChanged)

    def _get_can_redo(self):
        return self.editor.can_redo

    canRedo = Property(bool, _get_can_redo, notify=historyChanged)

    def _get_has_clipboard(self):
        return bool(self.editor.clipboard)

    hasClipboard = Property(bool, _get_has_clipboard, notify=historyChanged)

    def _get_show_guides(self):
        return self._show_guides

    def _set_show_guides(self, v):
        if v != self._show_guides:
            self._show_guides = bool(v)
            self.viewOptionsChanged.emit()
            self._schedule_render()

    showGuides = Property(bool, _get_show_guides, _set_show_guides, notify=viewOptionsChanged)

    def _get_show_fold(self):
        return self._show_fold

    def _set_show_fold(self, v):
        if v != self._show_fold:
            self._show_fold = bool(v)
            self.viewOptionsChanged.emit()
            self._schedule_render()

    showFold = Property(bool, _get_show_fold, _set_show_fold, notify=viewOptionsChanged)

    def _get_snap(self):
        return self.editor.snap_mm

    def _set_snap(self, v):
        self.editor.snap_mm = max(0.0, float(v))
        self.viewOptionsChanged.emit()

    snapMm = Property(float, _get_snap, _set_snap, notify=viewOptionsChanged)

    def _get_paper_rect(self):
        c = self.cfg
        return {'x': 0.0, 'y': 0.0, 'w': float(c.get('width_mm', 50)), 'h': float(c.get('height_mm', 68))}

    paperRect = Property('QVariant', _get_paper_rect, notify=docChanged)

    # ------------------------------------------------------------------ refresh plumbing
    def _refresh_all(self):
        self._refresh_selection()
        self._refresh_overlay()
        self.docChanged.emit()
        self._schedule_render()

    def _refresh_selection(self):
        ed = self.editor
        self._inspector_model.sync(ed.inspector_fields())
        self._elements_model.sync(self.cfg['elements'], ed.selected)
        self.selectionChanged.emit()

    def _refresh_overlay(self):
        self._overlay = self.editor.overlay()
        self.overlayChanged.emit()

    def _schedule_render(self):
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _render(self):
        """Render the workspace in the thread pool so editing, dragging and typing never wait for it.

        At most one render runs at a time; requests arriving meanwhile are coalesced into a single follow-up render
        of the latest document, so a burst of edits costs two renders, not one per edit."""
        if self._render_busy:
            self._render_again = True
            return
        try:
            snapshot = self.bound_cfg()           # deep copy taken on the UI thread; the worker never sees self.cfg
        except Exception as e:
            self._render_failed(str(e))
            return
        show_guides, show_fold = self._show_guides, self._show_fold

        def job():
            img, m = render_workspace(snapshot, snapshot, scale=RENDER_SCALE,
                                      show_guides=show_guides, show_fold=show_fold)
            return pil_to_qimage(img, PREVIEW_TRANSPARENT), m

        self._render_busy = True
        self._render_again = False
        run_async(job, self._render_done, self._render_failed)

    def _render_done(self, result):
        qimage, m = result
        self.provider.set_qimage('workspace', qimage)
        self._workspace_rect = {'x': m['x'], 'y': m['y'], 'w': m['w'], 'h': m['h']}
        self._preview_version += 1
        self._preview_error = ''
        self._render_finished()

    def _render_failed(self, message):
        self._preview_error = f'Lỗi xem trước: {message}'
        self._render_finished()

    def _render_finished(self):
        self._render_busy = False
        self.previewChanged.emit()
        if self._render_again:
            self._schedule_render()

    def wait_for_render(self, timeout_ms=5000):
        """Block (processing events) until no preview render is pending. For tests and scripted use."""
        import time
        from PySide6.QtCore import QCoreApplication
        end = time.monotonic() + timeout_ms / 1000.0
        while (self._render_busy or self._render_timer.isActive()) and time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.002)                     # releases the GIL so the render worker can run
        return not (self._render_busy or self._render_timer.isActive())

    def _write_working_copy(self):
        self.workspace.save_working_copy(self.cfg, self._template_name)

    def flush(self):
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._write_working_copy()

    def _commit(self, note):
        """A command changed the document: refresh everything that depends on it."""
        if note is None:
            return False
        self._dirty = True
        self._refresh_selection()
        self._refresh_overlay()
        self.docChanged.emit()
        self.templateChanged.emit()
        self.historyChanged.emit()
        self._schedule_render()
        self._save_timer.start()
        self.message.emit(f"{note_vi(note)} — đã áp dụng khi in, chưa lưu vào mẫu.")
        self.committed.emit()
        return True

    # ------------------------------------------------------------------ selection / view
    @Slot(float)
    def setViewScale(self, px_per_mm):
        """Zoom changed (screen pixels per millimetre): handle sizes / hit tolerances are in pixels."""
        if px_per_mm > 0:
            self.editor.view_mm_per_px = 1.0 / px_per_mm
            self._refresh_overlay()

    @Slot(int, bool)
    def selectIndex(self, index, additive=False):
        ed = self.editor
        if additive:
            ns = set(ed.selected)
            ns.symmetric_difference_update({index})
            ed.set_selection(ns, index if index in ns else None)
        else:
            ed.set_selection({index}, index)
        self._refresh_selection()
        self._refresh_overlay()

    @Slot()
    def selectAll(self):
        self.editor.select_all()
        self._refresh_selection()
        self._refresh_overlay()

    @Slot()
    def clearSelection(self):
        self.editor.set_selection(set(), None)
        self._refresh_selection()
        self._refresh_overlay()

    # ------------------------------------------------------------------ pointer interaction (millimetres)
    @Slot(float, float, bool, result=str)
    def pointerPress(self, x, y, shift):
        before = set(self.editor.selected)
        mode = self.editor.press(x, y, shift)
        if set(self.editor.selected) != before:
            self._refresh_selection()
        self._refresh_overlay()
        return mode

    @Slot(float, float, bool)
    def pointerMove(self, x, y, shift):
        g = self.editor.drag_ghost(x, y, shift)
        self._ghost = g or {}
        self.ghostChanged.emit()

    @Slot(float, float, bool)
    def pointerRelease(self, x, y, shift):
        before = set(self.editor.selected)
        note = self.editor.release(x, y, shift)
        self._ghost = {}
        self.ghostChanged.emit()
        if note:
            self._commit(note)
        else:
            if set(self.editor.selected) != before:
                self._refresh_selection()
            self._refresh_overlay()

    @Slot()
    def pointerCancel(self):
        self.editor.cancel_drag()
        self._ghost = {}
        self.ghostChanged.emit()

    @Slot(float, float, result='QVariantMap')
    def hover(self, x, y):
        return self.editor.hover(x, y)

    @Slot(float, float, result=int)
    def hitElement(self, x, y):
        i = self.editor.hit_element(x, y)
        return -1 if i is None else i

    @Slot(int, result=str)
    def elementText(self, i):
        e = self.cfg['elements'][i] if 0 <= i < len(self.cfg['elements']) else {}
        return str(e.get('text', ''))

    @Slot(int, result=str)
    def elementType(self, i):
        e = self.cfg['elements'][i] if 0 <= i < len(self.cfg['elements']) else {}
        return str(e.get('type', ''))

    @Slot(str, result=str)
    def typeLabel(self, etype):
        return TYPE_LABELS.get(etype, etype.replace('_', ' ').capitalize())

    @Slot(int, result=bool)
    def elementBold(self, i):
        e = self.cfg['elements'][i] if 0 <= i < len(self.cfg['elements']) else {}
        return bool(e.get('bold'))

    # ------------------------------------------------------------------ edits
    @Slot(str, 'QVariant')
    def setProp(self, key, value):
        self._commit(self.editor.set_prop(key, value))

    @Slot(str, 'QVariant')
    def setDoc(self, key, value):
        if key == 'virtual_area_show':
            self._commit(self.editor.set_doc(virtual_area_show=bool(value)))
        else:
            self._commit(self.editor.set_doc(**{key: value}))

    @Slot('QVariantMap')
    def setDocMany(self, values):
        self._commit(self.editor.set_doc(**dict(values)))

    def apply_profile(self, profile):
        self._commit(self.editor.apply_profile(profile))

    @Slot()
    def undo(self):
        n = self.editor.undo()
        if n:
            self._commit(n)

    @Slot()
    def redo(self):
        n = self.editor.redo()
        if n:
            self._commit(n)

    @Slot(str)
    def addText(self, text):
        self._commit(self.editor.add_text(text or 'Chữ mới'))

    @Slot(str, float, bool, float, float)
    def addTextStyled(self, text, font_size, bold, w, h):
        """Palette presets (title / subtitle / body): same text element, different starting style and box."""
        self._commit(self.editor.add_text(text or 'Chữ mới', font_size, bold, w, h))

    @Slot('QStringList', bool)
    def addFields(self, fields, as_barcode):
        self._commit(self.editor.add_fields(list(fields), as_barcode))

    @Slot(str)
    def addSpecial(self, kind):
        self._commit(self.editor.add_special(kind))

    @Slot(str)
    def addImage(self, path):
        self._commit(self.editor.add_special('image', path))

    @Slot(str)
    def addSymbol(self, key):
        self._commit(self.editor.add_symbol(key))

    @Slot(str)
    def addShape(self, kind):
        self._commit(self.editor.add_shape(kind))

    @Slot(int, str)
    def setElementText(self, index, text):
        self._commit(self.editor.set_element_text(index, text))

    @Slot()
    def groupSelected(self):
        self._commit(self.editor.group_selected())

    @Slot()
    def ungroupSelected(self):
        self._commit(self.editor.ungroup_selected())

    @Slot()
    def deleteSelected(self):
        self._commit(self.editor.delete_selected())

    @Slot()
    def duplicateSelected(self):
        self._commit(self.editor.duplicate_selected())

    @Slot()
    def copySelected(self):
        n = self.editor.copy_selected()
        if n:
            self.historyChanged.emit()
            self.message.emit(note_vi(n) + ' — Ctrl+V để dán')

    @Slot()
    def paste(self):
        self._commit(self.editor.paste())

    @Slot(str)
    def centerOnLabel(self, axis):
        self._commit(self.editor.center_on_label(axis))

    @Slot(str)
    def align(self, mode):
        self._commit(self.editor.align_selected(mode))

    @Slot(int, int, bool)
    def nudge(self, sx, sy, big):
        self._commit(self.editor.nudge(sx, sy, big))

    @Slot(int)
    def reorder(self, delta):
        self._commit(self.editor.reorder(delta))

    @Slot(float)
    def rotateBy(self, delta):
        self._commit(self.editor.rotate_selected(delta))

    @Slot()
    def resetRotation(self):
        self._commit(self.editor.rotate_selected(None))

    @Slot(int)
    def changeFontSize(self, direction):
        self._commit(self.editor.change_font_size(direction))

    @Slot(bool)
    def setLocked(self, value):
        self._commit(self.editor.set_lock_selected(value))

    @Slot(bool)
    def setPrinted(self, value):
        """Print / do not print the selected elements (they stay on the template)."""
        self._commit(self.editor.set_print(sorted(self.editor.selected), bool(value)))

    @Slot(int)
    def togglePrint(self, index):
        """Element-list switch: print / do not print one element without changing the selection."""
        self._commit(self.editor.toggle_print(index))

    @Slot()
    def unlockAll(self):
        self._commit(self.editor.unlock_all())

    @Slot()
    def showVirtualArea(self):
        self._commit(self.editor.show_virtual_area())

    @Slot()
    def ensureFoldLine(self):
        n = self.editor.ensure_fold_line()
        self._commit(n or None)
        if n is None:
            self.message.emit('Kéo đường gập màu cam lên/xuống. Các phần tử mặt sau giữ nguyên vị trí nhìn thấy.')

    # ------------------------------------------------------------------ template persistence
    @Slot(str, result=str)
    def openTemplate(self, name):
        """Load a library template. Returns '' on success or an error message."""
        try:
            cfg = self.templates.load(name)
        except Exception as e:
            return str(e)
        self.workspace.clear_working_copy()
        self.load_cfg(cfg, name)
        self.workspace.set('last_template', name)
        self.message.emit(f'Đã mở mẫu: {name}')
        return ''

    @Slot(result=str)
    def saveTemplate(self):
        """Save into the library under the current name. Returns '' on success, 'needs_name' or an error."""
        if not self._template_name:
            return 'needs_name'
        try:
            self.templates.save(self._template_name, self.cfg)
        except Exception as e:
            return str(e)
        self._dirty = False
        self.workspace.clear_working_copy()
        self.templateChanged.emit()
        self.message.emit(f'Đã lưu mẫu: {self._template_name}')
        return ''

    @Slot(str, result=str)
    def saveTemplateAs(self, name):
        if not (name or '').strip():
            return 'Hãy nhập tên mẫu.'
        try:
            saved = self.templates.save_as(name, self.cfg)
        except Exception as e:
            return str(e)
        self._template_name = saved
        self._dirty = False
        self.workspace.clear_working_copy()
        self.workspace.set('last_template', saved)
        self.templateChanged.emit()
        self.message.emit(f'Đã lưu vào thư viện: {saved}')
        return ''

    @Slot()
    def reloadSaved(self):
        if self._template_name:
            err = self.openTemplate(self._template_name)
            if err:
                self.message.emit(err)

    def restore_session(self, templates_available):
        """Open the last used template (recovering an unsaved layout from the previous session)."""
        name = self.workspace.get('last_template', '')
        if name not in templates_available:
            name = templates_available[0] if templates_available else ''
        if not name:
            return
        recovered = self.workspace.recover_working_copy(name)      # read before openTemplate() clears it
        if self.openTemplate(name):
            return
        if recovered:
            self.load_cfg(recovered, name, dirty=True)
            self._write_working_copy()                              # keep the recovered layout safe until saved
            self.message.emit('Đã khôi phục bố cục chưa lưu từ lần trước. Nhớ lưu mẫu khi xong.')
