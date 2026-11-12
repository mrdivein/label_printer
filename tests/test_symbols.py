"""Bundled symbols (fragile, seal...): palette keys, files, rendering and portable paths."""
import os
import re

from labelapp.core.editor import LabelEditor
from labelapp.core.label_engine import render_label
from labelapp.paths import qml_dir, symbol_png, symbols_dir
from labelapp.services.image_service import load_element_image


def palette_keys():
    qml = open(os.path.join(qml_dir(), "panels", "LeftPanel.qml"), encoding="utf-8").read()
    return re.findall(r'\{ k: "([a-z_]+)"', qml)


def test_every_palette_symbol_has_svg_and_png():
    keys = palette_keys()
    assert "fragile" in keys and "seal" in keys and len(keys) == len(set(keys))
    for k in keys:
        assert os.path.isfile(os.path.join(symbols_dir(), k + ".svg")), k
        assert load_element_image("symbol:" + k) is not None, k


def test_symbol_path_is_resolved_not_treated_as_file():
    assert symbol_png("symbol:fragile").endswith(os.path.join("symbols", "fragile.png"))
    assert symbol_png("C:/logo.png") is None
    assert load_element_image("symbol:does_not_exist") is None


def test_added_symbol_prints_black_square_without_dither():
    ed = LabelEditor({"width_mm": 30, "height_mm": 30, "dpi": 300, "elements": []})
    ed.add_symbol("tick", size_mm=12)
    e = ed.cfg["elements"][-1]
    assert e["path"] == "symbol:tick" and e["w"] == e["h"] == 12 and e["dither"] is False
    img = render_label(ed.cfg)
    assert img.getextrema()[0] == 0          # black ink reached the label
