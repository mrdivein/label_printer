"""Vector PDF master + physical-DPI raster (the "VECTOR master -> 1 raster @ printer DPI" print pipeline)."""
import io
import os
import re
import tempfile

from PIL import Image

from ..services.image_service import load_element_image
from .geometry import (_element_angle, element_center_mm, element_rotation_center, point_in_region,
                       rotate_point_cw)
from .label_engine import barcode_text_height_mm, find_font, make_barcode, qr_matrix, render_label
from .models import normalize_cfg, scale_layout_cfg
from .units import DEFAULT_DPI, mm_to_px

def _pdf_font_name(name="Arial", bold=False):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    reg_name = "LP_" + re.sub(r"[^A-Za-z0-9_]+", "_", str(name or "Arial"))
    reg_name += "_Bold" if bold else "_Regular"

    try:
        pdfmetrics.getFont(reg_name)
        return reg_name
    except Exception:
        pass

    path = find_font(name, bold)
    if path:
        try:
            pdfmetrics.registerFont(TTFont(reg_name, path))
            return reg_name
        except Exception:
            pass

    return "Helvetica-Bold" if bold else "Helvetica"

def _pdf_wrap_text(text, font_name, font_size, max_width_pt):
    from reportlab.pdfbase import pdfmetrics
    words = str(text).split()
    if not words:
        return [""]

    lines = []
    cur = words[0]
    for word in words[1:]:
        test = cur + " " + word
        if pdfmetrics.stringWidth(test, font_name, font_size) <= max_width_pt:
            cur = test
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines

def _element_fold_region(cfg, e):
    if e.get("physical"):
        return None
    cx, cy = element_center_mm(e)
    for r in cfg.get("fold_regions", []):
        if not r.get("enabled", True):
            continue
        if int(r.get("angle", 180)) % 360 != 180:
            continue
        if point_in_region(cx, cy, r):
            return r
    return None

def _transform_point_for_pdf(cfg, x, y, fold_region=None):
    """
    Template coordinates are top-left mm.
    Applies fold -> page orientation -> static skew -> final X/Y offset.
    Returns PDF-space coordinates in points.
    """
    import math
    from reportlab.lib.units import mm as RL_MM

    cfg = normalize_cfg(cfg)
    base_w = float(cfg["width_mm"])
    base_h = float(cfg["height_mm"])

    x = float(x)
    y = float(y)

    if fold_region is not None:
        rcx = float(fold_region.get("x", 0)) + float(fold_region.get("w", 0)) / 2.0
        rcy = float(fold_region.get("y", 0)) + float(fold_region.get("h", 0)) / 2.0
        x = 2.0 * rcx - x
        y = 2.0 * rcy - y

    orientation = str(cfg.get("orientation", "portrait")).lower()
    if orientation == "landscape":
        # Match Pillow rotate(90, expand=True): visual CCW.
        x, y = y, base_w - x
        page_w = base_h
        page_h = base_w
    else:
        page_w = base_w
        page_h = base_h

    # Convert to PDF bottom-left coordinates.
    px = x * RL_MM
    py = (page_h - y) * RL_MM

    # Match raster static skew around page center.
    angle = float(cfg.get("rotation_deg", 0.0))
    if abs(angle) > 0.0001:
        a = math.radians(angle)
        pcx = page_w * RL_MM / 2.0
        pcy = page_h * RL_MM / 2.0
        dx = px - pcx
        dy = py - pcy
        px = pcx + dx * math.cos(a) - dy * math.sin(a)
        py = pcy + dx * math.sin(a) + dy * math.cos(a)

    # Final physical offset. Positive Y in config means down.
    px += float(cfg.get("offset_x_mm", 0.0)) * RL_MM
    py -= float(cfg.get("offset_y_mm", 0.0)) * RL_MM

    return px, py

def _element_total_angle(cfg, e, fold_region=None):
    angle = 0.0
    if fold_region is not None:
        angle += 180.0
    if str(cfg.get("orientation", "portrait")).lower() == "landscape":
        angle += 90.0
    angle += float(cfg.get("rotation_deg", 0.0))
    # Per-element angle is clockwise in the designer; PDF rotation is counter-clockwise.
    angle -= _element_angle(e)
    return angle

