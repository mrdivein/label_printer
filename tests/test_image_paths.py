"""File-dialog URLs become real paths, and templates that saved a QUrl's text instead of a path still show their image."""
from PIL import Image, ImageDraw
from PySide6.QtCore import QUrl

from labelapp.core.editor import LabelEditor
from labelapp.core.label_engine import render_label
from labelapp.core.units import mm_to_px
from labelapp.paths import to_local_path


def test_to_local_path_accepts_every_form_qml_hands_out(tmp_path):
    p = (tmp_path / "Logo INSIZE.jpg").as_posix()
    assert to_local_path(QUrl.fromLocalFile(p)) == p                       # QUrl object (FileDialog.selectedFile)
    assert to_local_path(QUrl.fromLocalFile(p).toString()) == p            # file:/// string
    assert to_local_path(str(QUrl.fromLocalFile(p))) == p                  # "PySide6.QtCore.QUrl('file:///...')"
    assert to_local_path("PySide6.QtCore.QUrl('file:///C:/Users/x/Logo%20INSIZE.jpg')") == "C:/Users/x/Logo INSIZE.jpg"
    assert to_local_path(r"C:\a\b.png") == r"C:\a\b.png"                   # plain paths untouched
    assert to_local_path("{{Logo}}") == "{{Logo}}"
    assert to_local_path(None) == ""


def test_bridge_to_local_path_with_a_qurl_object(qapp, tmp_path):
    from labelapp.bridge.app_bridge import AppBridge
    p = (tmp_path / "logo.png").as_posix()
    assert AppBridge().toLocalPath(QUrl.fromLocalFile(p)) == p


def _jpg_logo(tmp_path):
    p = tmp_path / "Logo INSIZE.jpg"
    im = Image.new("RGB", (200, 40), (255, 255, 255))
    ImageDraw.Draw(im).rectangle((5, 5, 195, 35), fill=(40, 60, 50))    # dark green on white, like a JPG logo
    im.save(p, quality=90)
    return p.as_posix()


def test_image_added_from_a_file_dialog_url_is_drawn(tmp_path):
    path = _jpg_logo(tmp_path)
    ed = LabelEditor({"width_mm": 40, "height_mm": 30, "dpi": 203, "elements": []})
    ed.add_special("image", QUrl.fromLocalFile(path))
    e = ed.elements[-1]
    assert e["path"] == path
    e.update(x=2, y=2, w=30, h=8)
    img = render_label(ed.cfg).convert("L")
    box = img.crop((mm_to_px(4, 203), mm_to_px(3, 203), mm_to_px(28, 203), mm_to_px(9, 203)))
    assert sum(box.histogram()[:128]) > 0.5 * box.width * box.height


def test_template_with_saved_qurl_text_is_repaired_on_load(tmp_path):
    path = _jpg_logo(tmp_path)
    broken = str(QUrl.fromLocalFile(path))
    cfg = {"width_mm": 40, "height_mm": 30, "dpi": 203,
           "elements": [{"type": "image", "path": broken, "x": 2, "y": 2, "w": 30, "h": 8}]}
    assert render_label(cfg).convert("L").getextrema()[0] == 0              # renderer copes with the old text
    ed = LabelEditor(cfg)
    assert ed.elements[0]["path"] == path                                  # and the editor fixes it for the next save
