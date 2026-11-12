"""LibraryController: template library management (list / preview / new / duplicate / rename / delete / import / export)."""
import os

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from ..core.share_check import ACTION_LABELS, sanitize, scan
from ..i18n import tr, trf
from ..paths import to_local_path
from ..services.gallery_service import render_card
from ..services.template_service import LABEL_PRESETS, TemplateError, TemplateService, write_template
from .preview_provider import pil_to_qimage


def _local(path_or_url):
    """QML file dialogs hand out file:// URLs (as QUrl objects)."""
    return to_local_path(path_or_url)


class LibraryController(QObject):
    namesChanged = Signal()
    previewChanged = Signal()
    rawPreviewChanged = Signal()
    shareChanged = Signal()
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
        self._raw = True
        self._preview_name = ''
        self._share = {'name': '', 'cfg': None, 'findings': [], 'actions': {}, 'version': 0, 'cleaned': True}
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
        return tr(self._info)

    previewInfo = Property(str, _get_info, notify=previewChanged)

    def _get_dir(self):
        return self.templates.library_dir

    libraryDir = Property(str, _get_dir, constant=True)

    # ------------------------------------------------------------------ slots
    @Slot()
    def refresh(self):
        self._names = self.templates.list_templates()
        self.namesChanged.emit()

    def _get_raw(self):
        return self._raw

    def _set_raw(self, v):
        if bool(v) != self._raw:
            self._raw = bool(v)
            self.rawPreviewChanged.emit()
            if self._preview_name:
                self.showPreview(self._preview_name)

    # True: the library preview shows the original template ({{fields}} visible), not the current data row.
    rawPreview = Property(bool, _get_raw, _set_raw, notify=rawPreviewChanged)

    @Slot(str)
    def showPreview(self, name):
        self._preview_name = name
        try:
            row = None if self._raw else self.data.current_row_dict()
            cfg, img = self.templates.preview_image(name, row)
            self.provider.set_image('thumb', img, transparent=((242, 242, 242),))
            self._preview_version += 1
            self._info = (f"{name}   ·   {cfg['width_mm']:g} × {cfg['height_mm']:g} mm   ·   " + trf('{} phần tử', len(cfg['elements']))
                          + ('   ·   ' + tr('Mẫu gốc: các ô {{…}} được thay bằng dữ liệu của bạn khi in.') if self._raw else
                             ('   ·   ' + tr('xem trước theo dòng dữ liệu đang chọn') if row else '')))
        except Exception as e:
            self.provider.drop('thumb')
            self._preview_version += 1
            self._info = trf('Không xem trước được: {}', e)
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

    # ------------------------------------------------------------------ share check (original template, cleaned copy)
    def _get_findings(self):
        out = []
        for f in self._share['findings']:
            act = self._share['actions'].get(f['id'], f['action'])
            out.append(dict(f, title=' · '.join(tr(x) for x in f['title'].split(' · ')), reason=tr(f['reason']),
                            action=act, actionLabels=[tr(ACTION_LABELS[a]) for a in f['actions']]))
        return out

    shareFindings = Property('QVariantList', _get_findings, notify=shareChanged)

    def _get_share_source(self):
        return f"image://preview/share?v={self._share['version']}"

    sharePreviewSource = Property(str, _get_share_source, notify=shareChanged)

    def _get_share_cleaned(self):
        return self._share['cleaned']

    shareShowsCleaned = Property(bool, _get_share_cleaned, notify=shareChanged)

    def _get_share_summary(self):
        n = sum(1 for f in self._share['findings'] if f['severity'] > 0)
        return trf('Tìm thấy {} mục cần xem lại', n) if n else tr(
            'Không thấy thông tin nhạy cảm. Vẫn nên xem lại các chữ cố định bên dưới.')

    shareSummary = Property(str, _get_share_summary, notify=shareChanged)

    def _render_share(self):
        sh = self._share
        cfg = self._cleaned() if sh['cleaned'] else sh['cfg']
        try:
            self.provider.set_qimage('share', pil_to_qimage(render_card(cfg, 900)))
        except Exception as e:
            self.message.emit(trf('Không xem trước được: {}', e))
        sh['version'] += 1
        self.shareChanged.emit()

    def _cleaned(self):
        sh = self._share
        return sanitize(sh['cfg'], sh['findings'], sh['actions'])

    @Slot(str, result=str)
    def shareCheck(self, name):
        """Scan a library template for company / personal details. Returns '' or an error message."""
        try:
            cfg = self.templates.load(name)
        except Exception as e:
            return str(e)
        self._share = {'name': name, 'cfg': cfg, 'findings': scan(cfg), 'actions': {}, 'version':
                       self._share['version'], 'cleaned': True}
        self._render_share()
        return ''

    @Slot(str, str)
    def setShareAction(self, finding_id, action):
        self._share['actions'][finding_id] = action
        self._render_share()

    @Slot(bool)
    def showShareCleaned(self, cleaned):
        self._share['cleaned'] = bool(cleaned)
        self._render_share()

    @Slot(str, result=str)
    def exportShared(self, dest):
        """Write the cleaned copy to `dest`. Returns '' or an error message."""
        if self._share['cfg'] is None:
            return ''
        path = _local(dest)
        try:
            write_template(path, self._cleaned())
        except OSError as e:
            return str(e)
        self.message.emit(trf('Đã xuất bản chia sẻ: {}', os.path.basename(path)))
        return ''

    def _get_share_name(self):
        return self._share['name']

    shareName = Property(str, _get_share_name, notify=shareChanged)
