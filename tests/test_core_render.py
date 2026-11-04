"""Rendering / print geometry invariants of the shared core (what the printed label looks like and how big it is)."""
import copy

import pytest

from labelapp.core.binding import bind_row_to_template
from labelapp.core.label_engine import clean_text, find_font, render_label, render_preview_with_guides
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
    c = normalize_cfg(templates["Hang_Tag_50x68.json"])
    c["orientation"] = "landscape"
    w, h = render_label(c).size
    assert (w, h) == (mm_to_px(68, 300), mm_to_px(50, 300))


def test_hq_raster_has_exact_printer_dot_dimensions(templates):
    c = normalize_cfg(templates["Hang_Tag_56x83_Thermal.json"])
    img = render_print_hq(c)
    assert img.size == (mm_to_px(56, 300), mm_to_px(83, 300))


def test_zpl_header_matches_raster_and_copies(templates, sample_row):
    c = bind_row_to_template(normalize_cfg(templates["Hang_Tag_50x68.json"]), sample_row)
    assert c["copies"] == 2                               # row "Copies" column wins
    img = render_label(c)
    raw = build_raw_gzpl(c, img).decode("ascii")
    assert f"^PW{img.width}" in raw and f"^LL{img.height}" in raw and "^PQ2,0,1,N" in raw


def test_pdf_page_is_physical_size(templates, tmp_path):
    c = normalize_cfg(templates["Hang_Tag_50x68.json"])
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
    c = bind_row_to_template(normalize_cfg(templates["Hang_Tag_56x83_Thermal.json"]), sample_row)
    assert render_label(c).tobytes() == render_label(copy.deepcopy(c)).tobytes()


def test_preflight_flags_blank_barcode_and_bad_paper(templates):
    c = normalize_cfg(templates["Hang_Tag_50x68.json"])
    c["elements"].append({"type": "barcode", "value": "", "x": 1, "y": 1, "w": 10, "h": 5})
    errors, _ = preflight_checks(c)
    assert any("barcode is blank" in e for e in errors)
    c["width_mm"] = 0
    assert any("Paper width" in e for e in preflight_checks(c)[0])


def test_preview_with_guides_is_larger_than_label(templates):
    c = normalize_cfg(templates["Hang_Tag_50x68.json"])
    assert render_preview_with_guides(c, scale=2).width > render_label(c).width


def test_all_element_types_render(sample_row):
    c = normalize_cfg({"width_mm": 50, "height_mm": 40, "elements": [
        {"type": "qr", "value": "x", "x": 1, "y": 1, "w": 12, "h": 12},
        {"type": "barcode", "value": "5901234123457", "x": 14, "y": 1, "w": 30, "h": 10, "symbology": "ean13", "show_text": True},
        {"type": "ellipse", "x": 1, "y": 15, "w": 10, "h": 6}, {"type": "fill_box", "x": 13, "y": 15, "w": 5, "h": 5},
        {"type": "text", "text": "hi", "x": 20, "y": 15, "w": 20, "h": 5, "angle": 30}, {"type": "line", "x": 1, "y": 30, "x2": 40, "y2": 35}]})
    img = render_label(c)
    assert img.convert('L').getextrema() == (0, 255)


def test_cached_auto_fit_matches_direct_measurement():
    from PIL import Image, ImageDraw
    from labelapp.core.label_engine import _fit_font, fit_font
    draw = ImageDraw.Draw(Image.new("L", (400, 200), 255))
    for text, w, h, wrap in [("NORTHWIND", 300, 60, False), ("123 Đường Mẫu, Quận 1, TP Hồ Chí Minh", 200, 80, True),
                             ("X" * 80, 50, 10, False)]:
        for _ in range(2):          # second call is served from the cache
            f1, t1 = fit_font(draw, text, w, h, "Arial", 14, 4, False, wrap, 300)
            f2, t2 = _fit_font(draw, text, w, h, "Arial", 14, 4, False, wrap, 300)
            assert t1 == t2 and f1.size == f2.size


MULTILINE_TEXT = "AB-1\t2\nCD-2\t3\r\nEF-3\t4\n"


def _text_cfg(**over):
    e = {"type": "text", "text": MULTILINE_TEXT, "x": 2, "y": 2, "w": 50, "h": 30, "font": "Arial", "bold": True,
         "font_size": 12, "wrap": False, "auto_fit": False, "min_font_size": 4, "align": "left"}
    e.update(over)
    return normalize_cfg({"width_mm": 60, "height_mm": 40, "dpi": 300, "elements": [e]})


def _ink_rows(img):
    """(first, last) y of each run of rows that contain ink: one run per printed line of text."""
    gray = img.convert("L")
    rows = [gray.crop((0, y, gray.width, y + 1)).getextrema()[0] < 128 for y in range(gray.height)]
    runs, start = [], None
    for y, ink in enumerate(rows + [False]):
        if ink and start is None:
            start = y
        elif not ink and start is not None:
            runs.append((start, y - 1))
            start = None
    return runs


def test_clean_text_normalises_breaks_and_tabs():
    assert clean_text("a\t1\r\nb\x0b\u2028c\x01\n\n") == "a    1\nb\n\nc"


@pytest.mark.parametrize("over", [{}, {"wrap": True}, {"auto_fit": True}])
def test_print_keeps_line_breaks_and_line_spacing_of_preview(over):
    cfg = _text_cfg(**over)
    preview, printed = _ink_rows(render_label(cfg)), _ink_rows(render_print_hq(cfg))
    assert len(printed) == 3
    if find_font("Arial", True):        # the preview only matches the PDF with a real font (not on the CI runner)
        assert len(preview) == 3
        assert abs((preview[-1][0] - preview[0][0]) - (printed[-1][0] - printed[0][0])) <= 4


def test_tabs_are_drawn_as_spaces_in_preview_and_print():
    with_tab, with_spaces = _text_cfg(text="AB\tC"), _text_cfg(text="AB    C")
    assert render_print_hq(with_tab).tobytes() == render_print_hq(with_spaces).tobytes()
    assert render_label(with_tab).tobytes() == render_label(with_spaces).tobytes()


def test_wrap_keeps_hard_line_breaks():
    cfg = _text_cfg(text="AAA\nBBB", wrap=True)
    assert len(_ink_rows(render_print_hq(cfg))) == 2
    if find_font("Arial", True):
        assert len(_ink_rows(render_label(cfg))) == 2


@pytest.mark.skipif(find_font("Arial", True) is None, reason="needs the same font in preview and PDF")
def test_auto_fit_print_stops_at_min_font_size_like_preview():
    cfg = _text_cfg(text="LUXURY SUNGLASSES ITALY", auto_fit=True, font_size=8.2, min_font_size=7.6, w=10, h=8)
    width = lambda img: img.convert("L").point(lambda p: 255 if p < 128 else 0).getbbox()[2]
    assert abs(width(render_label(cfg)) - width(render_print_hq(cfg))) <= 12