def save_exact_print_pdf(cfg, path, return_raster=False):
    """
    VECTOR master PDF used by both PDF Proof and Print via PDF.

    Text, lines, boxes and Code128 stay vector in the PDF.
    The PDF is rasterized only once, later, at the physical printer DPI.
    Preview guides are never included.
    """
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.graphics.barcode import code128
    from reportlab.lib.units import mm as RL_MM

    cfg_original = cfg
    cfg = scale_layout_cfg(normalize_cfg(cfg))

    base_w = float(cfg["width_mm"])
    base_h = float(cfg["height_mm"])
    orientation = str(cfg.get("orientation", "portrait")).lower()

    if orientation == "landscape":
        page_w_mm, page_h_mm = base_h, base_w
    else:
        page_w_mm, page_h_mm = base_w, base_h

    c = canvas.Canvas(
        path,
        pagesize=(page_w_mm * RL_MM, page_h_mm * RL_MM),
        pageCompression=1
    )

    clip_active = False  # v18: no hard clipping; virtual area is guide-only

    for e in cfg.get("elements", []):
        t = str(e.get("type", "")).lower()
        fr = _element_fold_region(cfg, e)
        angle = _element_total_angle(cfg, e, fr)

        if t == "line":
            x1 = float(e.get("x", 0))
            y1 = float(e.get("y", 0))
            x2 = float(e.get("x2", x1))
            y2 = float(e.get("y2", y1))
            la = _element_angle(e)
            if abs(la) > 0.0001:
                lcx, lcy = element_rotation_center(e)
                x1, y1 = rotate_point_cw(x1, y1, lcx, lcy, la)
                x2, y2 = rotate_point_cw(x2, y2, lcx, lcy, la)
            p1 = _transform_point_for_pdf(cfg, x1, y1, fr)
            p2 = _transform_point_for_pdf(cfg, x2, y2, fr)
            c.setLineWidth(max(0.1, float(e.get("thickness", 0.2)) * RL_MM))
            c.line(p1[0], p1[1], p2[0], p2[1])
            continue

        x = float(e.get("x", 0))
        y = float(e.get("y", 0))
        w = float(e.get("w", base_w - x))
        h = float(e.get("h", base_h - y))
        cx = x + w / 2.0
        cy = y + h / 2.0
        pcx, pcy = _transform_point_for_pdf(cfg, cx, cy, fr)

        c.saveState()
        c.translate(pcx, pcy)
        if abs(angle) > 0.0001:
            c.rotate(angle)

        left = -w * RL_MM / 2.0
        bottom = -h * RL_MM / 2.0
        top = h * RL_MM / 2.0

        if t == "box":
            c.setLineWidth(max(0.1, float(e.get("thickness", 0.2)) * RL_MM))
            c.rect(left, bottom, w * RL_MM, h * RL_MM, fill=0, stroke=1)

        elif t == "fill_box":
            c.rect(left, bottom, w * RL_MM, h * RL_MM, fill=1, stroke=0)

        elif t == "text":
            text = str(e.get("text", ""))
            font_name = _pdf_font_name(e.get("font", "Arial"), bool(e.get("bold", False)))
            size = float(e.get("font_size", 8))
            min_size = float(e.get("min_font_size", 4))
            wrap = bool(e.get("wrap", True))
            auto_fit = bool(e.get("auto_fit", False))
            align = str(e.get("align", "left")).lower()

            max_w_pt = w * RL_MM
            max_h_pt = h * RL_MM
            chosen = size

            while True:
                lines = _pdf_wrap_text(text, font_name, chosen, max_w_pt) if wrap else [text]
                leading = chosen * 1.08
                max_line_w = max(
                    [pdfmetrics.stringWidth(line, font_name, chosen) for line in lines] or [0]
                )
                total_h = len(lines) * leading
                if (
                    not auto_fit
                    or (max_line_w <= max_w_pt and total_h <= max_h_pt)
                    or chosen <= min_size
                ):
                    break
                chosen -= 0.5

            c.setFont(font_name, chosen)

            for i, line in enumerate(lines):
                line_w = pdfmetrics.stringWidth(line, font_name, chosen)
                if align == "center":
                    tx = left + max(0.0, (max_w_pt - line_w) / 2.0)
                elif align == "right":
                    tx = left + max(0.0, max_w_pt - line_w)
                else:
                    tx = left

                baseline = top - chosen - i * leading
                c.drawString(tx, baseline, line)

        elif t == "barcode":
            value = str(e.get("value", "")).strip()
            text_mm = barcode_text_height_mm(e)
            if value:
                sym = str(e.get("symbology", "code128")).lower()
                if text_mm:
                    # Human-readable digits under the bars; bars use the remaining height.
                    tsize = float(e.get("text_size", 6.0))
                    tfont = _pdf_font_name(e.get("font", "Arial"), False)
                    c.setFont(tfont, tsize)
                    c.drawString(left + max(0.0, (w * RL_MM - pdfmetrics.stringWidth(value, tfont, tsize)) / 2.0),
                                 bottom + tsize * 0.2, value)
                    bottom += text_mm * RL_MM
                    h -= text_mm
                if sym == "code128":
                    target_w = w * RL_MM
                    target_h = min(
                        h,
                        float(e.get("barcode_height_mm", max(5, h - 2)))
                    ) * RL_MM

                    pdpi = max(1, int(cfg.get("dpi", DEFAULT_DPI)))
                    wanted_mm = max(0.12, float(e.get("module_width", 0.25)))
                    wanted_dots = max(1, int(round(wanted_mm * pdpi / 25.4)))
                    bc = None
                    for dots in range(wanted_dots, 0, -1):
                        snapped_mm = dots * 25.4 / pdpi
                        trial_width = snapped_mm * RL_MM
                        trial = code128.Code128(value, barHeight=target_h, barWidth=trial_width, humanReadable=False)
                        if trial.width <= target_w or dots == 1:
                            bc = trial
                            break

                    bx = left + max(0.0, (target_w - bc.width) / 2.0)
                    by = bottom + max(0.0, (h * RL_MM - target_h) / 2.0)
                    bc.drawOn(c, bx, by)
                else:
                    # Unsupported barcode types keep a high-resolution raster fallback,
                    # but Code128 (the bundled templates) remains vector.
                    hi_dpi = max(1200, int(cfg.get("dpi", DEFAULT_DPI)) * 4)
                    bc_img = make_barcode(
                        value,
                        hi_dpi,
                        sym,
                        e.get("barcode_height_mm", max(5, h - 2)),
                        e.get("module_width", 0.25),
                        e.get("quiet_zone", 1.0)
                    )
                    from reportlab.lib.utils import ImageReader
                    buf = io.BytesIO()
                    bc_img.save(buf, format="PNG")
                    buf.seek(0)
                    c.drawImage(
                        ImageReader(buf),
                        left,
                        bottom,
                        width=w * RL_MM,
                        height=h * RL_MM,
                        preserveAspectRatio=True,
                        anchor="c",
                        mask="auto"
                    )

        elif t == "qr":
            value = str(e.get("value", "")).strip()
            if value:
                m = qr_matrix(value, e.get("ecc", "M"))
                n = len(m)
                pdpi = max(1, int(cfg.get("dpi", DEFAULT_DPI)))
                side_dots = int(min(w, h) * pdpi / 25.4)
                mod_mm = max(1, side_dots // n) * 25.4 / pdpi      # whole printer dots per module
                mod = mod_mm * RL_MM
                side = mod * n
                ox = left + (w * RL_MM - side) / 2.0
                oy = bottom + (h * RL_MM - side) / 2.0
                for r, rowv in enumerate(m):
                    cidx = 0
                    while cidx < n:
                        if rowv[cidx]:
                            c0 = cidx
                            while cidx < n and rowv[cidx]:
                                cidx += 1
                            c.rect(ox + c0 * mod, oy + (n - 1 - r) * mod, (cidx - c0) * mod, mod, fill=1, stroke=0)
                        else:
                            cidx += 1

        elif t == "image":
            im = load_element_image(e.get("path", ""))
            if im is not None:
                from reportlab.lib.utils import ImageReader
                if e.get("dither", False):
                    im = im.convert("1").convert("L")
                c.drawImage(ImageReader(im), left, bottom, width=w * RL_MM, height=h * RL_MM,
                            preserveAspectRatio=(e.get("fit", "contain") != "stretch"), anchor="c", mask="auto")

        c.restoreState()

    if clip_active:
        c.restoreState()

    c.showPage()
    c.save()

    # The direct raster is only needed for proofs/comparison; skip the extra render otherwise.
    return render_label(cfg_original) if return_raster else None

def rasterize_exact_print_pdf(path, dpi, threshold=180):
    """
    Render the generated PDF back at the printer's physical DPI.
    Used by the optional PDF -> printer pipeline.
    """
    import fitz

    doc = fitz.open(path)
    try:
        if len(doc) != 1:
            raise RuntimeError("Print PDF must contain exactly one page.")

        page = doc[0]
        matrix = fitz.Matrix(float(dpi) / 72.0, float(dpi) / 72.0)
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)

        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        return img.point(lambda p: 0 if p < int(threshold) else 255, mode="1")
    finally:
        doc.close()

