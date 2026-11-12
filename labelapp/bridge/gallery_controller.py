"""GalleryController: the ready-made template gallery (QML ``Gallery``).

Thumbnails are rendered off the UI thread into the preview image provider as ``g_<id>``; ``thumbs`` maps a
template id to a version number once its picture is ready, so QML only loads images that exist.
"""
from PySide6.QtCore import Property, QObject, Signal, Slot

from ..i18n import language, trf
from ..services.gallery_service import GalleryService
from .preview_provider import pil_to_qimage
from .tasks import run_async


class GalleryController(QObject):
    thumbsChanged = Signal()
    previewChanged = Signal()
    message = Signal(str)

    def __init__(self, templates, library, provider, parent=None, service=None):
        super().__init__(parent)
        self.templates = templates
        self.library = library
        self.provider = provider
        self.service = service or GalleryService()
        self._thumbs = {}
        self._loading = False
        self._preview_version = 0
        self._preview_id = ""

    # ------------------------------------------------------------------ catalogue
    def _get_categories(self):
        return self.service.categories()

    categories = Property('QVariantList', _get_categories, constant=True)

    def _get_items(self):
        return self.service.items()

    items = Property('QVariantList', _get_items, constant=True)

    def _get_total(self):
        return len(self.service.items())

    total = Property(int, _get_total, constant=True)

    @Slot(str, result='QStringList')
    def search(self, query):
        return self.service.search(query)

    # ------------------------------------------------------------------ thumbnails
    def _get_thumbs(self):
        return dict(self._thumbs)

    thumbs = Property('QVariantMap', _get_thumbs, notify=thumbsChanged)

    @Slot()
    def loadThumbs(self):
        """Render every missing thumbnail in the background (once per session)."""
        if self._loading:
            return
        todo = [it["id"] for it in self.service.items() if it["id"] not in self._thumbs]
        if not todo:
            return
        self._loading = True
        chunk = 6
        pending = {"n": 0}

        def job_for(ids):
            def job():
                return [(tid, pil_to_qimage(self.service.render(tid, True, 360))) for tid in ids]
            return job

        def done(results):
            for tid, qimg in results:
                self.provider.set_qimage("g_" + tid, qimg)
                self._thumbs[tid] = self._thumbs.get(tid, 0) + 1
            self.thumbsChanged.emit()
            finish()

        def finish(_err=None):
            pending["n"] -= 1
            if pending["n"] <= 0:
                self._loading = False

        for i in range(0, len(todo), chunk):
            pending["n"] += 1
            run_async(job_for(todo[i:i + chunk]), done, finish)

    # ------------------------------------------------------------------ large preview (sample data / original)
    def _get_preview_source(self):
        return f"image://preview/gallery_big?v={self._preview_version}"

    previewSource = Property(str, _get_preview_source, notify=previewChanged)

    @Slot(str, bool)
    def showPreview(self, tid, with_sample):
        """Render the selected template large, filled with its sample data or as the original ({{fields}} visible)."""
        if not tid:
            return
        self._preview_id = tid
        stamp = self._preview_version + 1
        self._preview_version = stamp

        def job():
            return pil_to_qimage(self.service.render(tid, with_sample, 900))

        def ok(qimg):
            if stamp == self._preview_version:
                self.provider.set_qimage("gallery_big", qimg)
                self._preview_version += 1
                self.previewChanged.emit()

        run_async(job, ok, lambda e: self.message.emit(str(e)))

    # ------------------------------------------------------------------ use
    @Slot(str, result=str)
    def useTemplate(self, tid):
        """Copy the template into the library and open it. Returns '' or an error message."""
        try:
            name = self.service.install(tid, self.templates, language())
        except Exception as e:                       # OSError, missing id
            return str(e)
        self.library.refresh()
        err = self.library.document.openTemplate(name)
        if not err:
            self.message.emit(trf("Đã thêm mẫu vào thư viện: {}", name[:-5]))
        return err
