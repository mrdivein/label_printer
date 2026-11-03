"""LibraryController: template library management (list / preview / new / duplicate / rename / delete / import / export)."""
import os

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from ..services.template_service import LABEL_PRESETS, TemplateError, TemplateService


def _local(path_or_url):
    """QML file dialogs hand out file:// URLs."""
    s = str(path_or_url)
    if s.startswith('file:'):
        return QUrl(s).toLocalFile()
    return s


class LibraryController(QObject):
    namesChanged = Signal()
    previewChanged = Signal()
    message = Signal(str)

    def __init__(self, templates: TemplateService, document, data, provider, parent=None):
        super().__init__(parent)
        self.templates = templates
        self.document = document
        self.data = data
        self.provider = provider
        self._names = []
        self._preview_version = 0
        self._info = ''
        self.refresh()

    # ------------------------------------------------------------------ properties
    def _get_names(self):
        return self._names

    names = Property('QStringList', _get_names, notify=namesChanged)

    def _get_presets(self):
        return [{'name': k, 'w': v[0], 'h': v[1]} for k, v in LABEL_PRESETS.items()]

    presets = Property('QVariantList', _get_presets, constant=True)

    def _get_preview_source(self):
        return f"image://preview/thumb?v={self._preview_version}"

    previewSource = Property(str, _get_preview_source, notify=previewChanged)

    def _get_info(self):
        return self._info

    previewInfo = Property(str, _get_info, notify=previewChanged)

    def _get_dir(self):
        return self.templates.library_dir

    libraryDir = Property(str, _get_dir, constant=True)

    # ------------------------------------------------------------------ slots
    @Slot()
    def refresh(self):
        self._names = self.templates.list_templates()
        self.namesChanged.emit()

    @Slot(str)
    def showPreview(self, name):
        try:
            cfg, img = self.templates.preview_image(name, self.data.current_row_dict())
            self.provider.set_image('thumb', img, transparent=((242, 242, 242),))
            self._preview_version += 1
            self._info = (f"{name}   ·   {cfg['width_mm']:g} × {cfg['height_mm']:g} mm   ·   {len(cfg['elements'])} elements"
                          + ("   ·   preview uses the selected data row" if self.data.current_row_dict() else ""))
        except Exception as e:
            self.provider.drop('thumb')
            self._preview_version += 1
            self._info = f'Cannot preview: {e}'
        self.previewChanged.emit()

    @Slot(str, float, float, int, result=str)
    def createTemplate(self, name, w, h, dpi):
        """Returns '' (and opens the new template) or an error message."""
        try:
            new = self.templates.create(name, w, h, dpi)
        except (TemplateError, ValueError, OSError) as e:
            return str(e)
        self.refresh()
        return self.document.openTemplate(new)

    @Slot(str, str, result=str)
    def duplicate(self, name, new_name):
        try:
            self.templates.duplicate(name, new_name)
        except (TemplateError, OSError) as e:
            return str(e)
        self.refresh()
        return ''

    @Slot(str, str, result=str)
    def rename(self, name, new_name):
        try:
            nn = self.templates.rename(name, new_name)
        except (TemplateError, OSError) as e:
            return str(e)
        if self.document.templateName == name:
            self.document._template_name = nn
            self.document.workspace.set('last_template', nn)
            self.document.templateChanged.emit()
        self.refresh()
        return ''

    @Slot(str, result=str)
    def delete(self, name):
        try:
            self.templates.delete(name)
        except OSError as e:
            return str(e)
        self.refresh()
        return ''

    @Slot(str, str, result=str)
    def exportTemplate(self, name, dest):
        try:
            self.templates.export(name, _local(dest))
        except OSError as e:
            return str(e)
        return ''

    @Slot(str, str, bool, result=str)
    def importTemplate(self, src, name, overwrite):
        """Import a JSON template file. Returns '' | 'exists:<name>' | error message. Opens it on success."""
        src = _local(src)
        try:
            imported = self.templates.import_file(src, name or None, overwrite)
        except TemplateError as e:
            msg = str(e)
            if 'already exists' in msg:
                return 'exists:' + os.path.basename(src)
            return msg
        self.refresh()
        return self.document.openTemplate(imported)

    @Slot()
    def openFolder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.templates.library_dir))
