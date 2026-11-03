"""UpdateController (QML: ``Updates``): checks for a new version at start and every 4 hours,
downloads it in the background and offers "Restart to update". A downloaded update is also
installed when the app is closed normally, without restarting it.
"""
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ..services import update_service as us
from ..version import __version__
from .tasks import run_async

CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000


class UpdateController(QObject):
    changed = Signal()
    quitRequested = Signal()
    _progress = Signal(float)                   # emitted from the download thread, delivered on the UI thread

    def __init__(self, parent=None, supported=None):
        super().__init__(parent)
        self._supported = us.updates_supported() if supported is None else bool(supported)
        self._state = "idle" if self._supported else "dev"   # idle|checking|downloading|ready|current|error|dev
        self._text = "" if self._supported else "Updates work in the installed app only"
        self._percent = 0.0
        self._version = ""
        self._installer = None
        self._busy = False
        self._progress.connect(self._on_progress)
        self._timer = QTimer(self)
        self._timer.setInterval(CHECK_INTERVAL_MS)
        self._timer.timeout.connect(self.check)

    def start(self):
        if self._supported:
            QTimer.singleShot(3000, self.check)
            self._timer.start()

    # ------------------------------------------------------------------ properties
    def _set(self, state, text, percent=None):
        self._state, self._text = state, text
        if percent is not None:
            self._percent = percent
        self.changed.emit()

    state = Property(str, lambda s: s._state, notify=changed)
    text = Property(str, lambda s: s._text, notify=changed)
    percent = Property(float, lambda s: s._percent, notify=changed)
    newVersion = Property(str, lambda s: s._version, notify=changed)
    currentVersion = Property(str, lambda s: __version__, constant=True)
    supported = Property(bool, lambda s: s._supported, constant=True)

    # ------------------------------------------------------------------ slots
    @Slot()
    def check(self):
        if not self._supported or self._busy or self._state == "ready":
            return
        self._busy = True
        self._set("checking", "Checking for updates")
        run_async(us.fetch_manifest, self._on_manifest, self._on_error)

    def _on_manifest(self, m):
        if not us.is_newer(m["version"]):
            self._busy = False
            self._set("current", "Up to date (%s)" % __version__)
            return
        self._version = m["version"]
        self._set("downloading", "Downloading %s" % m["version"], 0.0)
        run_async(lambda: us.download(m, progress=self._progress.emit), self._on_downloaded, self._on_error)

    def _on_progress(self, p):
        if self._state == "downloading":
            self._set("downloading", "Downloading %s  %d%%" % (self._version, int(p)), p)

    def _on_downloaded(self, path):
        self._busy = False
        self._installer = path
        self._set("ready", "Version %s ready" % self._version, 100.0)

    def _on_error(self, msg):
        self._busy = False
        self._set("error", str(msg))

    @Slot()
    def installNow(self):
        """Start the silent installer (it restarts the app) and quit."""
        if not self._installer:
            return
        try:
            us.launch_installer(self._installer, relaunch=True)
        except Exception as e:
            self._set("error", "Could not start the installer: %s" % e)
            return
        self._installer = None
        self.quitRequested.emit()

    def install_on_quit(self):
        """Called while the app shuts down: install a downloaded update without restarting the app."""
        if self._installer:
            try:
                us.launch_installer(self._installer, relaunch=False)
            except Exception:
                pass
            self._installer = None
