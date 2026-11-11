"""Image elements stay visible on a 1-bit thermal label, and elements can be kept on the label but not printed."""
from PIL import Image, ImageDraw

from labelapp.core.binding import missing_fields
from labelapp.core.designer_geometry import render_workspace
from labelapp.core.editor import LabelEditor
from labelapp.core.label_engine import render_label
from labelapp.core.pdf_export import render_print_hq
from labelapp.core.preflight import preflight_checks
from labelapp.core.units import mm_to_px


def _page(elements, w=40, h=30, dpi=203):
    return {"width_mm": w, "height_mm": h, "dpi": dpi, "elements": elements,
            "virtual_print_area": {"show": False, "x": 0, "y": 0, "w": w, "h": h}}


def _dark(img, box_mm, dpi):
    x, y, w, h = (mm_to_px(v, dpi) for v in box_mm)
    reg = img.convert("L").crop((x, y, x + w, y + h))
    return sum(reg.histogram()[:128]) / max(1, reg.width * reg.height)


def _logo(tmp_path, colour, name):
    p = tmp_path / name
    im = Image.new("RGBA", (300, 150), (0, 0, 0, 0))     # transparent background, like most PNG logos
    ImageDraw.Draw(im).rectangle((20, 20, 280, 130), fill=colour)
    im.save(p)
    return str(p)


def test_light_coloured_logo_is_not_lost_by_the_threshold(tmp_path):
    # Light blue (luminance ~165) used to fall above the print threshold and vanish completely.
    path = _logo(tmp_path, (110, 180, 255, 255), "light.png")
    cfg = _page([{"type": "image", "path": path, "x": 5, "y": 5, "w": 30, "h": 15, "fit": "contain"}])
    share = _dark(render_label(cfg), (8, 8, 24, 9), 203)
    assert 0.15 < share < 0.85                     # dithered: visible, but not a solid black block


def test_dark_photo_is_not_a_black_block(tmp_path):
    path = _logo(tmp_path, (90, 90, 90, 255), "grey.png")
    cfg = _page([{"type": "image", "path": path, "x": 5, "y": 5, "w": 30, "h": 15}])
    assert _dark(render_label(cfg), (8, 8, 24, 9), 203) < 0.9


def test_dither_can_be_switched_off_for_pure_black_artwork(tmp_path):
    path = _logo(tmp_path, (110, 180, 255, 255), "light2.png")
    cfg = _page([{"type": "image", "path": path, "x": 5, "y": 5, "w": 30, "h": 15, "dither": False}])
    assert _dark(render_label(cfg), (8, 8, 24, 9), 203) == 0       # the old hard threshold, on request


def test_unprinted_element_is_not_printed_but_stays_in_the_designer():
    box = {"type": "fill_box", "x": 5, "y": 5, "w": 10, "h": 10}
    on = _page([dict(box)])
    off = _page([dict(box, print=False)])
    assert _dark(render_label(on), (6, 6, 8, 8), 203) > 0.99
    assert _dark(render_label(off), (6, 6, 8, 8), 203) == 0
    assert render_print_hq(off).convert("L").getextrema() == (255, 255)    # PDF / driver path too
    img, m = render_workspace(off, off, scale=1)                           # designer still draws it
    assert img.convert("L").getextrema()[0] == 0
    assert off["elements"][0]["print"] is False                            # template keeps the element


def test_unprinted_elements_need_no_data_and_raise_no_preflight_errors():
    cfg = _page([{"type": "text", "text": "{{Price}}", "x": 1, "y": 1, "w": 10, "h": 4, "print": False},
                 {"type": "barcode", "value": "", "x": 1, "y": 8, "w": 20, "h": 8, "print": False}])
    assert missing_fields(cfg, {"Price": ""}) == []
    errors, _ = preflight_checks(cfg)
    assert errors == []


def test_editor_print_switch_undo_and_locked_elements(templates):
    ed = LabelEditor(templates["Hang_Tag_50x68.json"])
    ed.elements[1]["locked"] = True
    assert ed.toggle_print(1) == "Print off"
    assert ed.elements[1]["print"] is False
    assert [e for e in ed.overlay()["elements"] if e["index"] == 1][0]["printed"] is False
    ed.selected = {1}
    field = [f for f in ed.inspector_fields() if f["key"] == "print"][0]
    assert field["value"] is False
    assert ed.set_prop("print", True) == "Print on" and "print" not in ed.elements[1]
    ed.undo()
    assert ed.elements[1]["print"] is False
