"""Label rendering engine: template cfg -> 1-bit raster at printer DPI, plus the on-screen preview with guides.

Moved verbatim from the original app.py so rendered output stays pixel-identical.
"""
import functools
import io
import math
import os
import re
import threading

from PIL import Image, ImageChops, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter

from ..services.image_service import load_element_image
from .geometry import _element_angle, element_center_mm, element_rotation_center, in_fold_band
from .models import normalize_cfg, scale_layout_cfg
from .units import DEFAULT_DPI, mm_to_px

TEXT_LINE_SPACING_PX = 1
TAB_SPACES = 4

@functools.lru_cache(maxsize=64)
def find_font(name="Arial", bold=False):
    windir = os.environ.get("WINDIR", r"C:\Windows")
    fonts = os.path.join(windir, "Fonts")
    n = (name or "Arial").lower().replace(" ", "")
    mapping = {
        ("arial", False): ["arial.ttf"],
        ("arial", True): ["arialbd.ttf"],
        ("segoeui", False): ["segoeui.ttf"],
        ("segoeui", True): ["segoeuib.ttf"],
        ("segoeuilight", False): ["segoeuil.ttf", "segoeui.ttf"],
        ("segoeuilight", True): ["segoeuib.ttf"],
        ("segoeuisemilight", False): ["segoeuisl.ttf", "segoeui.ttf"],
        ("tahoma", False): ["tahoma.ttf"],
        ("tahoma", True): ["tahomabd.ttf"],
        ("verdana", False): ["verdana.ttf"],
        ("verdana", True): ["verdanab.ttf"],
        ("arialnarrow", False): ["arialn.ttf"],
        ("arialnarrow", True): ["arialnb.ttf"],
    }
    candidates = mapping.get((n, bold), []) + [("arialbd.ttf" if bold else "arial.ttf")]
    for c in candidates:
        p = os.path.join(fonts, c)
        if os.path.exists(p):
            return p
    return None

@functools.lru_cache(maxsize=256)
def load_font(name, size_pt, bold=False, dpi=DEFAULT_DPI):
    px = max(5, int(round(float(size_pt) * float(dpi) / 72)))
    path = find_font(name, bold)
    return ImageFont.truetype(path, px) if path else ImageFont.load_default()

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(text):
    """Printable form of an element's text, shared by the raster and the PDF so both show the same characters.

    Any line separator becomes a newline, a tab (cells pasted from Excel) becomes spaces, and other control characters,
    which fonts draw as an empty box, are dropped. Trailing line breaks are removed."""
    text = "\n".join(str(text).splitlines()).replace("\t", " " * TAB_SPACES)
    return "\n".join(_CONTROL_CHARS.sub("", line) for line in text.split("\n")).rstrip("\n")


def wrap_text(draw, text, font, max_width):
    """Word-wrap each line of `text` to max_width; existing line breaks are kept."""
    out = []
    for para in str(text).split("\n"):
        words = para.split()
        if not words:
            out.append("")
            continue
        cur = words[0]
        for word in words[1:]:
            test = cur + " " + word
            bb = draw.textbbox((0, 0), test, font=font)
            if bb[2] - bb[0] <= max_width:
                cur = test
            else:
                out.append(cur)
                cur = word
        out.append(cur)
    return "\n".join(out)

_MEASURE_DRAW = ImageDraw.Draw(Image.new("L", (1, 1)))   # text metrics only; same mode as the label raster


def text_line_pitch_px(font):
    """Distance between baselines of consecutive lines in the raster, so the PDF can use the same line spacing."""
    one = _MEASURE_DRAW.multiline_textbbox((0, 0), "A", font=font, spacing=TEXT_LINE_SPACING_PX)
    two = _MEASURE_DRAW.multiline_textbbox((0, 0), "A\nA", font=font, spacing=TEXT_LINE_SPACING_PX)
    return two[3] - one[3]


