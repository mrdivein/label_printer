"""image://preview/<name> — serves PIL images produced by the Python renderer to QML without touching disk."""
from PIL import Image, ImageChops
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


PREVIEW_MARGIN_RGB = (242, 242, 242)     # grey surround drawn by render_preview_with_guides()
PAPER_RGB = (255, 255, 255)
WORKSPACE_BORDER_RGB = (100, 100, 100)   # outline of the whole workspace page (not the nominal paper guide)


def pil_to_qimage(img, transparent=()):
    """PIL -> QImage. Pixels exactly equal to one of the `transparent` colours become transparent, so the view's own
    themed canvas / paper shows through and only the black artwork and the coloured guides stay opaque.
    (The render is strictly 1-bit black on white, so this is lossless.)"""
    rgb = img.convert("RGB")
    w, h = rgb.size
    if transparent:
        keep = None
        for col in transparent:
            diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, col)).convert("L").point(lambda p: 255 if p else 0)
            keep = diff if keep is None else ImageChops.multiply(keep, diff)
        rgba = rgb.copy()
        rgba.putalpha(keep)
        qi = QImage(rgba.tobytes("raw", "RGBA"), w, h, 4 * w, QImage.Format.Format_RGBA8888)
    else:
        qi = QImage(rgb.tobytes("raw", "RGB"), w, h, 3 * w, QImage.Format.Format_RGB888)
    return qi.copy()            # detach from the python bytes buffer


class PreviewProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._images = {}

    def set_image(self, name, pil_image, transparent=(PREVIEW_MARGIN_RGB, PAPER_RGB, WORKSPACE_BORDER_RGB)):
        self._images[name] = pil_to_qimage(pil_image, transparent)

    def drop(self, name):
        self._images.pop(name, None)

    def requestImage(self, image_id, size, requested_size):
        name = image_id.split("?", 1)[0]
        img = self._images.get(name)
        if img is None:
            img = QImage(1, 1, QImage.Format.Format_RGB888)
            img.fill(0xFFFFFF)
        return img
