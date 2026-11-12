"""AppBridge: composition root and application-level state (status bar, theme, window state).

Builds the services and controllers, wires them together and exposes them to QML as
App (this object), Doc, Lib, Data and Printing. It contains no label or printing logic itself.
"""
import os
import subprocess
import sys

from PySide6.QtCore import Property, QObject, QThreadPool, QUrl, Signal, Slot

from ..i18n import I18nBridge, tr
from ..paths import to_local_path
from ..paths import app_root
from ..services.print_service import PrintService
from ..services.template_service import TemplateService
from ..services.workspace_service import Workspace
from .data_controller import DataController
from .document_controller import DocumentController
from .gallery_controller import GalleryController
from .library_controller import LibraryController
from .preview_provider import PreviewProvider
from .print_controller import PrintController
from .profile_controller import ProfileController
from .scan_controller import ScanController
from ..services.profile_service import ProfileService
from ..version import __version__
from .update_controller import UpdateController

APP_NAME = "Temly"
APP_VERSION = __version__


class AppBridge(QObject):
    statusChanged = Signal()
    themeChanged = Signal()
    errorRaised = Signal(str, str)      # title, text -> QML message dialog

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workspace = Workspace()
        self.provider = PreviewProvider()
        self.templates = TemplateService()
        self.data = DataController(self.workspace, self)
        self.document = DocumentController(self.templates, self.workspace, self.provider, self)
        self.document.row_provider = self.data.current_row_dict
        self.library = LibraryController(self.templates, self.document, self.data, self.provider, self)
        self.print_service = PrintService(history_enabled=bool(self.workspace.get('save_history', True)))
        self.printing = PrintController(self.workspace, self.document, self.data, self.print_service, self)
        self.scan = ScanController(self.workspace, self.data, self.printing, self)
        self.profiles = ProfileController(ProfileService(), self.document, self.printing, self)
        self.updates = UpdateController(self)
        self.i18n = I18nBridge(self.workspace, self)
        self.gallery = GalleryController(self.templates, self.library, self.provider, self)
        self.i18n.languageChanged.connect(self._retranslate)
        self._status = 'Sẵn sàng'
        self._dark = bool(self.workspace.get('qt_dark', False))

        for src in (self.document, self.library, self.data, self.printing, self.profiles, self.scan, self.gallery):
            src.message.connect(self.setStatus)
        for src in (self.data, self.printing, self.scan):
            src.error.connect(self.errorRaised)
        self.data.rowChanged.connect(self.document._schedule_render)
        self.data.rowChanged.connect(self.document._refresh_overlay)

    # ------------------------------------------------------------------ properties
    def _get_status(self):
        return tr(self._status)

    status = Property(str, _get_status, notify=statusChanged)

    def _get_dark(self):
        return self._dark

    def _set_dark(self, v):
        if bool(v) != self._dark:
            self._dark = bool(v)
            self.workspace.set('qt_dark', self._dark)
            self.themeChanged.emit()

    darkMode = Property(bool, _get_dark, _set_dark, notify=themeChanged)

    def _get_title(self):
        return APP_NAME

    appName = Property(str, _get_title, constant=True)

    def _get_version(self):
        return APP_VERSION

    appVersion = Property(str, _get_version, constant=True)

    def _get_is_windows(self):
        return sys.platform.startswith('win')

    isWindows = Property(bool, _get_is_windows, constant=True)

    def _get_window(self):
        return self.workspace.get('qt_window', {}) or {}

    windowState = Property('QVariant', _get_window, constant=True)

    def _retranslate(self):
        """After a language switch: Python-made texts (status, element list, inspector rows) re-describe themselves."""
        self.statusChanged.emit()
        self.document.retranslate()
        if self.library._preview_name:
            self.library.showPreview(self.library._preview_name)
        if self.library._share['cfg'] is not None:
            self.library._render_share()

    # ------------------------------------------------------------------ slots
    @Slot(str)
    def setStatus(self, text):
        self._status = text
        self.statusChanged.emit()

    @Slot('QVariant', result=str)
    def toLocalPath(self, url):
        """QML file dialogs return file:// URLs; Python code wants a native path."""
        return to_local_path(url)

    @Slot(int, int, int, int, bool)
    def saveWindow(self, x, y, w, h, maximized):
        self.workspace.set('qt_window', {'x': x, 'y': y, 'w': w, 'h': h, 'maximized': maximized})

    def start(self):
        """After the window exists: restore the previous session and discover printers (off the UI thread)."""
        self.library.refresh()
        self.document.restore_session(self.library.names)
        self.data.restore_last()
        self.printing.refreshPrinters()
        self.updates.start()

    def _get_legacy(self):
        return os.path.exists(os.path.join(app_root(), 'app.py')) and not getattr(sys, 'frozen', False)

    legacyAvailable = Property(bool, _get_legacy, constant=True)

    @Slot()
    def launchLegacy(self):
        """Open the original Tkinter app (print history, guide editor... not yet in the Qt UI)."""
        try:
            subprocess.Popen([sys.executable, os.path.join(app_root(), 'app.py')], cwd=app_root())
        except Exception as e:
            self.errorRaised.emit('Ứng dụng cũ', str(e))

    @Slot()
    def shutdown(self):
        QThreadPool.globalInstance().waitForDone(3000)     # let a running preview render / file load finish
        self.document.flush()
        self.workspace.save()
        self.updates.install_on_quit()