def fit_font(draw, text, box_w, box_h, font_name, max_pt, min_pt, bold, wrap, dpi):
    """Largest font (max_pt down to min_pt in 0.5 pt steps) whose text fits the box.

    Text metrics do not depend on the image being drawn on, so for the usual greyscale raster the search is cached:
    re-rendering after an edit (or for the next data row with the same text) skips the step-down loop."""
    if getattr(draw, "mode", None) == "L":
        try:
            return _fit_font_cached(str(text), box_w, box_h, font_name, float(max_pt), float(min_pt), bool(bold),
                                    bool(wrap), dpi)
        except TypeError:           # unhashable argument: measure directly
            pass
    return _fit_font(draw, text, box_w, box_h, font_name, max_pt, min_pt, bold, wrap, dpi)


@functools.lru_cache(maxsize=2048)
def _fit_font_cached(text, box_w, box_h, font_name, max_pt, min_pt, bold, wrap, dpi):
    return _fit_font(_MEASURE_DRAW, text, box_w, box_h, font_name, max_pt, min_pt, bold, wrap, dpi)


def _fit_font(draw, text, box_w, box_h, font_name, max_pt, min_pt, bold, wrap, dpi):
    pt = float(max_pt)
    while pt >= float(min_pt):
        f = load_font(font_name, pt, bold, dpi)
        txt = wrap_text(draw, text, f, box_w) if wrap else text
        bb = draw.multiline_textbbox((0, 0), txt, font=f, spacing=TEXT_LINE_SPACING_PX)
        if (bb[2]-bb[0]) <= box_w and (bb[3]-bb[1]) <= box_h:
            return f, txt
        pt -= 0.5
    f = load_font(font_name, min_pt, bold, dpi)
    return f, wrap_text(draw, text, f, box_w) if wrap else text

@functools.lru_cache(maxsize=128)
def make_barcode(value, dpi, kind="code128", height_mm=10, module_width=0.25, quiet_zone=1.0):
    value = str(value).strip()
    if not value:
        return Image.new("L", (10, 10), 255)
    cls = barcode.get_barcode_class((kind or "code128").lower())
    b = cls(value, writer=ImageWriter())
    buf = io.BytesIO()
    b.write(buf, {
        "module_width": float(module_width),
        "module_height": float(height_mm),
        "quiet_zone": float(quiet_zone),
        "font_size": 0,
        "write_text": False,
        "dpi": int(dpi),
    })
    buf.seek(0)
    return Image.open(buf).convert("L")

@functools.lru_cache(maxsize=256)
def code128_modules(value):
    """Code128 bar pattern as ((offset, width), ...) in modules, plus the total module count (no quiet zone).

    Single source of truth shared by the preview raster and the vector PDF / RAW print path."""
    from reportlab.graphics.barcode import code128
    b = code128.Code128(str(value), barWidth=1, quiet=False, humanReadable=False)
    b.validate(); b.encode(); b.decompose()
    bars, pos = [], 0
    for ch in b.decomposed:
        wd = ord(ch.upper()) - 64
        if ch.isupper():
            bars.append((pos, wd))
        pos += wd
    return tuple(bars), pos