def compare_print_rasters(a, b):
    """
    Quick bit-level parity check between direct raster and PDF round-trip raster.
    Returns (same_size, differing_pixels, total_pixels).
    """
    aa = a.convert("1")
    bb = b.convert("1")
    if aa.size != bb.size:
        return False, None, None

    pa = aa.load()
    pb = bb.load()
    diff = 0
    total = aa.width * aa.height
    for y in range(aa.height):
        for x in range(aa.width):
            if pa[x, y] != pb[x, y]:
                diff += 1
    return True, diff, total


def is_virtual_printer_name(name):
    low = str(name or "").lower()
    tokens = (
        "pdf", "xps", "onenote", "fax", "document writer",
        "adobe pdf", "foxit pdf", "nitro pdf", "cute pdf"
    )
    return any(t in low for t in tokens)

def render_print_hq(cfg, temp_dir=None):
    """Highest-quality thermal raster with one final 1-bit conversion."""
    cfg = normalize_cfg(cfg)
    temp_dir = temp_dir or tempfile.gettempdir()
    os.makedirs(temp_dir, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="label_hq_", suffix=".pdf", dir=temp_dir)
    os.close(fd)
    try:
        save_exact_print_pdf(cfg, path)
        physical_dpi = int(cfg.get("dpi", DEFAULT_DPI))
        mode = str(cfg.get("render_mode", "thermal_crisp")).lower()
        oversample = max(1, min(6, int(cfg.get("oversample", 4))))
        threshold = int(cfg.get("threshold", 145))
        if mode == "thermal_crisp" and oversample > 1:
            import fitz
            doc = fitz.open(path)
            try:
                page = doc[0]
                hi_dpi = physical_dpi * oversample
                matrix = fitz.Matrix(float(hi_dpi) / 72.0, float(hi_dpi) / 72.0)
                pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)
                hi = Image.frombytes("L", (pix.width, pix.height), pix.samples)
            finally:
                doc.close()
            target_w = mm_to_px(cfg.get("width_mm", 50), physical_dpi)
            target_h = mm_to_px(cfg.get("height_mm", 68), physical_dpi)
            if str(cfg.get("orientation", "portrait")).lower() == "landscape":
                target_w, target_h = target_h, target_w
            gray = hi.resize((target_w, target_h), Image.Resampling.LANCZOS)
            img = gray.point(lambda p: 0 if p < threshold else 255, mode="1")
        else:
            img = rasterize_exact_print_pdf(path, physical_dpi, threshold)
        return img
    finally:
        try: os.remove(path)
        except Exception: pass
