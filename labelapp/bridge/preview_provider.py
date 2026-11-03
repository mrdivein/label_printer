"""image://preview/<name> — serves PIL images produced by the Python renderer to QML without touching disk."""
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


PREVIEW_MARGIN_RGB = (242, 242, 242)     # grey surround drawn by render_preview_with_guides()
PAPER_RGB = (255, 255, 255)
WORKSPACE_BORDER_RGB = (100, 100, 100)   # outline of the whole workspace page (not the nominal paper guide)
PREVIEW_TRANSPARENT = (PREVIEW_MARGIN_RGB, PAPER_RGB, WORKSPACE_BORDER_RGB)


def _alpha_lut(colors):
    """256-entry table over luminance: 0 (transparent) for the given grey colours, 255 otherwise.

    The preview is black ink + a few saturated guide colours on near-white greys, and none of the guide colours
    has the luminance of the greys we drop, so a luminance table is exact for what the renderer draws and much
    cheaper than three per-channel comparisons on a multi-megapixel image."""
    lut = [255] * 256
    for r, g, b in colors:
        lut[(r * 299 + g * 587 + b * 114) // 1000] = 0
    return lut


def pil_to_qimage(img, transparent=()):
    """PIL -> QImage. Pixels whose colour is one of the `transparent` greys become transparent, so the view's own
    themed canvas / paper shows through and only the black artwork and the coloured guides stay opaque."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    if transparent:
        rgb.putalpha(rgb.convert("L").point(_alpha_lut(transparent)))
        qi = QImage(rgb.tobytes("raw", "RGBA"), w, h, 4 * w, QImage.Format.Format_RGBA8888)
    else:
        qi = QImage(rgb.tobytes("raw", "RGB"), w, h, 3 * w, QImage.Format.Format_RGB888)
    return qi.copy()            # detach from the python bytes buffer


class PreviewProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._images = {}

    def set_image(self, name, pil_image, transparent=PREVIEW_TRANSPARENT):
        self._images[name] = pil_to_qimage(pil_image, transparent)

    def set_qimage(self, name, qimage):
        """Store an image already converted with pil_to_qimage() (e.g. in a worker thread)."""
        self._images[name] = qimage

    def drop(self, name):
        self._images.pop(name, None)

    def requestImage(self, image_id, size, requested_size):
        name = image_id.split("?", 1)[0]
        img = self._images.get(name)
        if img is None:
            img = QImage(1, 1, QImage.Format.Format_RGB888)
            img.fill(0xFFFFFF)
        return img