def code128_layout(e, w_px, h_px, dpi):
    """Whole-dot Code128 layout for a box of w_px x h_px printer dots.

    Returns (mod_px, left_px, bar_h_px, bars). Default 'fill' mode makes the barcode as wide as the box allows
    on a whole number of dots per module, so preview == print and every bar edge sits on a printer dot.
    fit == "module" (or physical) keeps the authored module_width / barcode_height_mm instead."""
    bars, total = code128_modules(str(e.get("value", "")).strip())
    if e.get("fit") == "module" or e.get("physical"):
        mod = max(1, int(round(max(0.12, float(e.get("module_width", 0.25))) * dpi / 25.4)))
        while mod > 1 and mod * total > w_px:
            mod -= 1
        bar_h = min(h_px, max(1, mm_to_px(e.get("barcode_height_mm", max(5, h_px * 25.4 / dpi - 2)), dpi)))
    else:
        mod = max(1, w_px // total)
        bar_h = h_px
        if e.get("crop_height"):                      # fill the width, cut the bars to barcode_height_mm
            bar_h = min(h_px, mm_to_px(e.get("barcode_height_mm", 0), dpi) or h_px)
    left = max(0, (w_px - mod * total) // 2)
    return mod, left, bar_h, bars

@functools.lru_cache(maxsize=64)
def qr_matrix(value, level="M"):
    """Boolean module matrix of a QR code (uses reportlab's encoder; no extra dependency)."""
    from reportlab.graphics.barcode import qrencoder
    lv = {"L": qrencoder.QRErrorCorrectLevel.L, "M": qrencoder.QRErrorCorrectLevel.M,
          "Q": qrencoder.QRErrorCorrectLevel.Q, "H": qrencoder.QRErrorCorrectLevel.H}.get(str(level).upper(), qrencoder.QRErrorCorrectLevel.M)
    q = qrencoder.QRCode(None, lv)
    q.addData(str(value))
    q.make()
    n = q.getModuleCount()
    return tuple(tuple(bool(q.isDark(r, c)) for c in range(n)) for r in range(n))

def _qr_square_px(w, h, n):
    """Largest square (px) that holds n modules on whole pixels, centred offset helper."""
    side = min(w, h)
    mod = max(1, side // n)
    return mod, mod * n


def barcode_text_size(e):
    """Point size of the digits under a barcode (`text_size`, else `font_size`, else 6)."""
    return float(e.get("text_size", e.get("font_size", 6.0)))


def barcode_full_code(value, kind):
    """Digits as they print under an EAN/UPC symbol (check digit included)."""
    kind = (kind or "code128").lower()
    if kind in ("ean13", "ean8", "upca"):
        try:
            return barcode.get_barcode_class(kind)(str(value).strip()).get_fullcode()
        except Exception:
            pass
    return str(value).strip()


def barcode_text_height_mm(e):
    if not e.get("show_text"):
        return 0.0
    return barcode_text_size(e) * 25.4 / 72.0 * 1.2

def apply_fold_regions(img, cfg):
    cfg = normalize_cfg(cfg)
    dpi = int(cfg["dpi"])
    out = img.copy()
    for region in cfg.get("fold_regions", []):
        if not region.get("enabled", True):
            continue
        angle = int(region.get("angle", 180)) % 360
        if angle != 180:
            continue
        x = mm_to_px(region.get("x", 0), dpi)
        y = mm_to_px(region.get("y", 0), dpi)
        w = mm_to_px(region.get("w", 0), dpi)
        h = mm_to_px(region.get("h", 0), dpi)
        if w <= 0 or h <= 0:
            continue
        x = max(0, x)
        y = max(0, y)
        x2 = min(out.width, x + w)
        y2 = min(out.height, y + h)
        if x2 <= x or y2 <= y:
            continue
        crop = out.crop((x, y, x2, y2)).rotate(180, expand=False)
        out.paste(crop, (x, y))
    return out


def _draw_element(img, draw, e, cfg, dpi):
    t = e.get("type", "").lower()
    x = mm_to_px(e.get("x", 0), dpi)
    y = mm_to_px(e.get("y", 0), dpi)
    w = mm_to_px(e.get("w", cfg["width_mm"] - e.get("x", 0)), dpi)
    h = mm_to_px(e.get("h", cfg["height_mm"] - e.get("y", 0)), dpi)

    if t == "text":
        text = clean_text(e.get("text", ""))
        font_name = e.get("font", "Arial")
        bold = bool(e.get("bold", False))
        size = float(e.get("font_size", 8))
        wrap = bool(e.get("wrap", False))
        align = e.get("align", "left")
        if e.get("auto_fit", False):
            f, final_text = fit_font(draw, text, w, h, font_name, size, e.get("min_font_size", 4), bold, wrap, dpi)
        else:
            f = load_font(font_name, size, bold, dpi)
            final_text = wrap_text(draw, text, f, w) if wrap else text

        bb = draw.multiline_textbbox((0, 0), final_text, font=f, spacing=TEXT_LINE_SPACING_PX)
        tw = bb[2] - bb[0]
        tx = x
        if align == "center":
            tx = x + max(0, (w - tw) // 2)
        elif align == "right":
            tx = x + max(0, w - tw)
        draw.multiline_text((tx, y), final_text, font=f, fill=0, spacing=TEXT_LINE_SPACING_PX, align=align)

    elif t == "line":
        x2 = mm_to_px(e.get("x2", e.get("x", 0)+e.get("w", 0)), dpi)
        y2 = mm_to_px(e.get("y2", e.get("y", 0)), dpi)
        draw.line((x, y, x2, y2), fill=0, width=max(1, mm_to_px(e.get("thickness", 0.2), dpi)))

    elif t == "box":
        draw.rectangle((x, y, x+w, y+h), outline=0, width=max(1, mm_to_px(e.get("thickness", 0.2), dpi)))

    elif t == "fill_box":
        draw.rectangle((x, y, x+w, y+h), fill=0)

    elif t == "ellipse":
        draw.ellipse((x, y, x+w, y+h), outline=0, width=max(1, mm_to_px(e.get("thickness", 0.2), dpi)))

    elif t == "barcode":
        text_h = mm_to_px(barcode_text_height_mm(e), dpi)
        bars_h = max(1, h - text_h)
        value = str(e.get("value", "")).strip()
        sym = str(e.get("symbology", "code128")).lower()
        dark = None
        if value and sym == "code128":
            mod, left, bar_h, bars = code128_layout(e, w, bars_h, dpi)
            by = y + (bars_h - bar_h) // 2
            for off, wd in bars:
                draw.rectangle((x + left + off * mod, by, x + left + (off + wd) * mod - 1, by + bar_h - 1), fill=0)
        elif value:
            bc = make_barcode(
                value, dpi,
                e.get("symbology", "code128"),
                60 if e.get("crop_height", False) else e.get("barcode_height_mm", max(5, e.get("h", 12)-2)),
                e.get("module_width", 0.25),
                e.get("quiet_zone", 1.0)
            )
            if e.get("crop_height", False):
                # Scale by width only, then cut the bars to the wanted height (bars carry no information vertically).
                ratio = w / bc.width
                nw, nh = max(1, int(bc.width * ratio)), max(1, int(bc.height * ratio))
                bc = bc.resize((nw, nh), Image.Resampling.NEAREST)
                want_h = mm_to_px(e.get("barcode_height_mm", 0), dpi) or bars_h
                keep = max(1, min(nh, bars_h, want_h))
                top = (nh - keep) // 2
                bc = bc.crop((0, top, nw, top + keep))
                nh = keep
            else:
                ratio = min(w / bc.width, bars_h / bc.height)
                nw, nh = max(1, int(bc.width * ratio)), max(1, int(bc.height * ratio))
                bc = bc.resize((nw, nh), Image.Resampling.NEAREST)
            by = y + (bars_h - nh) // 2
            img.paste(bc, (x + (w - nw) // 2, by))
            dark = bc.point(lambda p: 255 if p < 128 else 0).getbbox()
        if text_h and value:
            f = load_font(e.get("font", "Arial"), barcode_text_size(e), False, dpi)
            kind = str(e.get("symbology", "code128")).lower()
            code = barcode_full_code(value, kind)
            ty = y + bars_h
            if kind == "ean13" and len(code) == 13 and dark:
                # EAN-13 layout: 1st digit left of the bars, then 6 digits under each half.
                bx = x + (w - nw) // 2
                m = (dark[2] - dark[0]) / 95.0
                x0 = bx + dark[0]
                def put(txt, x_from):
                    for i, ch in enumerate(txt):  # one 7-module cell per digit, like a printed EAN-13
                        bb = draw.textbbox((0, 0), ch, font=f)
                        cx = x_from + (i + 0.5) * 7 * m
                        draw.text((int(cx - (bb[2] - bb[0]) / 2) - bb[0], ty - bb[1]), ch, font=f, fill=0)
                bb = draw.textbbox((0, 0), code[0], font=f)
                draw.text((int(x0 - 7 * m - (bb[2] - bb[0]) / 2) - bb[0], ty - bb[1]), code[0], font=f, fill=0)
                put(code[1:7], x0 + 3 * m)
                put(code[7:], x0 + 50 * m)
            else:
                bb = draw.textbbox((0, 0), code, font=f)
                draw.text((x + max(0, (w - (bb[2] - bb[0])) // 2) - bb[0], ty - bb[1]), code, font=f, fill=0)

    elif t == "qr":
        value = str(e.get("value", "")).strip()
        if value:
            m = qr_matrix(value, e.get("ecc", "M"))
            n = len(m)
            quiet = 0  # the box itself is the quiet zone
            mod, side = _qr_square_px(w, h, n)
            ox = x + (w - side) // 2
            oy = y + (h - side) // 2
            for r, rowv in enumerate(m):
                c = 0
                while c < n:
                    if rowv[c]:
                        c0 = c
                        while c < n and rowv[c]:
                            c += 1
                        draw.rectangle((ox + c0 * mod, oy + r * mod, ox + c * mod - 1, oy + (r + 1) * mod - 1), fill=0)
                    else:
                        c += 1

    elif t == "image":
        im = load_element_image(e.get("path", ""))
        if im is not None and w > 0 and h > 0:
            ratio = min(w / im.width, h / im.height) if e.get("fit", "contain") != "stretch" else None
            if ratio is None:
                nw, nh = w, h
            else:
                nw, nh = max(1, int(im.width * ratio)), max(1, int(im.height * ratio))
            pic = im.resize((nw, nh), Image.Resampling.LANCZOS)
            if e.get("dither", False):
                pic = pic.convert("1").convert("L")
            img.paste(pic, (x + (w - nw) // 2, y + (h - nh) // 2))


def _draw_element_rotated(img, e, cfg, dpi, angle):
    """Draw one element rotated by `angle` degrees (clockwise) around its own centre.

    The element is rendered on a 2x supersampled square layer, rotated, scaled back
    and merged with the page using "darkest pixel wins".
    """
    cx_mm, cy_mm = element_rotation_center(e)
    t = str(e.get("type", "")).lower()
    if t == "line":
        ex = abs(float(e.get("x2", e.get("x", 0))) - float(e.get("x", 0)))
        ey = abs(float(e.get("y2", e.get("y", 0))) - float(e.get("y", 0)))
    else:
        ex = float(e.get("w", 0)); ey = float(e.get("h", 0))
    r_mm = math.hypot(ex, ey) / 2.0 + 2.0 + float(e.get("thickness", 0) or 0)
    ss = 2
    layer_dpi = dpi * ss
    size = max(4, mm_to_px(2 * r_mm, layer_dpi))
    layer = Image.new("L", (size, size), 255)
    ldraw = ImageDraw.Draw(layer)
    e2 = dict(e)
    dx = r_mm - cx_mm; dy = r_mm - cy_mm
    for k in ("x", "x2"):
        if k in e2:
            e2[k] = float(e2[k]) + dx
    for k in ("y", "y2"):
        if k in e2:
            e2[k] = float(e2[k]) + dy
    lcfg = dict(cfg); lcfg["width_mm"] = 2 * r_mm; lcfg["height_mm"] = 2 * r_mm
    _draw_element(layer, ldraw, e2, lcfg, layer_dpi)
    layer = layer.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=255)
    out_size = max(2, mm_to_px(2 * r_mm, dpi))
    layer = layer.resize((out_size, out_size), Image.Resampling.BOX)
    full = Image.new("L", img.size, 255)
    full.paste(layer, (mm_to_px(cx_mm, dpi) - out_size // 2, mm_to_px(cy_mm, dpi) - out_size // 2))
    merged = ImageChops.darker(img, full)
    img.paste(merged)


# The designer preview renders in a worker thread while printing / thumbnails render on the UI thread. Pillow's
# FreeType faces (shared through the font cache) are not safe to use from two threads at once, so renders are
# serialised. Re-entrant because render_preview_with_guides() and the PDF export call render_label().
_RENDER_LOCK = threading.RLock()


def render_label(cfg):
    with _RENDER_LOCK:
        return _render_label(cfg)


def _render_label(cfg):
    cfg = scale_layout_cfg(normalize_cfg(cfg))
    dpi = int(cfg["dpi"])
    wpx = mm_to_px(cfg["width_mm"], dpi)
    hpx = mm_to_px(cfg["height_mm"], dpi)

    img = Image.new("L", (wpx, hpx), 255)
    draw = ImageDraw.Draw(img)

    # Fold regions: an element belongs to a region by its centre (same rule as the PDF export and the designer),
    # and is flipped 180 degrees about the region centre as a whole -- so text running past the region/label edge
    # stays attached to its element instead of being cut at the region border.
    folds = [r for r in cfg.get("fold_regions", [])
             if r.get("enabled", True) and int(r.get("angle", 180)) % 360 == 180
             and float(r.get("w", 0)) > 0 and float(r.get("h", 0)) > 0]
    layers = {}

    def _fold_of(e):
        cx, cy = element_center_mm(e)
        for i, r in enumerate(folds):
            if in_fold_band(cx, cy, r):
                return i
        return None

    for e in cfg["elements"]:
        if e.get("physical"):
            continue
        fi = _fold_of(e) if folds else None
        if fi is None:
            target, tdraw = img, draw
        else:
            if fi not in layers:
                layer = Image.new("L", (wpx, hpx), 255)
                layers[fi] = (layer, ImageDraw.Draw(layer))
            target, tdraw = layers[fi]
        angle = _element_angle(e) % 360.0
        if abs(angle) > 0.0001 and abs(angle - 360.0) > 0.0001:
            _draw_element_rotated(target, e, cfg, dpi, angle)
        else:
            _draw_element(target, tdraw, e, cfg, dpi)

    for fi, (layer, _) in layers.items():
        r = folds[fi]
        cx = mm_to_px(float(r["x"]) + float(r["w"]) / 2, dpi)
        cy = mm_to_px(float(r["y"]) + float(r["h"]) / 2, dpi)
        flipped = Image.new("L", (wpx, hpx), 255)
        flipped.paste(layer.rotate(180), (2 * cx - wpx, 2 * cy - hpx))   # point p -> 2c - p
        img = ImageChops.darker(img, flipped)

    threshold = int(cfg.get("threshold", 180))
    out = img.point(lambda p: 0 if p < threshold else 255, mode="1")
    physical = [e for e in cfg["elements"] if e.get("physical")]
    if physical:
        # "Physical" elements (rulers/test marks) are placed on the paper AFTER folding,
        # so they never get flipped with a fold region.
        pimg = Image.new("L", (wpx, hpx), 255)
        pdraw = ImageDraw.Draw(pimg)
        for e in physical:
            _draw_element(pimg, pdraw, e, cfg, dpi)
        pbits = pimg.point(lambda p: 0 if p < threshold else 255, mode="L")
        out = ImageChops.darker(out.convert("L"), pbits).point(lambda p: 0 if p < 128 else 255, mode="1")
    if str(cfg.get("orientation", "portrait")).lower() == "landscape":
        out = out.rotate(90, expand=True)

    rotation_deg = float(cfg.get("rotation_deg", 0.0))
    if abs(rotation_deg) > 0.0001:
        out = out.rotate(rotation_deg, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=1)

    # True global physical offset: shift the final composed print,
    # so folded/rotated faces move in the same physical direction.
    dx = mm_to_px(cfg.get("offset_x_mm", 0), dpi)
    dy = mm_to_px(cfg.get("offset_y_mm", 0), dpi)
    if dx != 0 or dy != 0:
        shifted = Image.new("1", out.size, 1)
        shifted.paste(out, (dx, dy))
        out = shifted

    return out

def clip_to_printable_area(img, cfg):
    """Hard clip final output to an optional physical printable area."""
    cfg = normalize_cfg(cfg)
    area = cfg.get("printable_area") or {}
    if not area.get("enabled", False):
        return img
    dpi = int(cfg.get("dpi", DEFAULT_DPI))
    x = max(0, mm_to_px(area.get("x", 0), dpi))
    y = max(0, mm_to_px(area.get("y", 0), dpi))
    w = max(0, mm_to_px(area.get("w", cfg.get("width_mm", 0)), dpi))
    h = max(0, mm_to_px(area.get("h", cfg.get("height_mm", 0)), dpi))
    x2 = min(img.width, x + w)
    y2 = min(img.height, y + h)
    bg = 1 if img.mode == "1" else 255
    out = Image.new(img.mode, img.size, bg)
    if x2 > x and y2 > y:
        out.paste(img.crop((x, y, x2, y2)), (x, y))
    return out

def render_preview_with_guides(cfg, scale=3, show_guides=True, show_fold=True):
    cfg = normalize_cfg(cfg)
    rendered = render_label({**cfg, "dpi": int(cfg["dpi"]) * int(scale)})
    page = rendered.convert("RGB")

    margin = 36
    canvas = Image.new("RGB", (page.width + margin*2, page.height + margin*2), (242, 242, 242))
    canvas.paste(page, (margin, margin))

    draw = ImageDraw.Draw(canvas)
    # page border
    draw.rectangle((margin, margin, margin + page.width - 1, margin + page.height - 1), outline=(100, 100, 100), width=2)

    area = cfg.get("virtual_print_area") or {}
    if area.get("show", True):
        sdpi = int(cfg["dpi"]) * int(scale)
        ax = margin + mm_to_px(area.get("x", 0), sdpi)
        ay = margin + mm_to_px(area.get("y", 0), sdpi)
        aw = mm_to_px(area.get("w", cfg.get("width_mm", 0)), sdpi)
        ah = mm_to_px(area.get("h", cfg.get("height_mm", 0)), sdpi)
        draw.rectangle((ax, ay, ax+aw, ay+ah), outline=(30, 160, 60), width=max(2, scale))

    if show_fold:
        for fr in cfg.get("fold_regions", []):
            if not fr.get("enabled", True):
                continue
            x = margin + mm_to_px(fr.get("x", 0), cfg["dpi"] * scale)
            y = margin + mm_to_px(fr.get("y", 0), cfg["dpi"] * scale)
            w = mm_to_px(fr.get("w", 0), cfg["dpi"] * scale)
            h = mm_to_px(fr.get("h", 0), cfg["dpi"] * scale)
            draw.rectangle((x, y, x+w, y+h), outline=(140, 70, 255), width=2)
            label = fr.get("name", "FOLD")
            draw.text((x+4, y+4), label, fill=(140, 70, 255))

    if show_guides:
        for g in cfg.get("preview_guides", []):
            if not g.get("show", True):
                continue
            gtype = g.get("type", "box").lower()
            color_name = str(g.get("color", "red")).lower()
            color_map = {
                "red": (230, 30, 30),
                "blue": (30, 80, 230),
                "green": (30, 160, 60),
                "orange": (230, 120, 20),
                "purple": (150, 60, 220),
                "gray": (120, 120, 120),
                "black": (0, 0, 0),
            }
            color = color_map.get(color_name, (230, 30, 30))
            if gtype == "box":
                x = margin + mm_to_px(g.get("x", 0), cfg["dpi"] * scale)
                y = margin + mm_to_px(g.get("y", 0), cfg["dpi"] * scale)
                w = mm_to_px(g.get("w", 0), cfg["dpi"] * scale)
                h = mm_to_px(g.get("h", 0), cfg["dpi"] * scale)
                draw.rectangle((x, y, x+w, y+h), outline=color, width=3)
                if g.get("name"):
                    draw.text((x+4, y+4), str(g["name"]), fill=color)
            elif gtype == "line":
                x1 = margin + mm_to_px(g.get("x", 0), cfg["dpi"] * scale)
                y1 = margin + mm_to_px(g.get("y", 0), cfg["dpi"] * scale)
                x2 = margin + mm_to_px(g.get("x2", 0), cfg["dpi"] * scale)
                y2 = margin + mm_to_px(g.get("y2", 0), cfg["dpi"] * scale)
                draw.line((x1, y1, x2, y2), fill=color, width=3)
                if g.get("name"):
                    draw.text((x1+4, y1+4), str(g["name"]), fill=color)

    return canvas
