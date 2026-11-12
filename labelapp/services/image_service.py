"""Image loading for Image elements (cached, flattened to greyscale on white)."""
import functools
import os

from PIL import Image

from ..paths import symbol_png, to_local_path

@functools.lru_cache(maxsize=32)
def _load_image_file(path, mtime):
    im = Image.open(path)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im.convert("RGBA"))
        im = bg
    return im.convert("L")

def load_element_image(path):
    path = symbol_png(path) or os.path.expanduser(to_local_path(path or ""))
    if not path or not os.path.isfile(path):
        return None
    try:
        return _load_image_file(path, os.path.getmtime(path))
    except Exception:
        return None
