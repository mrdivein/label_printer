"""Rendering / print geometry invariants of the shared core (what the printed label looks like and how big it is)."""
import copy

import pytest

from labelapp.core.binding import bind_row_to_template
from labelapp.core.label_engine import render_label, render_preview_with_guides
from labelapp.core.models import normalize_cfg
from labelapp.core.pdf_export import render_print_hq, save_exact_print_pdf, rasterize_exact_print_pdf
from labelapp.core.preflight import preflight_checks
from labelapp.core.units import mm_to_px
from labelapp.services.printer_service import build_raw_gzpl


def test_mm_to_px_matches_dpi():
    assert mm_to_px(25.4, 300) == 300
    assert mm_to_px(50, 203) == round(50 * 203 / 25.4)


def test_label_dimensions_follow_paper_size_and_dpi(templates):
    for name, cfg in templates.items():
        c = normalize_cfg(cfg)
        img = render_label(c)
        assert img.size == (mm_to_px(c["width_mm"], c["dpi"]), mm_to_px(c["height_mm"], c["dpi"])), name


def test_landscape_swaps_axes(templates):
    c = normalize_cfg(templates["ECG_H_TAG_50x68.json"])
    c["orientation"] = "landscape"
    w, h = render_label(c).size
    assert (w, h) == (mm_to_px(68, 300), mm_to_px(50, 300))


def test_hq_raster_has_exact_printer_dot_dimensions(templates):
    c = normalize_cfg(templates["ECG_H_TAG_56x83_Thermal.json"])
    img = render_print_hq(c)
    assert img.size == (mm_to_px(56, 300), mm_to_px(83, 300))


def test_zpl_header_matches_raster_and_copies(templates, sample_row):
    c = bind_row_to_template(normalize_cfg(templates["ECG_H_TAG_50x68.json"]), sample_row)
    assert c["copies"] == 2                               # row "Copies" column wins
    img = render_label(c)
    raw = build_raw_gzpl(c, img).decode("ascii")
    assert f"^PW{img.width}" in raw and f"^LL{img.height}" in raw and "^PQ2,0,1,N" in raw


def test_pdf_page_is_physical_size(templates, tmp_path):
    c = normalize_cfg(templates["ECG_H_TAG_50x68.json"])
    p = str(tmp_path / "x.pdf")
    save_exact_print_pdf(c, p)
    import fitz
    with fitz.open(p) as d:
        assert len(d) == 1
        r = d[0].rect
        assert abs(r.width - 50 / 25.4 * 72) < 0.1 and abs(r.height - 68 / 25.4 * 72) < 0.1
    # Legacy "print via PDF" route: PyMuPDF rounds the pixmap up, so it can be 1 dot larger than the exact size
    # (the original app detects and refuses that case). The main HQ route resizes to the exact size (tested above).
    w, h = rasterize_exact_print_pdf(p, 300).size
    assert abs(w - mm_to_px(50, 300)) <= 1 and abs(h - mm_to_px(68, 300)) <= 1


def test_render_is_deterministic(templates, sample_row):
    c = bind_row_to_template(normalize_cfg(templates["ECG_H_TAG_56x83_Thermal.json"]), sample_row)
    assert render_label(c).tobytes() == render_label(copy.deepcopy(c)).tobytes()


def test_preflight_flags_blank_barcode_and_bad_paper(templates):
    c = normalize_cfg(templates["ECG_H_TAG_50x68.json"])
    c["elements"].append({"type": "barcode", "value": "", "x": 1, "y": 1, "w": 10, "h": 5})
    errors, _ = preflight_checks(c)
    assert any("barcode is blank" in e for e in errors)
    c["width_mm"] = 0
    assert any("Paper width" in e for e in preflight_checks(c)[0])


def test_preview_with_guides_is_larger_than_label(templates):
    c = normalize_cfg(templates["ECG_H_TAG_50x68.json"])
    assert render_preview_with_guides(c, scale=2).width > render_label(c).width


def test_all_element_types_render(sample_row):
    c = normalize_cfg({"width_mm": 50, "height_mm": 40, "elements": [
        {"type": "qr", "value": "x", "x": 1, "y": 1, "w": 12, "h": 12},
        {"type": "barcode", "value": "5901234123457", "x": 14, "y": 1, "w": 30, "h": 10, "symbology": "ean13", "show_text": True},
        {"type": "ellipse", "x": 1, "y": 15, "w": 10, "h": 6}, {"type": "fill_box", "x": 13, "y": 15, "w": 5, "h": 5},
        {"type": "text", "text": "hi", "x": 20, "y": 15, "w": 20, "h": 5, "angle": 30}, {"type": "line", "x": 1, "y": 30, "x2": 40, "y2": 35}]})
    img = render_label(c)
    assert img.convert('L').getextrema() == (0, 255)
