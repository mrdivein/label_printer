"""DocumentController: the label being designed.

Owns a LabelEditor (all editing rules live in labelapp.core.editor) and exposes its state to QML:
paper settings, element list, selection, inspector schema/values, canvas overlay geometry and the rendered
workspace image. QML only forwards user intent (pointer positions in millimetres, property edits, commands).
"""
import copy

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ..core.binding import bind_row_to_template
from ..core.designer_geometry import render_workspace
from ..core.editor import DOC_CHOICE_KEYS, DOC_NUMBER_KEYS, LabelEditor
from ..core.designer_geometry import virtual_area
from ..core.models import normalize_cfg
from ..services.template_service import TemplateService
from ..services.workspace_service import Workspace
from .models import ElementListModel, InspectorModel

RENDER_SCALE = 2                # preview supersampling relative to printer DPI (same as the Tk designer)
DOC_KEYS = DOC_NUMBER_KEYS + tuple(DOC_CHOICE_KEYS)


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
            return f'{n} elements'
        e = self.cfg['elements'][next(iter(self.editor.selected))]
        return str(e.get('type', '')).replace('_', ' ').capitalize() + (' — locked' if e.get('locked') else '')

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
        try:
            img, m = render_workspace(self.cfg, self.bound_cfg(), scale=RENDER_SCALE,
                                      show_guides=self._show_guides, show_fold=self._show_fold)
            self.provider.set_image('workspace', img)
            self._workspace_rect = {'x': m['x'], 'y': m['y'], 'w': m['w'], 'h': m['h']}
            self._preview_version += 1
            self._preview_error = ''
        except Exception as e:
            self._preview_error = f'Preview error: {e}'
        self.previewChanged.emit()

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
        self.message.emit(f"{note} — live for printing, not saved to the template yet.")
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
        self._commit(self.editor.add_text(text or 'New text'))

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
    def addShape(self, kind):
        self._commit(self.editor.add_shape(kind))

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
            self.message.emit(n + ' — Ctrl+V to paste')

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
            self.message.emit('Drag the orange fold line vertically. Back-face elements stay visually fixed.')

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
        self.message.emit(f'Template loaded: {name}')
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
        self.message.emit(f'Template saved: {self._template_name}')
        return ''

    @Slot(str, result=str)
    def saveTemplateAs(self, name):
        if not (name or '').strip():
            return 'Enter a template name.'
        try:
            saved = self.templates.save_as(name, self.cfg)
        except Exception as e:
            return str(e)
        self._template_name = saved
        self._dirty = False
        self.workspace.clear_working_copy()
        self.workspace.set('last_template', saved)
        self.templateChanged.emit()
        self.message.emit(f'Template saved to library: {saved}')
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
            self.message.emit('Recovered unsaved layout from the previous session. Save the template when ready.')
