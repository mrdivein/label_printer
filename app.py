
import io
import math
import os
import re
import csv
import json
import copy
import datetime
import csv as csvmod
import urllib.parse
import urllib.request
import tempfile
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageTk
import barcode
from barcode.writer import ImageWriter
from openpyxl import load_workbook

DEFAULT_DPI = 300
PLACEHOLDER_RE = re.compile(r"\{\{([^{}]+)\}\}")

# ----------------------------
# Core helpers
# ----------------------------
def mm_to_px(v, dpi):
    return int(round(float(v) * float(dpi) / 25.4))

def normalize_cfg(cfg):
    cfg = dict(cfg or {})
    cfg.setdefault("width_mm", 50)
    cfg.setdefault("height_mm", 68)
    cfg.setdefault("dpi", DEFAULT_DPI)
    cfg.setdefault("orientation", "portrait")
    cfg.setdefault("copies", 1)
    cfg.setdefault("offset_x_mm", 0.0)
    cfg.setdefault("offset_y_mm", 0.0)
    cfg.setdefault("threshold", 145)
    cfg.setdefault("render_mode", "thermal_crisp")
    cfg.setdefault("oversample", 4)
    # v18: virtual print area is a VISUAL guide only. It never clips output.
    if "virtual_print_area" not in cfg:
        old_area = cfg.get("printable_area") or {}
        cfg["virtual_print_area"] = {
            "show": True,
            "x": float(old_area.get("x", 0.0)),
            "y": float(old_area.get("y", 0.0)),
            "w": float(old_area.get("w", cfg.get("width_mm", 50))),
            "h": float(old_area.get("h", cfg.get("height_mm", 68))),
        }
    # Legacy key remains readable for old JSON, but is ignored as a hard clip.
    cfg.setdefault("printable_area", {"enabled": False, "x": 0.0, "y": 0.0, "w": cfg.get("width_mm", 50), "h": cfg.get("height_mm", 68)})
    cfg.setdefault("elements", [])
    cfg.setdefault("data_bindings", {})
    cfg.setdefault("fold_regions", [])
    cfg.setdefault("preview_guides", [])   # non-printing guides for preview only
    cfg.setdefault("rotation_deg", 0.0)
    # v21: printer size compensation (percent). 100 = artwork printed at nominal size.
    cfg.setdefault("scale_x_pct", 100.0)
    cfg.setdefault("scale_y_pct", 100.0)
    return cfg

def scale_layout_cfg(cfg):
    """Return cfg with artwork geometry scaled by scale_x_pct / scale_y_pct (printer size compensation).

    Page size is untouched; elements and fold regions are scaled about the page's top-left corner.
    """
    try:
        sx = float(cfg.get("scale_x_pct", 100.0)) / 100.0
        sy = float(cfg.get("scale_y_pct", 100.0)) / 100.0
    except Exception:
        return cfg
    if abs(sx - 1.0) < 1e-6 and abs(sy - 1.0) < 1e-6 or sx <= 0 or sy <= 0:
        return cfg
    avg = (sx + sy) / 2.0
    out = dict(cfg)
    els = []
    for e in cfg.get("elements", []):
        e = dict(e)
        for k in ("x", "x2", "w", "module_width"):
            if k in e:
                try: e[k] = float(e[k]) * sx
                except Exception: pass
        for k in ("y", "y2", "h", "barcode_height_mm"):
            if k in e:
                try: e[k] = float(e[k]) * sy
                except Exception: pass
        for k in ("font_size", "min_font_size", "thickness"):
            if k in e:
                try: e[k] = float(e[k]) * avg
                except Exception: pass
        els.append(e)
    out["elements"] = els
    frs = []
    for r in cfg.get("fold_regions", []):
        r = dict(r)
        for k in ("x", "w"):
            if k in r: r[k] = float(r[k]) * sx
        for k in ("y", "h"):
            if k in r: r[k] = float(r[k]) * sy
        frs.append(r)
    out["fold_regions"] = frs
    return out

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

def load_font(name, size_pt, bold=False, dpi=DEFAULT_DPI):
    px = max(5, int(round(float(size_pt) * float(dpi) / 72)))
    path = find_font(name, bold)
    return ImageFont.truetype(path, px) if path else ImageFont.load_default()

def wrap_text(draw, text, font, max_width):
    words = str(text).split()
    if not words:
        return ""
    lines, cur = [], words[0]
    for word in words[1:]:
        test = cur + " " + word
        bb = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] <= max_width:
            cur = test
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return "\n".join(lines)

def fit_font(draw, text, box_w, box_h, font_name, max_pt, min_pt, bold, wrap, dpi):
    pt = float(max_pt)
    while pt >= float(min_pt):
        f = load_font(font_name, pt, bold, dpi)
        txt = wrap_text(draw, text, f, box_w) if wrap else text
        bb = draw.multiline_textbbox((0, 0), txt, font=f, spacing=1)
        if (bb[2]-bb[0]) <= box_w and (bb[3]-bb[1]) <= box_h:
            return f, txt
        pt -= 0.5
    f = load_font(font_name, min_pt, bold, dpi)
    return f, wrap_text(draw, text, f, box_w) if wrap else text

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

def _element_angle(e):
    try:
        return float(e.get("angle", 0) or 0.0)
    except Exception:
        return 0.0

def rotate_point_cw(px, py, cx, cy, angle_deg):
    """Rotate a point clockwise (visually, y-down) around (cx, cy)."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    dx, dy = px - cx, py - cy
    return cx + dx * ca - dy * sa, cy + dx * sa + dy * ca

def element_rotation_center(e):
    t = str(e.get("type", "")).lower()
    if t == "line":
        x1 = float(e.get("x", 0)); y1 = float(e.get("y", 0))
        return ((x1 + float(e.get("x2", x1))) / 2.0, (y1 + float(e.get("y2", y1))) / 2.0)
    x = float(e.get("x", 0)); y = float(e.get("y", 0))
    return (x + float(e.get("w", 0)) / 2.0, y + float(e.get("h", 0)) / 2.0)

def _draw_element(img, draw, e, cfg, dpi):
    t = e.get("type", "").lower()
    x = mm_to_px(e.get("x", 0), dpi)
    y = mm_to_px(e.get("y", 0), dpi)
    w = mm_to_px(e.get("w", cfg["width_mm"] - e.get("x", 0)), dpi)
    h = mm_to_px(e.get("h", cfg["height_mm"] - e.get("y", 0)), dpi)

    if t == "text":
        text = str(e.get("text", ""))
        font_name = e.get("font", "Arial")
        bold = bool(e.get("bold", False))
        size = float(e.get("font_size", 8))
        wrap = bool(e.get("wrap", True))
        align = e.get("align", "left")
        if e.get("auto_fit", False):
            f, final_text = fit_font(draw, text, w, h, font_name, size, e.get("min_font_size", 4), bold, wrap, dpi)
        else:
            f = load_font(font_name, size, bold, dpi)
            final_text = wrap_text(draw, text, f, w) if wrap else text

        bb = draw.multiline_textbbox((0, 0), final_text, font=f, spacing=1)
        tw = bb[2] - bb[0]
        tx = x
        if align == "center":
            tx = x + max(0, (w - tw) // 2)
        elif align == "right":
            tx = x + max(0, w - tw)
        draw.multiline_text((tx, y), final_text, font=f, fill=0, spacing=1, align=align)

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
        bc = make_barcode(
            e.get("value", ""), dpi,
            e.get("symbology", "code128"),
            e.get("barcode_height_mm", max(5, e.get("h", 12)-2)),
            e.get("module_width", 0.25),
            e.get("quiet_zone", 1.0)
        )
        ratio = min(w / bc.width, h / bc.height)
        nw, nh = max(1, int(bc.width * ratio)), max(1, int(bc.height * ratio))
        bc = bc.resize((nw, nh), Image.Resampling.NEAREST)
        img.paste(bc, (x + (w - nw) // 2, y + (h - nh) // 2))


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


def render_label(cfg):
    cfg = scale_layout_cfg(normalize_cfg(cfg))
    dpi = int(cfg["dpi"])
    wpx = mm_to_px(cfg["width_mm"], dpi)
    hpx = mm_to_px(cfg["height_mm"], dpi)

    img = Image.new("L", (wpx, hpx), 255)
    draw = ImageDraw.Draw(img)

    for e in cfg["elements"]:
        if e.get("physical"):
            continue
        angle = _element_angle(e) % 360.0
        if abs(angle) > 0.0001 and abs(angle - 360.0) > 0.0001:
            _draw_element_rotated(img, e, cfg, dpi, angle)
        else:
            _draw_element(img, draw, e, cfg, dpi)

    threshold = int(cfg.get("threshold", 180))
    out = img.point(lambda p: 0 if p < threshold else 255, mode="1")
    out = apply_fold_regions(out, cfg)
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

# ----------------------------
# Printing helpers
# ----------------------------
def image_to_zpl_gfa(img):
    mono = img.convert("1")
    width, height = mono.size
    row_bytes = (width + 7) // 8
    data = bytearray()
    pix = mono.load()
    for y in range(height):
        row = bytearray(row_bytes)
        for x in range(width):
            if pix[x, y] == 0:
                row[x // 8] |= (1 << (7 - (x % 8)))
        data.extend(row)
    total = len(data)
    return f"^GFA,{total},{total},{row_bytes},{data.hex().upper()}"

def build_raw_gzpl(cfg, img):
    copies = max(1, int(cfg.get("copies", 1)))
    return (
        "^XA\r\n"
        "^LH0,0\r\n"
        f"^PW{img.width}\r\n"
        f"^LL{img.height}\r\n"
        "^FO0,0\r\n"
        f"{image_to_zpl_gfa(img)}\r\n"
        "^FS\r\n"
        f"^PQ{copies},0,1,N\r\n"
        "^XZ\r\n"
    ).encode("ascii")

def enum_printers():
    try:
        import win32print
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return [p[2] for p in win32print.EnumPrinters(flags)]
    except Exception:
        return []

def preferred_printer(printers):
    for key in ("G530", "GoDEX", "Godex", "EZ530", "EZ530+"):
        for p in printers:
            if key.lower() in p.lower():
                return p
    return printers[0] if printers else ""

def raw_print(printer_name, raw_bytes):
    import win32print
    h = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(h, 1, ("ECG Label RAW", None, "RAW"))
        try:
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, raw_bytes)
            win32print.EndPagePrinter(h)
        finally:
            win32print.EndDocPrinter(h)
    finally:
        win32print.ClosePrinter(h)

# ----------------------------
# Data binding helpers
# ----------------------------
def format_binding_value(key, v):
    if v is None:
        return ""
    if key.lower() == "price":
        if isinstance(v, (int, float)):
            return f"{int(round(v)):,} VNĐ"
        s = str(v).strip()
        if not s:
            return ""
        compact = s.replace(",", "").replace(".", "").replace(" ", "")
        if compact.isdigit():
            return f"{int(compact):,} VNĐ"
        return s
    if key.lower() == "barcode":
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v).strip()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)

def resolve_row_value(row, column_name):
    """Resolve a source column dynamically. Exact header wins; trimmed/case-insensitive is fallback."""
    if column_name in row:
        return row.get(column_name, "")
    wanted = str(column_name).strip().casefold()
    for k, v in row.items():
        if str(k).strip().casefold() == wanted:
            return v
    return ""

def replace_placeholders(value, row, bindings):
    if not isinstance(value, str):
        return value
    def repl(m):
        key = m.group(1).strip()
        col = bindings.get(key, key)
        return format_binding_value(key, resolve_row_value(row, col))
    return PLACEHOLDER_RE.sub(repl, value)

def bind_row_to_template(template_cfg, row):
    cfg = copy.deepcopy(normalize_cfg(template_cfg))
    bindings = dict(cfg.get("data_bindings", {}))
    for e in cfg["elements"]:
        if "text" in e:
            e["text"] = replace_placeholders(e["text"], row, bindings)
        if "value" in e:
            e["value"] = replace_placeholders(e["value"], row, bindings)
    copies_col = bindings.get("Copies", "Copies")
    if row.get(copies_col) not in (None, ""):
        try:
            cfg["copies"] = max(1, int(float(row[copies_col])))
        except Exception:
            pass
    return cfg

# ----------------------------
# Data loading
# ----------------------------
def extract_google_sheet_id(url_or_id):
    s = str(url_or_id).strip()
    if not s:
        raise ValueError("Google Sheet URL/ID is empty.")
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", s):
        return s
    raise ValueError("Could not detect Google Sheet ID.")

def google_sheet_csv_url(url_or_id, sheet_name=None):
    sid = extract_google_sheet_id(url_or_id)
    url = f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv"
    if sheet_name:
        url += "&sheet=" + urllib.parse.quote(str(sheet_name))
    return url

def make_unique_headers(raw_headers):
    """Keep every source column addressable, including blanks and duplicate names."""
    out = []
    seen = {}
    for i, v in enumerate(raw_headers):
        base = str(v).strip() if v is not None else ""
        if not base:
            base = f"Column_{i+1}"
        key = base.casefold()
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            base = f"{base} ({seen[key]})"
        out.append(base)
    return out

def fetch_google_sheet_rows(url_or_id, sheet_name=None):
    req = urllib.request.Request(
        google_sheet_csv_url(url_or_id, sheet_name),
        headers={"User-Agent": "Mozilla/5.0 ECG-Label-Tool"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
    except Exception as e:
        raise RuntimeError("Cannot read Google Sheet. Share it as 'Anyone with the link - Viewer' or use Excel.\n\n" + str(e))
    rows = list(csv.reader(raw.decode("utf-8-sig", errors="replace").splitlines()))
    if not rows:
        return [], []
    headers = make_unique_headers(rows[0])
    data = []
    for r in rows[1:]:
        if not any(str(v).strip() for v in r):
            continue
        row = {}
        for i, h in enumerate(headers):
            row[h] = r[i] if i < len(r) else ""
        data.append(row)
    return headers, data

def normalize_search_text(v):
    return "" if v is None else str(v).strip().lower()


def infer_calibration_regions(cfg):
    """Return friendly face regions for the two included ECG tag families."""
    cfg = normalize_cfg(cfg)
    w = float(cfg.get("width_mm", 0))
    h = float(cfg.get("height_mm", 0))

    # 56x85 liner with 36x44 body, split into two 36x22 faces.
    if abs(w - 56) < 1.5 and abs(h - 85) < 2:
        return {
            "Top face": {"x": 10, "y": 41, "w": 36, "h": 22, "rotated": False},
            "Bottom face": {"x": 10, "y": 63, "w": 36, "h": 22, "rotated": True},
        }

    # 50x68 H-tag: front 25 + connector 18 + back 25.
    if abs(w - 50) < 1.5 and abs(h - 68) < 2:
        return {
            "Top face": {"x": 0, "y": 0, "w": 50, "h": 25, "rotated": False},
            "Bottom face": {"x": 0, "y": 43, "w": 50, "h": 25, "rotated": True},
        }

    # Generic fallback: use first 180-degree fold region as bottom face,
    # and the remaining area immediately above it as top face.
    folds = [r for r in cfg.get("fold_regions", []) if r.get("enabled", True) and int(r.get("angle",180)) % 360 == 180]
    if folds:
        fr = folds[0]
        bh = float(fr.get("h", h/2))
        return {
            "Top face": {
                "x": float(fr.get("x", 0)),
                "y": max(0.0, float(fr.get("y", 0)) - bh),
                "w": float(fr.get("w", w)),
                "h": bh,
                "rotated": False
            },
            "Bottom face": {
                "x": float(fr.get("x", 0)),
                "y": float(fr.get("y", 0)),
                "w": float(fr.get("w", w)),
                "h": bh,
                "rotated": True
            }
        }

    return {
        "Top face": {"x": 0, "y": 0, "w": w, "h": h/2, "rotated": False},
        "Bottom face": {"x": 0, "y": h/2, "w": w, "h": h/2, "rotated": False},
    }

def element_center_mm(e):
    t = str(e.get("type","")).lower()
    if t == "line":
        x1 = float(e.get("x",0)); y1 = float(e.get("y",0))
        x2 = float(e.get("x2",x1)); y2 = float(e.get("y2",y1))
        return ((x1+x2)/2, (y1+y2)/2)
    x = float(e.get("x",0)); y = float(e.get("y",0))
    w = float(e.get("w",0)); h = float(e.get("h",0))
    return (x+w/2, y+h/2)

def point_in_region(x, y, r):
    return (
        x >= float(r["x"]) and
        x <= float(r["x"]) + float(r["w"]) and
        y >= float(r["y"]) and
        y <= float(r["y"]) + float(r["h"])
    )

def shift_element(e, dx, dy):
    e["x"] = round(float(e.get("x",0)) + dx, 3)
    e["y"] = round(float(e.get("y",0)) + dy, 3)
    if "x2" in e:
        e["x2"] = round(float(e.get("x2",0)) + dx, 3)
    if "y2" in e:
        e["y2"] = round(float(e.get("y2",0)) + dy, 3)



def app_data_dir():
    p = os.path.join(os.path.dirname(__file__), "history")
    os.makedirs(p, exist_ok=True)
    return p

def create_session_dir():
    now = datetime.datetime.now()
    p = os.path.join(app_data_dir(), now.strftime("%Y-%m-%d"), "session_" + now.strftime("%H%M%S"))
    os.makedirs(p, exist_ok=True)
    return p

def safe_filename(s):
    s = re.sub(r'[<>:"/\\|?*]+', "_", str(s or "").strip())
    s = re.sub(r"\s+", "_", s)
    return s[:80] or "label"

def printer_info(printer_name):
    import win32print
    h = win32print.OpenPrinter(printer_name)
    try:
        info = win32print.GetPrinter(h, 2)
        dm = info.get("pDevMode")
        out = {
            "name": printer_name,
            "driver": info.get("pDriverName", ""),
            "port": info.get("pPortName", ""),
            "status": info.get("Status", 0),
            "paper_width_mm": None,
            "paper_length_mm": None,
            "orientation": None,
            "print_quality": None,
        }
        if dm:
            try:
                pw = getattr(dm, "PaperWidth", 0)
                pl = getattr(dm, "PaperLength", 0)
                if pw: out["paper_width_mm"] = round(float(pw)/10.0, 2)
                if pl: out["paper_length_mm"] = round(float(pl)/10.0, 2)
                ori = getattr(dm, "Orientation", 0)
                out["orientation"] = "portrait" if ori == 1 else ("landscape" if ori == 2 else None)
                out["print_quality"] = getattr(dm, "PrintQuality", None)
            except Exception:
                pass
        return out
    finally:
        win32print.ClosePrinter(h)

def status_text(status):
    if status == 0:
        return "Ready / no Windows error reported"
    pairs = [
        (0x1,"Paused"), (0x2,"Error"), (0x8,"Paper jam"), (0x10,"Paper out"),
        (0x40,"Paper problem"), (0x80,"Offline"), (0x200,"Busy"),
        (0x400,"Printing"), (0x400000,"User intervention")
    ]
    names = [n for b,n in pairs if status & b]
    return ", ".join(names) if names else f"Windows status code: {status}"



def app_data_dir():
    """Persistent user data that survives replacing/updating the application folder."""
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".ecg_label_tool")
    path = os.path.join(base, "ECG_Label_Tool")
    os.makedirs(path, exist_ok=True)
    return path

def persistent_template_dir():
    path = os.path.join(app_data_dir(), "templates")
    os.makedirs(path, exist_ok=True)
    return path

def bundled_template_dir():
    return os.path.join(os.path.dirname(__file__), "templates")

def ensure_persistent_library():
    """Seed bundled templates/profile into persistent storage without overwriting user files."""
    td = persistent_template_dir()
    src = bundled_template_dir()
    if os.path.isdir(src):
        for name in os.listdir(src):
            if not name.lower().endswith(".json"):
                continue
            sp = os.path.join(src, name)
            dp = os.path.join(td, name)
            if not os.path.exists(dp):
                try:
                    import shutil
                    shutil.copy2(sp, dp)
                except Exception:
                    pass
    # Migrate a legacy profile file from an older portable app folder if present.
    legacy = os.path.join(os.path.dirname(__file__), "printer_profiles.json")
    target = os.path.join(app_data_dir(), "printer_profiles.json")
    if os.path.exists(legacy) and not os.path.exists(target):
        try:
            import shutil
            shutil.copy2(legacy, target)
        except Exception:
            pass
    return td

def profiles_path():
    ensure_persistent_library()
    return os.path.join(app_data_dir(), "printer_profiles.json")

def load_profiles():
    p = profiles_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_profiles(data):
    with open(profiles_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def workspace_path():
    return os.path.join(app_data_dir(), "workspace_v20.json")

def working_copy_path():
    return os.path.join(app_data_dir(), "active_working_template.json")

def load_workspace_state():
    p = workspace_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_workspace_state(data):
    try:
        with open(workspace_path(), "w", encoding="utf-8") as f:
            json.dump(data or {}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def sources_path():
    return os.path.join(app_data_dir(), "data_sources.json")

def load_sources():
    """Saved Google Sheets + recent Excel files. Lives in the persistent app-data folder."""
    base = {"sheets": [], "excel": []}
    try:
        with open(sources_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            base["sheets"] = [x for x in data.get("sheets", []) if isinstance(x, dict) and x.get("url")]
            base["excel"] = [x for x in data.get("excel", []) if isinstance(x, str)]
    except Exception:
        pass
    return base

def save_sources(data):
    try:
        with open(sources_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _sheet_key(url):
    try:
        return extract_google_sheet_id(url)
    except Exception:
        return str(url).strip()

def default_sheet_name(url, tab):
    sid = _sheet_key(url)
    return f"{tab or 'Sheet'} · …{str(sid)[-6:]}"

def remember_google_source(url, tab, name=None):
    """Insert/refresh a saved sheet (keyed by sheet id + tab), most recently used first."""
    data = load_sources()
    sid = _sheet_key(url)
    keep = []
    old_name = None
    for it in data["sheets"]:
        if _sheet_key(it["url"]) == sid and (it.get("tab") or "") == (tab or ""):
            old_name = it.get("name")
        else:
            keep.append(it)
    entry = {"name": (name or old_name or default_sheet_name(url, tab)), "url": url, "tab": tab or "",
             "last_used": datetime.datetime.now().isoformat(timespec="seconds")}
    data["sheets"] = [entry] + keep
    save_sources(data)
    return entry

def remember_excel_source(path):
    data = load_sources()
    data["excel"] = [path] + [p for p in data["excel"] if p != path][:11]
    save_sources(data)

def backup_template_file(path, keep=5):
    if not path or not os.path.exists(path):
        return
    try:
        import shutil
        stem = os.path.splitext(os.path.basename(path))[0]
        bdir = os.path.join(app_data_dir(), "template_backups", stem)
        os.makedirs(bdir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        shutil.copy2(path, os.path.join(bdir, stamp + ".json"))
        files = sorted([os.path.join(bdir,n) for n in os.listdir(bdir) if n.lower().endswith('.json')], reverse=True)
        for old in files[int(keep):]:
            try: os.remove(old)
            except Exception: pass
    except Exception:
        pass

def preflight_checks(cfg):
    """
    Conservative validation. It does not change data or Google Sheets behavior.
    Returns (errors, warnings).
    """
    cfg = normalize_cfg(cfg)
    errors = []
    warnings = []

    w = float(cfg.get("width_mm", 0))
    h = float(cfg.get("height_mm", 0))
    dpi = int(cfg.get("dpi", 0))

    if w <= 0 or h <= 0:
        errors.append("Paper width/height must be greater than 0.")
    if dpi <= 0:
        errors.append("DPI must be greater than 0.")

    unresolved = []
    for i, e in enumerate(cfg.get("elements", []), start=1):
        for key in ("text", "value"):
            v = e.get(key)
            if isinstance(v, str) and "{{" in v and "}}" in v:
                unresolved.append(f"Element {i}: unresolved placeholder in {key}.")
    if unresolved:
        warnings.extend(unresolved[:8])
        if len(unresolved) > 8:
            warnings.append(f"...and {len(unresolved)-8} more unresolved placeholder(s).")

    # Element boundary checks in template coordinates.
    for i, e in enumerate(cfg.get("elements", []), start=1):
        t = str(e.get("type", "")).lower()
        try:
            x = float(e.get("x", 0))
            y = float(e.get("y", 0))
            if t == "line":
                x2 = float(e.get("x2", x))
                y2 = float(e.get("y2", y))
                if min(x, x2) < -0.5 or min(y, y2) < -0.5 or max(x, x2) > w + 0.5 or max(y, y2) > h + 0.5:
                    warnings.append(f"Element {i} line extends outside paper.")
            else:
                ew = float(e.get("w", 0))
                eh = float(e.get("h", 0))
                if x < -0.5 or y < -0.5 or (x + ew) > w + 0.5 or (y + eh) > h + 0.5:
                    warnings.append(f"Element {i} ({t}) extends outside paper.")
        except Exception:
            warnings.append(f"Element {i}: invalid numeric coordinates.")

        if t == "barcode":
            val = str(e.get("value", "")).strip()
            if not val:
                errors.append(f"Element {i}: barcode is blank.")
            try:
                mw = float(e.get("module_width", 0.25))
                if mw < 0.18:
                    warnings.append(f"Element {i}: barcode module_width {mw:g} mm may be too narrow.")
            except Exception:
                pass

    area = cfg.get("virtual_print_area") or {}
    if area.get("show", True):
        try:
            aw=float(area.get("w",0)); ah=float(area.get("h",0))
            if aw <= 0 or ah <= 0:
                errors.append("Virtual print area width/height must be greater than 0.")
        except Exception:
            errors.append("Virtual print area contains invalid numeric values.")

    if abs(float(cfg.get("rotation_deg", 0))) > 3:
        warnings.append("Skew compensation exceeds 3°. Check physical media alignment.")

    return errors, warnings

def make_calibration_test_cfg(base_cfg):
    """Calibration grid constrained to the configured printable area when enabled."""
    cfg = normalize_cfg(copy.deepcopy(base_cfg))
    pw = float(cfg["width_mm"]); ph = float(cfg["height_mm"])
    area = cfg.get("virtual_print_area") or {}
    if area.get("show", True):
        ox=float(area.get("x",0)); oy=float(area.get("y",0)); w=float(area.get("w",pw)); h=float(area.get("h",ph))
    else:
        ox=0.0; oy=0.0; w=pw; h=ph
    cfg["elements"] = []
    cfg["data_bindings"] = {}
    cfg["fold_regions"] = []
    inset=0.5
    cfg["elements"].append({"type":"box","x":ox+inset,"y":oy+inset,"w":max(0.1,w-2*inset),"h":max(0.1,h-2*inset),"thickness":0.2})
    step=5.0
    x=ox+step
    while x < ox+w:
        cfg["elements"].append({"type":"line","x":x,"y":oy+inset,"x2":x,"y2":oy+h-inset,"thickness":0.08}); x += step
    y=oy+step
    while y < oy+h:
        cfg["elements"].append({"type":"line","x":ox+inset,"y":y,"x2":ox+w-inset,"y2":y,"thickness":0.08}); y += step
    cfg["elements"].append({"type":"line","x":ox+w/2,"y":oy+inset,"x2":ox+w/2,"y2":oy+h-inset,"thickness":0.25})
    cfg["elements"].append({"type":"line","x":ox+inset,"y":oy+h/2,"x2":ox+w-inset,"y2":oy+h/2,"thickness":0.25})
    cfg["elements"].append({"type":"text","text":f"CAL {w:g}x{h:g}mm","x":ox+1.5,"y":oy+1.5,"w":max(8,w-3),"h":4,"font":"Tahoma","font_size":5.5,"bold":True,"align":"left","wrap":False,"auto_fit":True,"min_font_size":3.5})
    cfg["elements"].append({"type":"text","text":f"Offset X {cfg.get('offset_x_mm',0):g} / Y {cfg.get('offset_y_mm',0):g} / Skew {cfg.get('rotation_deg',0):g}°","x":ox+1.5,"y":max(oy+5,oy+h-4.5),"w":max(8,w-3),"h":3,"font":"Verdana","font_size":3.5,"bold":False,"align":"left","wrap":False,"auto_fit":True,"min_font_size":2.8})
    cfg["copies"] = 1
    return cfg


def make_text_quality_test_cfg(base_cfg):
    cfg = normalize_cfg(copy.deepcopy(base_cfg))
    pw=float(cfg["width_mm"]); ph=float(cfg["height_mm"]); area=cfg.get("virtual_print_area") or {}
    if area.get("show",True): ox=float(area.get("x",0)); oy=float(area.get("y",0)); w=float(area.get("w",pw)); h=float(area.get("h",ph))
    else: ox=0.0; oy=0.0; w=pw; h=ph
    cfg["copies"]=1; cfg["fold_regions"]=[]; cfg["data_bindings"]={}; cfg["elements"]=[]
    left=ox+1.5; top=oy+1.5
    cfg["elements"].append({"type":"text","text":"ECG TEXT QUALITY","x":left,"y":top,"w":max(8,w-3),"h":4,"font":"Tahoma","font_size":7.0,"bold":True,"align":"left","wrap":False,"auto_fit":True,"min_font_size":5.0})
    y=top+5.0
    samples=[("Verdana",3.0,False),("Verdana",3.5,False),("Verdana",4.0,False),("Tahoma",4.0,False),("Tahoma",4.5,True),("Tahoma",5.5,True)]
    for font,size,bold in samples:
        if y+3.2 > oy+h-1: break
        cfg["elements"].append({"type":"text","text":f"{font} {size:g}pt  Tiếng Việt: NHÀ NHẬP KHẨU  8,800,000 VNĐ","x":left,"y":y,"w":max(8,w-3),"h":3.0,"font":font,"font_size":size,"bold":bold,"align":"left","wrap":False,"auto_fit":True,"min_font_size":max(2.8,size-0.8)})
        y += 3.4
    return cfg


def make_barcode_quality_test_cfg(base_cfg):
    cfg=normalize_cfg(copy.deepcopy(base_cfg))
    pw=float(cfg["width_mm"]); ph=float(cfg["height_mm"]); area=cfg.get("virtual_print_area") or {}
    if area.get("show",True): ox=float(area.get("x",0)); oy=float(area.get("y",0)); w=float(area.get("w",pw)); h=float(area.get("h",ph))
    else: ox=0.0; oy=0.0; w=pw; h=ph
    cfg["copies"]=1; cfg["fold_regions"]=[]; cfg["data_bindings"]={}; cfg["elements"]=[]
    cfg["elements"].append({"type":"text","text":"ECG BARCODE QUALITY","x":ox+1.5,"y":oy+1.5,"w":max(8,w-3),"h":4,"font":"Tahoma","font_size":6.5,"bold":True,"align":"left","wrap":False,"auto_fit":True,"min_font_size":4.5})
    dpi=max(1,int(cfg.get("dpi",300))); y=oy+6.0; value="889214705891"
    for dots in (2,3,4):
        if y+10.8 > oy+h-0.5: break
        mw=dots*25.4/dpi
        cfg["elements"].append({"type":"text","text":f"Code128 {dots} dots/module ({mw:.3f} mm)","x":ox+1.5,"y":y,"w":max(8,w-3),"h":2.5,"font":"Verdana","font_size":3.4,"bold":False,"align":"left","wrap":False,"auto_fit":True,"min_font_size":2.8})
        cfg["elements"].append({"type":"barcode","value":value,"x":ox+1.5,"y":y+2.3,"w":max(8,w-3),"h":5.8,"symbology":"code128","barcode_height_mm":5.4,"module_width":mw,"quiet_zone":1.0,"show_text":False})
        cfg["elements"].append({"type":"text","text":value,"x":ox+1.5,"y":y+8.2,"w":max(8,w-3),"h":2.0,"font":"Verdana","font_size":3.0,"bold":False,"align":"center","wrap":False})
        y += 10.5
    return cfg


def _ruler_elements(w, h, label_every=10, font="Arial"):
    """Millimetre rulers along all four paper edges (physical elements: never folded)."""
    els = []
    def line(x1, y1, x2, y2, t=0.1):
        els.append({"type": "line", "x": round(x1, 3), "y": round(y1, 3), "x2": round(x2, 3), "y2": round(y2, 3), "thickness": t, "physical": True})
    def label(txt, x, y, align="center"):
        els.append({"type": "text", "text": str(txt), "x": round(x, 3), "y": round(y, 3), "w": 6.0, "h": 2.2, "font": font,
                    "font_size": 3.2, "bold": False, "align": align, "wrap": False, "physical": True})
    mm = 0
    while mm <= w + 1e-6:
        big = mm % label_every == 0; mid = mm % 5 == 0
        ln = 3.0 if big else (2.0 if mid else 1.0); t = 0.16 if big else 0.1
        line(mm, 0, mm, ln, t); line(mm, h, mm, h - ln, t)
        if big and 0 < mm < w - 3: label(mm, mm - 3.0, ln + 0.2)
        mm += 1
    mm = 0
    while mm <= h + 1e-6:
        big = mm % label_every == 0; mid = mm % 5 == 0
        ln = 3.0 if big else (2.0 if mid else 1.0); t = 0.16 if big else 0.1
        line(0, mm, ln, mm, t); line(w, mm, w - ln, mm, t)
        if big and 0 < mm < h - 3: label(mm, ln + 0.4, mm - 1.1, "left")
        mm += 1
    return els


def make_ruler_overlay_cfg(base_cfg, grid_every=10):
    """Current label + mm rulers + faint 10 mm crosshair marks, to compare screen vs. real print."""
    cfg = normalize_cfg(copy.deepcopy(base_cfg))
    w = float(cfg["width_mm"]); h = float(cfg["height_mm"])
    els = _ruler_elements(w, h)
    gx = grid_every
    while gx < w:
        gy = grid_every
        while gy < h:
            els.append({"type": "line", "x": gx - 0.8, "y": gy, "x2": gx + 0.8, "y2": gy, "thickness": 0.08, "physical": True})
            els.append({"type": "line", "x": gx, "y": gy - 0.8, "x2": gx, "y2": gy + 0.8, "thickness": 0.08, "physical": True})
            gy += grid_every
        gx += grid_every
    cfg["elements"] = list(cfg.get("elements", [])) + els
    cfg["copies"] = 1
    return cfg


def compare_sheet_geometry(base_cfg):
    """Nominal numbers of the compare sheet. Shared by the printout and the Measure dialog."""
    w = float(base_cfg.get("width_mm", 50)); h = float(base_cfg.get("height_mm", 68))
    inset = 2.0
    return {"w": w, "h": h, "inset": inset, "ref_x": round(w - 2 * inset, 3), "ref_y": round(h - 2 * inset, 3)}


def make_compare_sheet_cfg(base_cfg, compensated=False):
    """Printer-vs-app comparison sheet.

    Raw mode ignores offset / skew / size compensation so the printer's real error can be measured.
    Compensated mode keeps them so the correction can be verified afterwards.
    """
    cfg = normalize_cfg(copy.deepcopy(base_cfg))
    if not compensated:
        cfg["offset_x_mm"] = 0.0; cfg["offset_y_mm"] = 0.0; cfg["rotation_deg"] = 0.0
        cfg["scale_x_pct"] = 100.0; cfg["scale_y_pct"] = 100.0
    g = compare_sheet_geometry(cfg); w, h, inset = g["w"], g["h"], g["inset"]
    cfg["fold_regions"] = []; cfg["data_bindings"] = {}; cfg["copies"] = 1
    els = _ruler_elements(w, h)
    def line(x1, y1, x2, y2, t=0.2):
        els.append({"type": "line", "x": x1, "y": y1, "x2": x2, "y2": y2, "thickness": t, "physical": True})
    def text(txt, x, y, tw, th=2.6, size=4.0, bold=False, align="left"):
        els.append({"type": "text", "text": txt, "x": x, "y": y, "w": tw, "h": th, "font": "Arial", "font_size": size,
                    "bold": bold, "align": align, "wrap": False, "physical": True})
    # frame
    els.append({"type": "box", "x": inset, "y": inset, "w": w - 2 * inset, "h": h - 2 * inset, "thickness": 0.25, "physical": True})
    cx = w / 2.0; cy = h / 2.0
    # horizontal / vertical reference lines with end caps
    line(inset, cy, w - inset, cy, 0.25); line(inset, cy - 1.5, inset, cy + 1.5); line(w - inset, cy - 1.5, w - inset, cy + 1.5)
    line(cx, inset, cx, h - inset, 0.25); line(cx - 1.5, inset, cx + 1.5, inset); line(cx - 1.5, h - inset, cx + 1.5, h - inset)
    text(f"X ref = {g['ref_x']:g} mm", inset + 2, cy + 1.2, w - 2 * inset - 4, size=4.0, bold=True)
    text(f"Y ref = {g['ref_y']:g} mm", cx + 1.5, inset + 8, 22, size=4.0, bold=True)
    # 10 mm reference square
    sq = min(10.0, (w - 2 * inset) / 4, (h - 2 * inset) / 4)
    els.append({"type": "box", "x": inset + 3, "y": inset + 8, "w": sq, "h": sq, "thickness": 0.2, "physical": True})
    text(f"{sq:g}mm", inset + 3, inset + 8 + sq + 0.6, sq + 4, size=3.4)
    # corner marks
    for name, (px, py) in {"TL": (inset, inset), "TR": (w - inset, inset), "BL": (inset, h - inset), "BR": (w - inset, h - inset)}.items():
        line(px - 2, py, px + 2, py, 0.15); line(px, py - 2, px, py + 2, 0.15)
    # text + barcode samples
    sy = min(h - inset - 24, cy + 5)
    if sy > cy + 4:
        text("Text 8pt: ECG Label 0123456789", inset + 2, sy, w - 2 * inset - 4, size=8.0)
        text("Text 5pt: ECG Label 0123456789", inset + 2, sy + 3.6, w - 2 * inset - 4, size=5.0)
        els.append({"type": "barcode", "value": "1234567890", "x": inset + 2, "y": sy + 7.2, "w": min(30.0, w - 2 * inset - 4), "h": 8.0,
                    "symbology": "code128", "barcode_height_mm": 7.0, "module_width": 0.25, "quiet_zone": 1.0, "physical": True})
    mode = "WITH compensation" if compensated else "RAW (no compensation)"
    text(f"COMPARE {w:g}x{h:g}mm  {mode}", inset + 1, inset + 4.0, w - 2 * inset - 2, th=2.4, size=3.4, bold=True)
    cfg["elements"] = els
    return cfg


def _pdf_font_name(name="Arial", bold=False):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    reg_name = "ECG_" + re.sub(r"[^A-Za-z0-9_]+", "_", str(name or "Arial"))
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

def save_exact_print_pdf(cfg, path):
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
            if value:
                sym = str(e.get("symbology", "code128")).lower()
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
                    # but Code128 (the ECG templates) remains vector.
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

        c.restoreState()

    if clip_active:
        c.restoreState()

    c.showPage()
    c.save()

    # Return direct RAW raster only for optional comparison/reporting.
    return render_label(cfg_original)

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
    fd, path = tempfile.mkstemp(prefix="ecg_hq_", suffix=".pdf", dir=temp_dir)
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


def print_pdf_via_windows_driver(pdf_path, printer_name):
    """
    Ask the installed Windows PDF handler to print the VECTOR PDF to a chosen
    Windows printer using the shell 'printto' verb. This is the correct route
    for virtual printers; sending ZPL RAW to a PDF/XPS printer is not.

    The selected PDF application/driver owns the final print dialog and may show
    a Save As prompt (e.g. Microsoft Print to PDF).
    """
    import win32api
    params = f'"{printer_name}"'
    result = win32api.ShellExecute(0, "printto", pdf_path, params, os.path.dirname(pdf_path) or ".", 1)
    if int(result) <= 32:
        raise RuntimeError(
            f"Windows PDF print handler returned error code {result}. "
            "Open the PDF Proof and print manually to this printer if its PDF app does not support PrintTo."
        )
    return result


def normalize_barcode_value(v):
    """Normalize scanner/data barcode values without guessing their length."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).strip()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    # Scanner control characters / whitespace never belong to ECG UPC/EAN keys.
    s = re.sub(r"[\x00-\x20\x7f]+", "", s)
    return s


def detect_barcode_columns(headers):
    preferred = ["Barcode", "UPC/EAN", "UPC", "EAN", "EAN/UPC", "GTIN"]
    by_lower = {str(h).strip().lower(): h for h in headers}
    found = []
    for p in preferred:
        h = by_lower.get(p.lower())
        if h is not None and h not in found:
            found.append(h)
    for h in headers:
        low = str(h).strip().lower()
        if h not in found and any(k in low for k in ("barcode", "upc", "ean", "gtin")):
            found.append(h)
    return found


def build_barcode_lookup(headers, rows):
    columns = detect_barcode_columns(headers)
    lookup = {}
    row_primary = {}
    for i, row in enumerate(rows):
        seen = set()
        for col in columns:
            code = normalize_barcode_value(row.get(col, ""))
            if not code or code in seen:
                continue
            seen.add(code)
            lookup.setdefault(code, []).append(i)
            row_primary.setdefault(i, code)
    # Deduplicate row ids while preserving order.
    for code, ids in list(lookup.items()):
        lookup[code] = list(dict.fromkeys(ids))
    return columns, lookup, row_primary


def segment_concatenated_codes(raw, known_codes, max_solutions=2):
    """
    Split a glued scanner string ONLY by barcodes that exist in the loaded data.
    Returns (status, sequence):
      exact/unique -> list[str]
      ambiguous/not_found -> []
    It stops after max_solutions to avoid expensive ambiguity expansion.
    """
    s = normalize_barcode_value(raw)
    if not s:
        return "not_found", []
    if s in known_codes:
        return "exact", [s]

    lengths = sorted({len(c) for c in known_codes if c}, reverse=True)
    if not lengths:
        return "not_found", []

    # Practical guard against accidental huge clipboard contents.
    if len(s) > 1000:
        return "not_found", []

    memo = {}
    def solve(pos):
        if pos == len(s):
            return [[]]
        if pos in memo:
            return memo[pos]
        solutions = []
        for L in lengths:
            end = pos + L
            if end > len(s):
                continue
            part = s[pos:end]
            if part not in known_codes:
                continue
            for tail in solve(end):
                solutions.append([part] + tail)
                if len(solutions) >= max_solutions:
                    memo[pos] = solutions
                    return solutions
        memo[pos] = solutions
        return solutions

    sols = solve(0)
    # Remove duplicate sequences if equivalent paths occurred.
    unique = []
    seen = set()
    for seq in sols:
        k = tuple(seq)
        if k not in seen:
            seen.add(k)
            unique.append(seq)
        if len(unique) >= max_solutions:
            break

    if len(unique) == 1:
        return "unique", unique[0]
    if len(unique) > 1:
        return "ambiguous", []
    return "not_found", []

# ----------------------------
# UI dialogs
# ----------------------------

class VisualDesignerDialog(tk.Toplevel):
    """v20 visual designer.

    Designer edits are LIVE: every committed edit is pushed to the main JSON immediately,
    so Preview/Test Print/Print Current use the same active layout even before it is saved.
    Saving only persists the active layout to the template library.
    """
    PREVIEW_MARGIN = 36
    HANDLE = 6

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("ECG Label Designer v20.2 — Dynamic Fields")
        self.geometry("1440x900")
        self.minsize(1120, 700)
        self.cfg = copy.deepcopy(app.get_template_cfg())
        self.render_scale = 2
        self.tk_preview = None
        self.preview_source = None
        self.preview_ratio = 1.0
        self.preview_offset_x = 0
        self.preview_offset_y = 0
        self.workspace_min_x = 0.0
        self.workspace_min_y = 0.0

        self.selected_indices = set()
        self.primary_idx = None
        self.overlay_boxes = {}
        self.overlay_polys = {}
        self.rotate_center = (0, 0)
        self.element_handles = {}
        self.virtual_handles = {}
        self.virtual_border = None
        self.fold_overlay = None
        self.mode = None
        self.drag_start = None
        self.drag_before = None
        self.drag_original = None
        self.drag_role = None
        self.selection_rect = None
        self.marquee_start = None
        self.dirty = False
        self.undo_stack = []
        self.redo_stack = []
        self.snap_mm = tk.DoubleVar(value=float(getattr(app, 'workspace_state', {}).get('designer_step', 0.1) or 0.1))
        z = int(getattr(app, 'workspace_state', {}).get('designer_zoom', 200) or 200)
        self.zoom_percent = tk.IntVar(value=max(50,min(600,z)))
        self.zoom_text = tk.StringVar(value=f"{self.zoom_percent.get()}%")
        self.font_step = tk.DoubleVar(value=0.2)

        topbar = ttk.Frame(self, padding=(10, 8, 10, 0))
        topbar.pack(fill="x")
        self.live_label = ttk.Label(topbar, text="LIVE SYNC ON — Print uses this layout immediately", foreground="#16703a")
        self.live_label.pack(side="left")
        ttk.Button(topbar, text="Undo", command=self.undo).pack(side="left", padx=(14,2))
        ttk.Button(topbar, text="Redo", command=self.redo).pack(side="left", padx=2)
        ttk.Button(topbar, text="Test Print", command=self.test_print).pack(side="left", padx=(10,2))
        self.save_btn = ttk.Button(topbar, text="Save Template", command=self.save_json_now)
        self.save_btn.pack(side="right", padx=(5,0))
        ttk.Button(topbar, text="Save As...", command=self.save_as).pack(side="right", padx=3)
        ttk.Button(topbar, text="Load Template...", command=self.load_template_from_designer).pack(side="right", padx=3)

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(main, width=390)
        right = ttk.Frame(main)
        main.add(left, weight=1)
        main.add(right, weight=4)

        # -------- element panel --------
        hdr = ttk.Frame(left); hdr.pack(fill="x")
        ttk.Label(hdr, text="Elements").pack(side="left")
        self.selection_label = ttk.Label(hdr, text="")
        self.selection_label.pack(side="right")
        self.listbox = tk.Listbox(left, exportselection=False, selectmode="extended", height=6)
        self.listbox.pack(fill="both", expand=True, pady=(4,5))
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

        addbar = ttk.Frame(left); addbar.pack(fill="x", pady=(0,4))
        ttk.Button(addbar, text="+ Text", command=self.add_text).pack(side="left", padx=(0,2))
        ttk.Button(addbar, text="+ Field", command=self.add_field).pack(side="left", padx=2)
        shapes = ttk.Menubutton(addbar, text="+ Shape ▾")
        sm = tk.Menu(shapes, tearoff=False)
        sm.add_command(label="Line", command=lambda:self.add_shape('line'))
        sm.add_command(label="Rectangle", command=lambda:self.add_shape('box'))
        sm.add_command(label="Filled Rectangle", command=lambda:self.add_shape('fill_box'))
        sm.add_command(label="Ellipse", command=lambda:self.add_shape('ellipse'))
        shapes['menu']=sm; shapes.pack(side="left", padx=2)
        ttk.Button(addbar, text="Duplicate", command=self.duplicate_selected).pack(side="left", padx=2)
        ttk.Button(addbar, text="Delete", command=self.delete_selected).pack(side="left", padx=2)

        lockbar = ttk.Frame(left); lockbar.pack(fill="x", pady=(0,6))
        ttk.Button(lockbar, text="Lock", command=lambda:self.set_lock_selected(True)).pack(side="left", padx=(0,2))
        ttk.Button(lockbar, text="Unlock", command=lambda:self.set_lock_selected(False)).pack(side="left", padx=2)
        ttk.Button(lockbar, text="Unlock All", command=self.unlock_all).pack(side="left", padx=2)
        ttk.Button(lockbar, text="↑", width=3, command=lambda:self.reorder(-1)).pack(side="right", padx=1)
        ttk.Button(lockbar, text="↓", width=3, command=lambda:self.reorder(1)).pack(side="right", padx=1)

        alignbar = ttk.Frame(left); alignbar.pack(fill="x", pady=(0,7))
        ttk.Label(alignbar, text="Align").pack(side="left", padx=(0,4))
        ttk.Button(alignbar, text="Left", command=lambda:self.align_selected('left')).pack(side="left", padx=1)
        ttk.Button(alignbar, text="Top", command=lambda:self.align_selected('top')).pack(side="left", padx=1)
        ttk.Button(alignbar, text="H Center", command=lambda:self.align_selected('hcenter')).pack(side="left", padx=1)
        ttk.Button(alignbar, text="V Center", command=lambda:self.align_selected('vcenter')).pack(side="left", padx=1)

        form = ttk.LabelFrame(left, text="Selected element", padding=8)
        form.pack(fill="x")
        self.vars = {k:tk.StringVar() for k in ('x','y','w','h','font_size','text','value','angle')}
        row=0
        ttk.Label(form,text="Type").grid(row=row,column=0,sticky="w",pady=3)
        self.type_label=ttk.Label(form,text="")
        self.type_label.grid(row=row,column=1,columnspan=3,sticky="w",pady=3); row+=1
        for key,label in [('x','X (mm)'),('y','Y (mm)'),('w','Width (mm)'),('h','Height (mm)')]:
            ttk.Label(form,text=label).grid(row=row,column=0,sticky="w",pady=3)
            e=ttk.Entry(form,textvariable=self.vars[key],width=20); e.grid(row=row,column=1,columnspan=3,sticky="ew",pady=3)
            e.bind('<Return>',lambda ev:self.apply_selected()); row+=1
        ttk.Label(form,text="Font size").grid(row=row,column=0,sticky="w",pady=3)
        ttk.Button(form,text="−",width=3,command=lambda:self.change_font_size(-1)).grid(row=row,column=1,padx=(0,2))
        e=ttk.Entry(form,textvariable=self.vars['font_size'],width=10); e.grid(row=row,column=2,sticky="ew",pady=3)
        e.bind('<Return>',lambda ev:self.apply_selected())
        ttk.Button(form,text="+",width=3,command=lambda:self.change_font_size(1)).grid(row=row,column=3,padx=(2,0)); row+=1
        ttk.Label(form,text="Angle (°)").grid(row=row,column=0,sticky="w",pady=3)
        e=ttk.Entry(form,textvariable=self.vars['angle'],width=10); e.grid(row=row,column=1,columnspan=3,sticky="ew",pady=3)
        e.bind('<Return>',lambda ev:self.apply_selected()); row+=1
        rotbar=ttk.Frame(form); rotbar.grid(row=row,column=0,columnspan=4,sticky="ew",pady=(0,3))
        for lbl,d in (("↺90",-90),("↺15",-15),("↺1",-1),("↻1",1),("↻15",15),("↻90",90)):
            ttk.Button(rotbar,text=lbl,width=4,command=lambda d=d:self.rotate_selected(d)).pack(side="left",padx=1)
        ttk.Button(rotbar,text="0°",width=3,command=lambda:self.rotate_selected(None)).pack(side="left",padx=(4,1)); row+=1
        ttk.Label(form,text="Text").grid(row=row,column=0,sticky="w",pady=3)
        e=ttk.Entry(form,textvariable=self.vars['text']); e.grid(row=row,column=1,columnspan=3,sticky="ew",pady=3)
        e.bind('<Return>',lambda ev:self.apply_selected()); row+=1
        ttk.Label(form,text="Barcode value").grid(row=row,column=0,sticky="w",pady=3)
        e=ttk.Entry(form,textvariable=self.vars['value']); e.grid(row=row,column=1,columnspan=3,sticky="ew",pady=3)
        e.bind('<Return>',lambda ev:self.apply_selected()); row+=1
        ttk.Button(form,text="Apply values",command=self.apply_selected).grid(row=row,column=0,columnspan=4,sticky="ew",pady=(6,2))
        form.columnconfigure(2,weight=1)

        fine=ttk.LabelFrame(left,text="Fine move",padding=8); fine.pack(fill="x",pady=(8,0))
        ttk.Label(fine,text="Step (mm)").grid(row=0,column=0,sticky="w")
        ttk.Combobox(fine,textvariable=self.snap_mm,state="readonly",values=[0.05,0.1,0.25,0.5,1.0],width=8).grid(row=0,column=1,sticky="w")
        ttk.Label(fine,text="Font step").grid(row=0,column=2,sticky="e",padx=(10,2))
        ttk.Combobox(fine,textvariable=self.font_step,state="readonly",values=[0.1,0.2,0.5,1.0],width=6).grid(row=0,column=3,sticky="w")
        arrows=ttk.Frame(fine); arrows.grid(row=1,column=0,columnspan=4,pady=(5,0))
        ttk.Button(arrows,text="↑",width=6,command=lambda:self.nudge(0,-1)).grid(row=0,column=1,padx=2,pady=2)
        ttk.Button(arrows,text="←",width=6,command=lambda:self.nudge(-1,0)).grid(row=1,column=0,padx=2,pady=2)
        ttk.Button(arrows,text="→",width=6,command=lambda:self.nudge(1,0)).grid(row=1,column=2,padx=2,pady=2)
        ttk.Button(arrows,text="↓",width=6,command=lambda:self.nudge(0,1)).grid(row=2,column=1,padx=2,pady=2)

        # -------- canvas --------
        canvasbar=ttk.Frame(right); canvasbar.pack(fill="x",pady=(0,5))
        ttk.Label(canvasbar,text="Drag canvas").pack(side="left")
        ttk.Label(canvasbar,text="Drag empty space = multi-select | Shift+Click = add/remove | ↻ knob = rotate (Shift = 15° steps)",style="Muted.TLabel").pack(side="left",padx=10)
        ttk.Button(canvasbar,text="Virtual Area",command=self.select_virtual_area).pack(side="right",padx=(4,0))
        ttk.Button(canvasbar,text="Fold Line",command=self.ensure_fold_line).pack(side="right",padx=(4,0))
        ttk.Button(canvasbar,text="Fit",command=self.zoom_fit).pack(side="right",padx=(8,2))
        ttk.Button(canvasbar,text="+",width=3,command=lambda:self.change_zoom(25)).pack(side="right",padx=1)
        ttk.Button(canvasbar,text="−",width=3,command=lambda:self.change_zoom(-25)).pack(side="right",padx=1)
        self.zoom_combo=ttk.Combobox(canvasbar,textvariable=self.zoom_text,state="readonly",width=7,values=['75%','100%','125%','150%','200%','250%','300%','400%','500%'])
        self.zoom_combo.pack(side="right",padx=(3,2)); self.zoom_combo.bind('<<ComboboxSelected>>',self.zoom_combo_changed)
        ttk.Label(canvasbar,text="Zoom").pack(side="right")

        cf=ttk.Frame(right); cf.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(cf,background="#d9d9d9",highlightthickness=1,highlightbackground="#9a9a9a",cursor="arrow")
        hs=ttk.Scrollbar(cf,orient='horizontal',command=self.canvas.xview); vs=ttk.Scrollbar(cf,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hs.set,yscrollcommand=vs.set)
        self.canvas.grid(row=0,column=0,sticky='nsew'); vs.grid(row=0,column=1,sticky='ns'); hs.grid(row=1,column=0,sticky='ew')
        cf.rowconfigure(0,weight=1); cf.columnconfigure(0,weight=1)
        self.canvas.bind('<Configure>',lambda e:self.after_idle(self.render_canvas))
        self.canvas.bind('<Button-1>',self.canvas_press)
        self.canvas.bind('<B1-Motion>',self.canvas_drag)
        self.canvas.bind('<ButtonRelease-1>',self.canvas_release)
        self.canvas.bind('<Double-1>',self.canvas_double_click)
        self.canvas.bind('<MouseWheel>',self.canvas_mousewheel)
        self.canvas.bind('<Shift-MouseWheel>',self.canvas_shift_mousewheel)
        self.canvas.bind('<Control-MouseWheel>',self.canvas_ctrl_mousewheel)

        bottom=ttk.Frame(self,padding=(10,0,10,10)); bottom.pack(fill='x')
        self.coord_var=tk.StringVar(value="")
        ttk.Label(bottom,textvariable=self.coord_var).pack(side='left')
        ttk.Label(bottom,text="Changes are live; Save Template only persists them.",foreground="#555").pack(side='left',padx=15)
        ttk.Button(bottom,text="Close",command=self.close_dialog).pack(side='right')
        ttk.Button(bottom,text="Reload Saved",command=self.reload_saved).pack(side='right',padx=4)

        self.refresh_list()
        if self.cfg.get('elements'): self.set_selection({0},0)
        self.after(100,self.render_canvas)

        self.bind('<Control-z>',lambda e:self.undo())
        self.bind('<Control-y>',lambda e:self.redo())
        self.bind('<Control-s>',lambda e:self.save_json_now())
        self.bind('<Control-d>',lambda e:self.duplicate_selected())
        self.bind('<Delete>',lambda e:self.delete_selected())
        self.bind('<Up>',lambda e:self.nudge(0,-1))
        self.bind('<Down>',lambda e:self.nudge(0,1))
        self.bind('<Left>',lambda e:self.nudge(-1,0))
        self.bind('<Right>',lambda e:self.nudge(1,0))
        self.protocol('WM_DELETE_WINDOW',self.close_dialog)
        self.transient(parent)

    # ---------- shared state / undo ----------
    def _snapshot(self): return copy.deepcopy(self.cfg)
    def _push_undo(self, snap=None):
        snap = copy.deepcopy(snap if snap is not None else self.cfg)
        self.undo_stack.append(snap)
        if len(self.undo_stack)>60: self.undo_stack=self.undo_stack[-60:]
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack: return
        self.redo_stack.append(self._snapshot())
        self.cfg=self.undo_stack.pop()
        self._commit_live('Undo')
        self.refresh_list(); self._sanitize_selection(); self.render_canvas()

    def redo(self):
        if not self.redo_stack: return
        self.undo_stack.append(self._snapshot())
        self.cfg=self.redo_stack.pop()
        self._commit_live('Redo')
        self.refresh_list(); self._sanitize_selection(); self.render_canvas()

    def _commit_live(self, note='Layout changed'):
        self.dirty=True
        self.save_btn.config(text='Save Template *')
        self.app.set_template_cfg(self.cfg)
        try: self.app.save_working_copy(self.cfg)
        except Exception: pass
        try: self.app.preview_current()
        except Exception: pass
        self.app.status.config(text=f"{note} — LIVE for printing, not saved to template yet.")

    def _sanitize_selection(self):
        n=len(self.cfg.get('elements',[]))
        self.selected_indices={i for i in self.selected_indices if 0<=i<n}
        if self.primary_idx not in self.selected_indices:
            self.primary_idx=min(self.selected_indices) if self.selected_indices else None
        self.sync_list_selection(); self.update_form()

    # ---------- zoom ----------
    def zoom_fit(self):
        self.zoom_percent.set(100); self.zoom_text.set('100%'); self.render_canvas(reset_view=True)
    def change_zoom(self,delta):
        z=max(50,min(600,int(self.zoom_percent.get())+int(delta)))
        self.zoom_percent.set(z); self.zoom_text.set(f'{z}%')
        try:
            self.app.workspace_state['designer_zoom']=z; self.app.save_workspace()
        except Exception: pass
        self.render_canvas(preserve_center=True)
    def zoom_combo_changed(self,_event=None):
        try: z=int(str(self.zoom_text.get()).replace('%','').strip())
        except Exception: z=200
        self.zoom_percent.set(max(50,min(600,z))); self.zoom_text.set(f'{self.zoom_percent.get()}%')
        self.change_zoom(0)
    def canvas_mousewheel(self,event): self.canvas.yview_scroll(int(-event.delta/120),'units'); return 'break'
    def canvas_shift_mousewheel(self,event): self.canvas.xview_scroll(int(-event.delta/120),'units'); return 'break'
    def canvas_ctrl_mousewheel(self,event): self.change_zoom(25 if event.delta>0 else -25); return 'break'
    def _canvas_point(self,event): return self.canvas.canvasx(event.x),self.canvas.canvasy(event.y)

    # ---------- element list ----------
    def describe(self,i,e):
        lock='[L]' if e.get('locked',False) else '   '
        txt=str(e.get('text',e.get('value',''))).replace('\n',' ')[:31]
        ang=_element_angle(e); at=f" ↻{ang:g}°" if abs(ang)>0.0001 else ""
        return f"{i+1:02d} {lock} {e.get('type','?'):<8} {txt}{at}"
    def refresh_list(self):
        self.listbox.delete(0,'end')
        for i,e in enumerate(self.cfg.get('elements',[])): self.listbox.insert('end',self.describe(i,e))
        self.sync_list_selection()
    def sync_list_selection(self):
        self.listbox.selection_clear(0,'end')
        for i in sorted(self.selected_indices):
            if i<self.listbox.size(): self.listbox.selection_set(i)
        if self.primary_idx is not None and self.primary_idx<self.listbox.size(): self.listbox.see(self.primary_idx)
        self.selection_label.config(text=f"{len(self.selected_indices)} selected" if self.selected_indices else '')
    def set_selection(self,indices,primary=None):
        n=len(self.cfg.get('elements',[])); self.selected_indices={i for i in indices if 0<=i<n}
        self.primary_idx=primary if primary in self.selected_indices else (min(self.selected_indices) if self.selected_indices else None)
        self.sync_list_selection(); self.update_form(); self.draw_overlays()
    def on_list_select(self,_event=None):
        cur={int(i) for i in self.listbox.curselection()}
        primary=min(cur) if cur else None
        self.selected_indices=cur; self.primary_idx=primary
        self.update_form(); self.draw_overlays()
    def update_form(self):
        if not self.selected_indices:
            self.type_label.config(text='');
            for v in self.vars.values(): v.set('')
            self.coord_var.set(''); return
        if len(self.selected_indices)>1:
            self.type_label.config(text=f'{len(self.selected_indices)} elements')
            for k in ('x','y','w','h','text','value'): self.vars[k].set('')
            angs=[round(_element_angle(self.cfg['elements'][i]),3) for i in self.selected_indices]
            self.vars['angle'].set(f"{angs[0]:g}" if all(abs(a-angs[0])<1e-9 for a in angs) else '')
            fs=[]
            for i in self.selected_indices:
                e=self.cfg['elements'][i]
                if str(e.get('type','')).lower()=='text' and 'font_size' in e: fs.append(float(e.get('font_size',0)))
            self.vars['font_size'].set(str(fs[0]) if fs and all(abs(v-fs[0])<1e-9 for v in fs) else '')
            self.coord_var.set(f'{len(self.selected_indices)} elements selected'); return
        i=self.primary_idx; e=self.cfg['elements'][i]
        self.type_label.config(text=str(e.get('type','')) + ('  [LOCKED]' if e.get('locked') else ''))
        for k in ('x','y','w','h','font_size','text','value'): self.vars[k].set('' if k not in e else str(e.get(k,'')))
        self.vars['angle'].set(f"{_element_angle(e):g}")
        self.coord_var.set(f"Element {i+1}: x={e.get('x',0)} mm, y={e.get('y',0)} mm")

    # ---------- geometry helpers ----------
    def _snap(self,v):
        try: step=float(self.snap_mm.get())
        except Exception: step=0.1
        if step<=0: return round(float(v),3)
        return round(round(float(v)/step)*step,3)
    def _source_box(self,e):
        t=str(e.get('type','')).lower(); x=float(e.get('x',0) or 0); y=float(e.get('y',0) or 0)
        if t=='line':
            x2=float(e.get('x2',x) or x); y2=float(e.get('y2',y) or y)
            return min(x,x2),min(y,y2),max(abs(x2-x),0.5),max(abs(y2-y),0.5)
        return x,y,max(float(e.get('w',1) or 1),0.5),max(float(e.get('h',1) or 1),0.5)
    def _element_in_fold_region(self,e,fr):
        if not fr or not fr.get('enabled',True) or int(fr.get('angle',180))%360!=180:
            return False
        x,y,w,h=self._source_box(e); cx=x+w/2; cy=y+h/2
        rx=float(fr.get('x',0)); ry=float(fr.get('y',0)); rw=float(fr.get('w',0)); rh=float(fr.get('h',0))
        return rx<=cx<=rx+rw and ry<=cy<=ry+rh
    def _fold_for_element(self,e):
        for fr in self.cfg.get('fold_regions',[]):
            if self._element_in_fold_region(e,fr): return fr
        return None
    def _display_box_mm(self,e):
        x,y,w,h=self._source_box(e); fr=self._fold_for_element(e)
        if fr is not None:
            rx=float(fr.get('x',0)); ry=float(fr.get('y',0)); rw=float(fr.get('w',0)); rh=float(fr.get('h',0))
            x=rx+rw-(x-rx)-w; y=ry+rh-(y-ry)-h
        return x,y,w,h
    def _display_to_source_box(self,e,box):
        x,y,w,h=box; fr=self._fold_for_element(e)
        if fr is not None:
            rx=float(fr.get('x',0)); ry=float(fr.get('y',0)); rw=float(fr.get('w',0)); rh=float(fr.get('h',0))
            x=rx+rw-(x-rx)-w; y=ry+rh-(y-ry)-h
        return x,y,w,h
    def _virtual_area(self):
        a=dict(self.cfg.get('virtual_print_area') or {}); a.setdefault('show',True); a.setdefault('x',0.0); a.setdefault('y',0.0)
        a.setdefault('w',self.cfg.get('width_mm',56)); a.setdefault('h',self.cfg.get('height_mm',83)); return a
    def _bound_preview_cfg(self):
        cfg=copy.deepcopy(self.cfg)
        try:
            if self.app.rows: cfg=bind_row_to_template(cfg,self.app.rows[self.app.current_row_index])
        except Exception: pass
        return cfg
    def _workspace_preview_cfg(self):
        cfg=self._bound_preview_cfg(); pw=float(cfg.get('width_mm',56)); ph=float(cfg.get('height_mm',83)); pad=8.0
        min_x,min_y,max_x,max_y=-pad,-pad,pw+pad,ph+pad
        a=self._virtual_area()
        if a.get('show',True):
            ax=float(a.get('x',0)); ay=float(a.get('y',0)); aw=float(a.get('w',pw)); ah=float(a.get('h',ph))
            min_x=min(min_x,ax-pad); min_y=min(min_y,ay-pad); max_x=max(max_x,ax+aw+pad); max_y=max(max_y,ay+ah+pad)
        for e in cfg.get('elements',[]):
            try:
                if abs(_element_angle(e)%360)>0.0001:
                    pts=self._frame_corners(self._visual_frame(e)); xs=[p[0] for p in pts]; ys=[p[1] for p in pts]; x,y,w,h=min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)
                else: x,y,w,h=self._display_box_mm(e)
                min_x=min(min_x,x-pad); min_y=min(min_y,y-pad); max_x=max(max_x,x+w+pad); max_y=max(max_y,y+h+pad)
            except Exception: pass
        min_x=max(-300.0,min_x); min_y=max(-300.0,min_y); max_x=min(500.0,max_x); max_y=min(500.0,max_y)
        self.workspace_min_x=min_x; self.workspace_min_y=min_y; sx=-min_x; sy=-min_y
        wc=copy.deepcopy(cfg); wc['width_mm']=max(20,max_x-min_x); wc['height_mm']=max(20,max_y-min_y); wc['orientation']='portrait'
        wc['offset_x_mm']=0; wc['offset_y_mm']=0; wc['rotation_deg']=0; wc['scale_x_pct']=100.0; wc['scale_y_pct']=100.0; wc['printable_area']={'enabled':False,'x':0,'y':0,'w':wc['width_mm'],'h':wc['height_mm']}; wc['virtual_print_area']={'show':False,'x':0,'y':0,'w':1,'h':1}
        for e in wc.get('elements',[]):
            for k in ('x','x2'):
                if k in e: e[k]=float(e.get(k,0))+sx
            for k in ('y','y2'):
                if k in e: e[k]=float(e.get(k,0))+sy
        for fr in wc.get('fold_regions',[]): fr['x']=float(fr.get('x',0))+sx; fr['y']=float(fr.get('y',0))+sy
        shifted=[]
        for g in wc.get('preview_guides',[]):
            gg=copy.deepcopy(g)
            if 'x' in gg: gg['x']=float(gg.get('x',0))+sx
            if 'y' in gg: gg['y']=float(gg.get('y',0))+sy
            if 'x2' in gg: gg['x2']=float(gg.get('x2',0))+sx
            if 'y2' in gg: gg['y2']=float(gg.get('y2',0))+sy
            shifted.append(gg)
        shifted.append({'name':'Nominal paper','type':'box','x':sx,'y':sy,'w':pw,'h':ph,'color':'gray','show':True})
        if a.get('show',True): shifted.append({'name':'Virtual print area','type':'box','x':float(a.get('x',0))+sx,'y':float(a.get('y',0))+sy,'w':float(a.get('w',pw)),'h':float(a.get('h',ph)),'color':'green','show':True})
        wc['preview_guides']=shifted; return wc
    def _box_to_canvas(self,box):
        x,y,w,h=box; dpi=int(self.cfg.get('dpi',DEFAULT_DPI))*self.render_scale; x-=self.workspace_min_x; y-=self.workspace_min_y
        x1=self.PREVIEW_MARGIN+mm_to_px(x,dpi); y1=self.PREVIEW_MARGIN+mm_to_px(y,dpi); x2=self.PREVIEW_MARGIN+mm_to_px(x+w,dpi); y2=self.PREVIEW_MARGIN+mm_to_px(y+h,dpi); r=self.preview_ratio
        return self.preview_offset_x+x1*r,self.preview_offset_y+y1*r,self.preview_offset_x+x2*r,self.preview_offset_y+y2*r
    def _point_to_canvas(self,x,y):
        b=self._box_to_canvas((x,y,0,0)); return b[0],b[1]
    def _canvas_delta_mm(self,dx,dy):
        dpi=int(self.cfg.get('dpi',DEFAULT_DPI))*self.render_scale; denom=max(.0001,self.preview_ratio)*dpi
        return dx*25.4/denom,dy*25.4/denom

    # ---------- rotated element geometry (display coordinates, mm) ----------
    def _visual_frame(self,e):
        """(cx,cy,w,h,theta) of the element as shown in the preview (theta clockwise degrees)."""
        fr=self._fold_for_element(e); fold=180.0 if fr is not None else 0.0
        if str(e.get('type','')).lower()=='line':
            x1=float(e.get('x',0) or 0); y1=float(e.get('y',0) or 0); x2=float(e.get('x2',x1) or x1); y2=float(e.get('y2',y1) or y1)
            cx=(x1+x2)/2; cy=(y1+y2)/2
            if fr is not None:
                rx=float(fr.get('x',0)); ry=float(fr.get('y',0)); rw=float(fr.get('w',0)); rh=float(fr.get('h',0))
                cx=2*(rx+rw/2)-cx; cy=2*(ry+rh/2)-cy
            ln=max(math.hypot(x2-x1,y2-y1),0.5)
            return cx,cy,ln,max(float(e.get('thickness',0.2) or 0.2),0.8),math.degrees(math.atan2(y2-y1,x2-x1))+_element_angle(e)+fold
        x,y,w,h=self._display_box_mm(e)
        return x+w/2,y+h/2,w,h,_element_angle(e)+fold
    def _frame_corners(self,frame):
        cx,cy,w,h,th=frame
        return [rotate_point_cw(cx+dx,cy+dy,cx,cy,th) for dx,dy in ((-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2))]
    def _mm_to_canvas_pt(self,x,y):
        b=self._box_to_canvas((x,y,0,0)); return b[0],b[1]
    @staticmethod
    def _point_near_poly(pts,x,y,pad):
        inside=False; n=len(pts)
        for k in range(n):
            x1,y1=pts[k]; x2,y2=pts[(k+1)%n]
            if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/((y2-y1) or 1e-9)+x1: inside=not inside
            dx=x2-x1; dy=y2-y1; L=dx*dx+dy*dy
            t=0 if L==0 else max(0,min(1,((x-x1)*dx+(y-y1)*dy)/L))
            if math.hypot(x-(x1+t*dx),y-(y1+t*dy))<=pad: return True
        return inside

    # ---------- render overlays ----------
    def render_canvas(self,preserve_center=False,reset_view=False):
        if not self.winfo_exists(): return
        try:
            cw=max(300,self.canvas.winfo_width()); ch=max(300,self.canvas.winfo_height()); old=None
            if preserve_center:
                try:
                    r=[float(v) for v in str(self.canvas.cget('scrollregion')).split()]
                    cx=self.canvas.canvasx(cw/2); cy=self.canvas.canvasy(ch/2)
                    if len(r)==4: old=((cx-r[0])/max(1,r[2]-r[0]),(cy-r[1])/max(1,r[3]-r[1]))
                except Exception: old=None
            cfg=self._workspace_preview_cfg(); img=render_preview_with_guides(cfg,scale=self.render_scale,show_guides=True,show_fold=True); self.preview_source=img
            fit=min((cw-40)/img.width,(ch-40)/img.height,1.0); zoom=max(.5,min(6,float(self.zoom_percent.get())/100)); ratio=fit*zoom
            sw=max(1,int(img.width*ratio)); sh=max(1,int(img.height*ratio)); show=img if abs(ratio-1)<1e-9 else img.resize((sw,sh),Image.Resampling.LANCZOS); self.preview_ratio=ratio
            self.preview_offset_x=max(20,int((cw-sw)/2)) if sw<cw else 20; self.preview_offset_y=max(20,int((ch-sh)/2)) if sh<ch else 20
            tw=max(cw,self.preview_offset_x+sw+20); th=max(ch,self.preview_offset_y+sh+20)
            self.tk_preview=ImageTk.PhotoImage(show); self.canvas.delete('all'); self.canvas.create_image(self.preview_offset_x,self.preview_offset_y,anchor='nw',image=self.tk_preview,tags=('preview',)); self.canvas.configure(scrollregion=(0,0,tw,th)); self.draw_overlays()
            if reset_view: self.canvas.xview_moveto(0); self.canvas.yview_moveto(0)
            elif old:
                fx,fy=old; self.canvas.xview_moveto(max(0,min(1,fx-(cw/2)/max(tw,1)))); self.canvas.yview_moveto(max(0,min(1,fy-(ch/2)/max(th,1))))
        except Exception as ex:
            self.canvas.delete('all'); self.canvas.create_text(20,20,anchor='nw',fill='red',text=f'Preview error: {ex}')

    def _handle_rect(self,x,y):
        h=self.HANDLE; return (x-h,y-h,x+h,y+h)
    def draw_overlays(self):
        if not hasattr(self,'canvas') or self.preview_source is None: return
        self.canvas.delete('designer_overlay'); self.overlay_boxes={}; self.overlay_polys={}; self.element_handles={}; self.virtual_handles={}; self.virtual_border=None; self.fold_overlay=None
        els=self.cfg.get('elements',[])
        for i,e in enumerate(els):
            try: x1,y1,x2,y2=self._box_to_canvas(self._display_box_mm(e))
            except Exception: continue
            selected=i in self.selected_indices; locked=bool(e.get('locked',False)); color='#d11' if selected else ('#777' if locked else '#1677d2'); width=3 if selected else 1
            if abs(_element_angle(e)%360)>0.0001:
                pts=[self._mm_to_canvas_pt(px,py) for px,py in self._frame_corners(self._visual_frame(e))]
                flat=[c for p in pts for c in p]
                rid=self.canvas.create_polygon(*flat,outline=color,fill='',width=width,dash=(() if selected else (4,3)),tags=('designer_overlay',f'el_{i}'))
                xs=[p[0] for p in pts]; ys=[p[1] for p in pts]; x1,y1,x2,y2=min(xs),min(ys),max(xs),max(ys); self.overlay_polys[i]=pts
            else:
                rid=self.canvas.create_rectangle(x1,y1,x2,y2,outline=color,width=width,dash=(() if selected else (4,3)),tags=('designer_overlay',f'el_{i}'))
            self.overlay_boxes[i]=(x1,y1,x2,y2,rid)
            if selected:
                self.canvas.create_text(x1+3,y1-3,text=f"{i+1} {e.get('type','')}"+(' 🔒' if locked else ''),anchor='sw',fill=color,font=('Segoe UI',9,'bold'),tags=('designer_overlay',f'el_{i}'))
        # Resize handles for exactly one unlocked selection.
        if len(self.selected_indices)==1:
            i=next(iter(self.selected_indices)); e=els[i]
            if not e.get('locked',False):
                b=self.overlay_boxes.get(i)
                if b:
                    x1,y1,x2,y2,_=b; t=str(e.get('type','')).lower()
                    if i in self.overlay_polys:
                        if t!='line':
                            for role,(hx,hy) in zip(('nw','ne','se','sw'),self.overlay_polys[i]):
                                rr=self._handle_rect(hx,hy); self.canvas.create_rectangle(*rr,fill='white',outline='#d11',tags=('designer_overlay',)); self.element_handles[role]=rr
                    elif t=='line':
                        # Source line endpoints are sufficient as resize handles.
                        for role,(hx,hy) in {'line_start':(x1,y1),'line_end':(x2,y2)}.items():
                            rr=self._handle_rect(hx,hy); self.canvas.create_rectangle(*rr,fill='white',outline='#d11',tags=('designer_overlay',)); self.element_handles[role]=rr
                    else:
                        for role,(hx,hy) in {'nw':(x1,y1),'ne':(x2,y1),'sw':(x1,y2),'se':(x2,y2)}.items():
                            rr=self._handle_rect(hx,hy); self.canvas.create_rectangle(*rr,fill='white',outline='#d11',tags=('designer_overlay',)); self.element_handles[role]=rr
                    # Rotation handle: round knob above the element, along its own "up" direction.
                    fcx,fcy,fw,fh,fth=self._visual_frame(e); ccx,ccy=self._mm_to_canvas_pt(fcx,fcy)
                    pts=self.overlay_polys.get(i) or [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]
                    mx=(pts[0][0]+pts[1][0])/2; my=(pts[0][1]+pts[1][1])/2
                    ux=mx-ccx; uy=my-ccy; ul=math.hypot(ux,uy)
                    if ul<1e-6: ux,uy,ul=0.0,-1.0,1.0
                    kx=mx+ux/ul*26; ky=my+uy/ul*26
                    self.canvas.create_line(mx,my,kx,ky,fill='#d11',tags=('designer_overlay',))
                    self.canvas.create_oval(kx-8,ky-8,kx+8,ky+8,fill='#fff3c4',outline='#d11',width=2,tags=('designer_overlay',))
                    self.canvas.create_text(kx,ky,text='↻',fill='#d11',font=('Segoe UI',9,'bold'),tags=('designer_overlay',))
                    self.element_handles['rotate']=(kx-9,ky-9,kx+9,ky+9); self.rotate_center=(ccx,ccy)
        # Draggable virtual print area (guide only).
        a=self._virtual_area()
        if a.get('show',True):
            x1,y1,x2,y2=self._box_to_canvas((float(a.get('x',0)),float(a.get('y',0)),float(a.get('w',1)),float(a.get('h',1))))
            self.virtual_border=(x1,y1,x2,y2)
            self.canvas.create_rectangle(x1,y1,x2,y2,outline='#159447',width=2,dash=(7,3),tags=('designer_overlay',))
            self.canvas.create_text(x1+4,y1-4,text='VIRTUAL PRINT AREA',anchor='sw',fill='#087b32',font=('Segoe UI',9,'bold'),tags=('designer_overlay',))
            for role,(hx,hy) in {'nw':(x1,y1),'ne':(x2,y1),'sw':(x1,y2),'se':(x2,y2)}.items():
                rr=self._handle_rect(hx,hy); self.canvas.create_rectangle(*rr,fill='#dff5e6',outline='#159447',tags=('designer_overlay',)); self.virtual_handles[role]=rr
        # First enabled 180-degree fold region becomes a directly draggable boundary.
        fr=self._first_fold()
        if fr:
            x1,y=self._point_to_canvas(float(fr.get('x',0)),float(fr.get('y',0))); x2,_=self._point_to_canvas(float(fr.get('x',0))+float(fr.get('w',0)),float(fr.get('y',0)))
            self.canvas.create_line(x1,y,x2,y,fill='#e18200',width=3,tags=('designer_overlay',)); self.canvas.create_rectangle(x1-7,y-7,x1+7,y+7,fill='#ffe5b7',outline='#e18200',tags=('designer_overlay',)); self.canvas.create_text(x1+10,y-8,text='FOLD',anchor='sw',fill='#b46600',font=('Segoe UI',9,'bold'),tags=('designer_overlay',)); self.fold_overlay=(x1,y,x2,y)

    # ---------- hit testing ----------
    @staticmethod
    def _inside(r,x,y,pad=0): return r[0]-pad<=x<=r[2]+pad and r[1]-pad<=y<=r[3]+pad
    def _hit_element(self,x,y):
        for i in range(len(self.cfg.get('elements',[]))-1,-1,-1):
            b=self.overlay_boxes.get(i)
            if not b: continue
            if i in self.overlay_polys:
                if self._point_near_poly(self.overlay_polys[i],x,y,4): return i
            elif self._inside(b[:4],x,y,4): return i
        return None
    def _hit_handle(self,handles,x,y):
        for role,r in handles.items():
            if self._inside(r,x,y,1): return role
        return None
    def _hit_virtual_border(self,x,y):
        if not self.virtual_border: return False
        x1,y1,x2,y2=self.virtual_border; p=6
        return (x1-p<=x<=x2+p and (abs(y-y1)<=p or abs(y-y2)<=p)) or (y1-p<=y<=y2+p and (abs(x-x1)<=p or abs(x-x2)<=p))
    def _hit_fold(self,x,y):
        if not self.fold_overlay: return False
        x1,yy,x2,_=self.fold_overlay; return min(x1,x2)-8<=x<=max(x1,x2)+8 and abs(y-yy)<=7

    # ---------- mouse interaction ----------
    def canvas_press(self,event):
        cx,cy=self._canvas_point(event); self.drag_start=(cx,cy); self.drag_before=self._snapshot(); self.drag_original=None; self.drag_role=None
        role=self._hit_handle(self.element_handles,cx,cy)
        if role and len(self.selected_indices)==1:
            e0=self.cfg['elements'][self.primary_idx]
            if role=='rotate':
                self.mode='element_rotate'; self.drag_role=role; self.drag_original=copy.deepcopy(e0); self.canvas.configure(cursor='exchange'); return
            if str(e0.get('type','')).lower()=='line' and abs(_element_angle(e0))>0.0001:
                # Bake the rotation into the end points so they can be dragged normally.
                lcx,lcy=element_rotation_center(e0); la=_element_angle(e0)
                e0['x'],e0['y']=rotate_point_cw(float(e0['x']),float(e0['y']),lcx,lcy,la)
                e0['x2'],e0['y2']=rotate_point_cw(float(e0.get('x2',e0['x'])),float(e0.get('y2',e0['y'])),lcx,lcy,la)
                e0.pop('angle',None)
            self.mode='element_resize'; self.drag_role=role; self.drag_original=copy.deepcopy(e0); self.canvas.configure(cursor='sizing'); return
        vrole=self._hit_handle(self.virtual_handles,cx,cy)
        if vrole:
            self.mode='virtual_resize'; self.drag_role=vrole; self.drag_original=copy.deepcopy(self._virtual_area()); self.canvas.configure(cursor='sizing'); return
        if self._hit_fold(cx,cy):
            fr0=copy.deepcopy(self._first_fold())
            members={}
            if fr0:
                for i,e in enumerate(self.cfg.get('elements',[])):
                    if self._element_in_fold_region(e,fr0):
                        members[i]=copy.deepcopy(e)
            self.mode='fold_move'; self.drag_original={'fold':fr0,'members':members}; self.canvas.configure(cursor='sb_v_double_arrow'); return
        idx=self._hit_element(cx,cy)
        shift=bool(event.state & 0x0001)
        if idx is not None:
            if shift:
                ns=set(self.selected_indices)
                if idx in ns: ns.remove(idx)
                else: ns.add(idx)
                self.set_selection(ns,idx if idx in ns else (min(ns) if ns else None)); self.mode=None; return
            if idx not in self.selected_indices: self.set_selection({idx},idx)
            else: self.primary_idx=idx; self.update_form(); self.draw_overlays()
            movable=[i for i in self.selected_indices if not self.cfg['elements'][i].get('locked',False)]
            if movable:
                self.mode='move'; self.drag_original={i:copy.deepcopy(self.cfg['elements'][i]) for i in movable}; self.canvas.configure(cursor='fleur')
            else: self.mode=None
            return
        if self._hit_virtual_border(cx,cy):
            self.mode='virtual_move'; self.drag_original=copy.deepcopy(self._virtual_area()); self.canvas.configure(cursor='fleur'); return
        # Empty canvas = marquee selection.
        if not shift: self.set_selection(set(),None)
        self.mode='marquee'; self.marquee_start=(cx,cy)
        self.selection_rect=self.canvas.create_rectangle(cx,cy,cx,cy,outline='#555',dash=(4,3),fill='',tags=('selection_box',))

    def canvas_drag(self,event):
        if not self.mode or not self.drag_start: return
        cx,cy=self._canvas_point(event); dx=cx-self.drag_start[0]; dy=cy-self.drag_start[1]
        if self.mode=='marquee' and self.selection_rect:
            self.canvas.coords(self.selection_rect,self.marquee_start[0],self.marquee_start[1],cx,cy); return
        if self.mode=='move':
            self.draw_overlays()
            for i in self.drag_original:
                for item in self.canvas.find_withtag(f'el_{i}'): self.canvas.move(item,dx,dy)
            self.coord_var.set(f'Move {len(self.drag_original)} element(s): Δ {dx:+.0f}px, {dy:+.0f}px'); return
        if self.mode=='element_rotate':
            self.canvas.delete('drag_ghost'); ang=self._rotate_drag_angle(cx,cy,bool(event.state & 0x0001))
            ccx,ccy=self.rotate_center; self.canvas.create_line(ccx,ccy,cx,cy,fill='#d11',dash=(4,3),tags=('drag_ghost',))
            self.canvas.create_text(cx+12,cy-12,text=f'{ang:g}°',fill='#d11',font=('Segoe UI',10,'bold'),tags=('drag_ghost',))
            self.coord_var.set(f'Rotate: {ang:g}°'); return
        if self.mode in ('virtual_move','virtual_resize','fold_move','element_resize'):
            # Ghost preview while dragging guides. The real JSON is committed only on mouse release.
            self.canvas.delete('drag_ghost')
            if self.mode in ('virtual_move','virtual_resize') and self.virtual_border:
                x1,y1,x2,y2=self.virtual_border
                if self.mode=='virtual_move':
                    gx1,gy1,gx2,gy2=x1+dx,y1+dy,x2+dx,y2+dy
                else:
                    gx1,gy1,gx2,gy2=x1,y1,x2,y2
                    r=self.drag_role or ''
                    if 'w' in r: gx1=x1+dx
                    if 'e' in r: gx2=x2+dx
                    if 'n' in r: gy1=y1+dy
                    if 's' in r: gy2=y2+dy
                    if gx2<gx1: gx1,gx2=gx2,gx1
                    if gy2<gy1: gy1,gy2=gy2,gy1
                self.canvas.create_rectangle(gx1,gy1,gx2,gy2,outline='#00a84f',width=2,dash=(3,3),tags=('drag_ghost',))
                self.canvas.create_text(gx1+4,gy1-4,text='NEW PRINT AREA',anchor='sw',fill='#00853e',font=('Segoe UI',9,'bold'),tags=('drag_ghost',))
            elif self.mode=='fold_move' and self.fold_overlay:
                x1,yy,x2,_=self.fold_overlay; gy=yy+dy
                self.canvas.create_line(x1,gy,x2,gy,fill='#ff9800',width=2,dash=(4,3),tags=('drag_ghost',))
                self.canvas.create_text(x1+10,gy-7,text='NEW FOLD',anchor='sw',fill='#b46600',font=('Segoe UI',9,'bold'),tags=('drag_ghost',))
            self.coord_var.set(f'{self.mode.replace("_"," ")}: Δ {dx:+.0f}px, {dy:+.0f}px')

    def canvas_release(self,event):
        if not self.mode or not self.drag_start:
            self.canvas.configure(cursor='arrow'); return
        cx,cy=self._canvas_point(event); dx=cx-self.drag_start[0]; dy=cy-self.drag_start[1]; mode=self.mode
        self.canvas.delete('drag_ghost')
        self.mode=None; self.drag_start=None; self.canvas.configure(cursor='arrow')
        changed=False
        if mode=='marquee':
            if self.selection_rect: self.canvas.delete(self.selection_rect); self.selection_rect=None
            x1,x2=sorted((self.marquee_start[0],cx)); y1,y2=sorted((self.marquee_start[1],cy)); hits=set(self.selected_indices)
            for i,b in self.overlay_boxes.items():
                bx1,by1,bx2,by2,_=b
                if not (bx2<x1 or bx1>x2 or by2<y1 or by1>y2): hits.add(i)
            self.set_selection(hits,min(hits) if hits else None); return
        if mode=='element_rotate' and self.primary_idx is not None:
            e=self.cfg['elements'][self.primary_idx]
            self._set_angle(e,self._rotate_drag_angle(cx,cy,bool(event.state & 0x0001)))
            self._push_undo(self.drag_before); self._commit_live('Rotated'); self.refresh_list(); self._sanitize_selection(); self.update_form(); self.render_canvas(); return
        if abs(dx)<1 and abs(dy)<1:
            if self.drag_before and self.drag_before!=self.cfg:
                self._push_undo(self.drag_before); self._commit_live('Line rotation applied')
            self.render_canvas(); return
        dxm,dym=self._canvas_delta_mm(dx,dy)
        if mode=='move':
            for i,orig in self.drag_original.items():
                e=self.cfg['elements'][i]; sx,sy=( -dxm,-dym) if self._fold_for_element(orig) is not None else (dxm,dym)
                ox=float(orig.get('x',0)); oy=float(orig.get('y',0)); e['x']=self._snap(ox+sx); e['y']=self._snap(oy+sy)
                if 'x2' in orig: e['x2']=self._snap(float(orig.get('x2',ox))+sx)
                if 'y2' in orig: e['y2']=self._snap(float(orig.get('y2',oy))+sy)
            changed=True
        elif mode=='element_resize' and self.primary_idx is not None:
            e=self.cfg['elements'][self.primary_idx]; orig=self.drag_original; role=self.drag_role; t=str(orig.get('type','')).lower()
            if t=='line':
                sx,sy=(-dxm,-dym) if self._fold_for_element(orig) is not None else (dxm,dym)
                if role=='line_start': e['x']=self._snap(float(orig.get('x',0))+sx); e['y']=self._snap(float(orig.get('y',0))+sy)
                else: e['x2']=self._snap(float(orig.get('x2',orig.get('x',0)))+sx); e['y2']=self._snap(float(orig.get('y2',orig.get('y',0)))+sy)
            else:
                x,y,w,h=self._display_box_mm(orig); nx,ny,nw,nh=x,y,w,h; minsz=.5
                th=self._visual_frame(orig)[4] if abs(_element_angle(orig))>0.0001 else 0.0
                odxm,odym=dxm,dym
                if th: dxm,dym=rotate_point_cw(dxm,dym,0,0,-th)   # pointer delta in the element's own frame
                if 'w' in role: nx=x+dxm; nw=w-dxm
                if 'e' in role: nw=w+dxm
                if 'n' in role: ny=y+dym; nh=h-dym
                if 's' in role: nh=h+dym
                if nw<minsz:
                    if 'w' in role: nx-=minsz-nw
                    nw=minsz
                if nh<minsz:
                    if 'n' in role: ny-=minsz-nh
                    nh=minsz
                if th:
                    # Keep the opposite corner fixed on the page although the centre (rotation pivot) moves.
                    ax=x if 'e' in role else x+w; ay=y if 's' in role else y+h
                    oc=(x+w/2,y+h/2); nc=(nx+nw/2,ny+nh/2)
                    wa=rotate_point_cw(ax,ay,oc[0],oc[1],th); wb=rotate_point_cw(ax,ay,nc[0],nc[1],th)
                    nx+=wa[0]-wb[0]; ny+=wa[1]-wb[1]
                sx,sy,sw,sh=self._display_to_source_box(orig,(nx,ny,nw,nh)); e['x']=self._snap(sx); e['y']=self._snap(sy); e['w']=self._snap(sw); e['h']=self._snap(sh)
            changed=True
        elif mode=='virtual_move':
            a=self.drag_original; self.cfg['virtual_print_area']={'show':True,'x':self._snap(float(a.get('x',0))+dxm),'y':self._snap(float(a.get('y',0))+dym),'w':float(a.get('w',1)),'h':float(a.get('h',1))}; changed=True
        elif mode=='virtual_resize':
            a=self.drag_original; x=float(a.get('x',0)); y=float(a.get('y',0)); w=float(a.get('w',1)); h=float(a.get('h',1)); nx,ny,nw,nh=x,y,w,h; r=self.drag_role; minsz=1.0
            if 'w' in r: nx=x+dxm; nw=w-dxm
            if 'e' in r: nw=w+dxm
            if 'n' in r: ny=y+dym; nh=h-dym
            if 's' in r: nh=h+dym
            if nw<minsz: nw=minsz
            if nh<minsz: nh=minsz
            self.cfg['virtual_print_area']={'show':True,'x':self._snap(nx),'y':self._snap(ny),'w':self._snap(nw),'h':self._snap(nh)}; changed=True
        elif mode=='fold_move':
            # Move only the fold boundary. Compensate existing back-face elements in source
            # coordinates so their FINAL folded positions stay exactly where they were.
            # This prevents the whole back face from jumping when the fold line is adjusted.
            fr=self._first_fold(); pack=self.drag_original or {}; orig=pack.get('fold') if isinstance(pack,dict) else None
            if fr and orig:
                oldy=float(orig.get('y',0)); bottom=oldy+float(orig.get('h',0)); newy=self._snap(oldy+dym); maxy=bottom-1.0; newy=min(newy,maxy)
                delta=newy-oldy
                fr['y']=newy; fr['h']=round(bottom-newy,3)
                for i,e0 in (pack.get('members',{}) or {}).items():
                    if i<0 or i>=len(self.cfg.get('elements',[])): continue
                    e=self.cfg['elements'][i]
                    if 'y' in e0: e['y']=self._snap(float(e0.get('y',0))+delta)
                    if 'y2' in e0: e['y2']=self._snap(float(e0.get('y2',e0.get('y',0)))+delta)
                changed=True
        if changed:
            self._push_undo(self.drag_before); self._commit_live(mode.replace('_',' ').title()); self.refresh_list(); self._sanitize_selection(); self.render_canvas()
        else: self.render_canvas()

    def _rotate_drag_angle(self,cx,cy,shift=False):
        e=self.drag_original; ccx,ccy=self.rotate_center
        view=math.degrees(math.atan2(cy-ccy,cx-ccx))+90.0
        if str(e.get('type','')).lower()=='line':
            base=math.degrees(math.atan2(float(e.get('y2',e.get('y',0)))-float(e.get('y',0)),float(e.get('x2',e.get('x',0)))-float(e.get('x',0))))
        else: base=0.0
        if self._fold_for_element(e) is not None: base+=180.0
        ang=view-base; step=15.0 if shift else 1.0
        ang=round(ang/step)*step
        return ((ang+180.0)%360.0)-180.0
    def canvas_double_click(self,event):
        cx,cy=self._canvas_point(event); idx=self._hit_element(cx,cy)
        if idx is not None:
            self.set_selection({idx},idx); e=self.cfg['elements'][idx]
            if str(e.get('type','')).lower()=='text' and not e.get('locked'):
                val=simpledialog.askstring('Edit text','Text:',initialvalue=str(e.get('text','')),parent=self)
                if val is not None:
                    self._push_undo(); e['text']=val; self._commit_live('Text edited'); self.refresh_list(); self.render_canvas()

    # ---------- edit commands ----------
    def apply_selected(self):
        if not self.selected_indices: return
        self._push_undo()
        try:
            if len(self.selected_indices)>1:
                fs=self.vars['font_size'].get().strip()
                if fs:
                    for i in self.selected_indices:
                        e=self.cfg['elements'][i]
                        if str(e.get('type','')).lower()=='text' and not e.get('locked'): e['font_size']=float(fs)
                an=self.vars['angle'].get().strip()
                if an!='':
                    for i in self.selected_indices:
                        e=self.cfg['elements'][i]
                        if not e.get('locked'): self._set_angle(e,float(an))
            else:
                i=self.primary_idx; e=self.cfg['elements'][i]
                if e.get('locked'): return
                for k in ('x','y','w','h','font_size'):
                    v=self.vars[k].get().strip()
                    if v!='': e[k]=float(v)
                an=self.vars['angle'].get().strip()
                if an!='': self._set_angle(e,float(an))
                if 'text' in e or self.vars['text'].get().strip(): e['text']=self.vars['text'].get()
                if 'value' in e or self.vars['value'].get().strip(): e['value']=self.vars['value'].get()
        except Exception as ex:
            if self.undo_stack: self.undo_stack.pop()
            messagebox.showerror('Designer',str(ex),parent=self); return
        self._commit_live('Values applied'); self.refresh_list(); self.update_form(); self.render_canvas()
    @staticmethod
    def _set_angle(e,value):
        a=((float(value)+180.0)%360.0)-180.0
        if abs(a)<0.0001: e.pop('angle',None)
        else: e['angle']=round(a,2)
    def rotate_selected(self,delta):
        ids=[i for i in self.selected_indices if not self.cfg['elements'][i].get('locked')]
        if not ids: return
        self._push_undo()
        for i in ids:
            e=self.cfg['elements'][i]
            self._set_angle(e,0.0 if delta is None else _element_angle(e)+float(delta))
        self._commit_live('Rotated'); self.refresh_list(); self.sync_list_selection(); self.update_form(); self.render_canvas()
    def change_font_size(self,direction):
        ids=[i for i in self.selected_indices if str(self.cfg['elements'][i].get('type','')).lower()=='text' and not self.cfg['elements'][i].get('locked')]
        if not ids: return
        try: step=float(self.font_step.get())
        except Exception: step=.2
        self._push_undo()
        for i in ids:
            e=self.cfg['elements'][i]; e['font_size']=round(max(1.0,float(e.get('font_size',8))+direction*step),2)
        self._commit_live('Font size changed'); self.update_form(); self.render_canvas()
    def nudge(self,sx,sy):
        ids=[i for i in self.selected_indices if not self.cfg['elements'][i].get('locked')]
        if not ids: return
        try: step=float(self.snap_mm.get())
        except Exception: step=.1
        self._push_undo()
        for i in ids:
            e=self.cfg['elements'][i]; sign=-1 if self._fold_for_element(e) is not None else 1; dx=sx*step*sign; dy=sy*step*sign
            e['x']=self._snap(float(e.get('x',0))+dx); e['y']=self._snap(float(e.get('y',0))+dy)
            if 'x2' in e: e['x2']=self._snap(float(e.get('x2',0))+dx)
            if 'y2' in e: e['y2']=self._snap(float(e.get('y2',0))+dy)
        self._commit_live('Moved'); self.update_form(); self.render_canvas()
        try: self.app.workspace_state['designer_step']=step; self.app.save_workspace()
        except Exception: pass
    def reorder(self,delta):
        if len(self.selected_indices)!=1: return
        i=self.primary_idx; ni=i+delta
        if ni<0 or ni>=len(self.cfg.get('elements',[])): return
        self._push_undo(); els=self.cfg['elements']; els[i],els[ni]=els[ni],els[i]; self.set_selection({ni},ni); self._commit_live('Layer order changed'); self.refresh_list(); self.render_canvas()
    def set_lock_selected(self,value):
        if not self.selected_indices: return
        self._push_undo()
        for i in self.selected_indices: self.cfg['elements'][i]['locked']=bool(value)
        self._commit_live('Locked' if value else 'Unlocked'); self.refresh_list(); self.update_form(); self.render_canvas()
    def unlock_all(self):
        if not any(e.get('locked') for e in self.cfg.get('elements',[])): return
        self._push_undo()
        for e in self.cfg.get('elements',[]): e['locked']=False
        self._commit_live('All elements unlocked'); self.refresh_list(); self.render_canvas()
    def delete_selected(self):
        if not self.selected_indices: return
        ids=[i for i in sorted(self.selected_indices,reverse=True) if not self.cfg['elements'][i].get('locked')]
        if not ids: return
        self._push_undo()
        for i in ids: self.cfg['elements'].pop(i)
        self.selected_indices=set(); self.primary_idx=None; self._commit_live('Element(s) deleted'); self.refresh_list(); self.render_canvas()
    def duplicate_selected(self):
        if not self.selected_indices: return
        self._push_undo(); new=[]
        for i in sorted(self.selected_indices):
            e=copy.deepcopy(self.cfg['elements'][i]); e['locked']=False
            e['x']=round(float(e.get('x',0))+1,3); e['y']=round(float(e.get('y',0))+1,3)
            if 'x2' in e: e['x2']=round(float(e.get('x2',0))+1,3)
            if 'y2' in e: e['y2']=round(float(e.get('y2',0))+1,3)
            self.cfg['elements'].append(e); new.append(len(self.cfg['elements'])-1)
        self.set_selection(set(new),new[-1] if new else None); self._commit_live('Duplicated'); self.refresh_list(); self.render_canvas()
    def _default_add_xy(self):
        a=self._virtual_area(); return float(a.get('x',0))+2,float(a.get('y',0))+2
    def add_text(self):
        txt=simpledialog.askstring('Add free text','Text:',initialvalue='New text',parent=self)
        if txt is None:return
        self._push_undo(); x,y=self._default_add_xy(); e={'type':'text','text':txt,'x':x,'y':y,'w':25.0,'h':4.0,'font':'Segoe UI','font_size':5.0,'bold':False,'align':'left','wrap':False,'auto_fit':False}
        self.cfg['elements'].append(e); i=len(self.cfg['elements'])-1; self.set_selection({i},i); self._commit_live('Free text added'); self.refresh_list(); self.render_canvas()
    def add_field(self):
        self.open_field_picker()

    def _add_dynamic_fields(self, fields, as_barcode=False):
        fields=[str(f).strip() for f in fields if str(f).strip()]
        if not fields:
            return
        self._push_undo(); x,y=self._default_add_xy(); new_ids=[]
        for n, field in enumerate(fields):
            yy=y+n*5.0
            if as_barcode:
                e={'type':'barcode','value':'{{'+field+'}}','x':x,'y':yy,'w':30.0,'h':7.0,'symbology':'code128','barcode_height_mm':6.5,'module_width':0.22,'quiet_zone':1.2,'show_text':False}
            else:
                e={'type':'text','text':'{{'+field+'}}','x':x,'y':yy,'w':25.0,'h':4.0,'font':'Segoe UI','font_size':5.0,'bold':False,'align':'left','wrap':False,'auto_fit':True,'min_font_size':3.0}
            self.cfg['elements'].append(e); new_ids.append(len(self.cfg['elements'])-1)
        self.set_selection(set(new_ids),new_ids[-1]); self._commit_live('Dynamic field(s) added'); self.refresh_list(); self.render_canvas()

    def open_field_picker(self):
        win=tk.Toplevel(self); win.title('Add Data Field'); win.geometry('620x520'); win.transient(self)
        frm=ttk.Frame(win,padding=10); frm.pack(fill='both',expand=True)
        ttk.Label(frm,text='Columns from the currently loaded Excel / Google Sheet',font=('Segoe UI',10,'bold')).pack(anchor='w')
        top=ttk.Frame(frm); top.pack(fill='x',pady=(8,6))
        search=tk.StringVar(); ttk.Label(top,text='Search').pack(side='left')
        ent=ttk.Entry(top,textvariable=search); ent.pack(side='left',fill='x',expand=True,padx=6)
        count_var=tk.StringVar(); ttk.Label(top,textvariable=count_var).pack(side='right')
        tree=ttk.Treeview(frm,columns=('field','sample'),show='headings',selectmode='extended')
        tree.heading('field',text='Field / Column'); tree.heading('sample',text='Sample from current row')
        tree.column('field',width=250,stretch=True); tree.column('sample',width=300,stretch=True)
        ysb=ttk.Scrollbar(frm,orient='vertical',command=tree.yview); tree.configure(yscrollcommand=ysb.set)
        body=ttk.Frame(frm); body.pack(fill='both',expand=True)
        tree.pack(in_=body,side='left',fill='both',expand=True); ysb.pack(in_=body,side='right',fill='y')
        manual=tk.StringVar(); mbar=ttk.Frame(frm); mbar.pack(fill='x',pady=(8,4))
        ttk.Label(mbar,text='Custom field').pack(side='left'); ttk.Entry(mbar,textvariable=manual).pack(side='left',fill='x',expand=True,padx=6)
        ttk.Label(frm,text='If you add a new column to Google Sheet, click Reload Source first. No JSON mapping is required; {{Column Name}} binds automatically.',foreground='#555').pack(anchor='w',pady=(2,8))

        def rows_for_filter():
            q=search.get().strip().casefold(); headers=list(getattr(self.app,'headers',[]) or [])
            row=self.app.rows[self.app.current_row_index] if getattr(self.app,'rows',[]) else {}
            out=[]
            for h in headers:
                sample=format_binding_value(str(h),resolve_row_value(row,h)) if row else ''
                if q and q not in str(h).casefold() and q not in str(sample).casefold():
                    continue
                out.append((h,sample))
            return out
        def refresh(*_):
            tree.delete(*tree.get_children()); items=rows_for_filter()
            for i,(h,v) in enumerate(items): tree.insert('', 'end', iid=str(i), values=(h,v))
            count_var.set(f'{len(items)} field(s)')
        def selected_fields():
            vals=[]
            for iid in tree.selection():
                v=tree.item(iid,'values')
                if v: vals.append(v[0])
            if not vals and manual.get().strip(): vals=[manual.get().strip().strip('{} ')]
            return vals
        def add_text_fields():
            vals=selected_fields()
            if not vals: messagebox.showinfo('Add Data Field','Select one or more fields, or enter a custom field name.',parent=win); return
            self._add_dynamic_fields(vals,False); win.destroy()
        def add_barcode_field():
            vals=selected_fields()
            if len(vals)!=1: messagebox.showinfo('Add Barcode','Select exactly one field for the barcode.',parent=win); return
            self._add_dynamic_fields(vals,True); win.destroy()
        def reload_source():
            try:
                self.app.reload_current_data_source(quiet=True)
                refresh()
            except Exception as ex: messagebox.showerror('Reload Source',str(ex),parent=win)
        search.trace_add('write',refresh)
        tree.bind('<Double-1>',lambda e:add_text_fields())
        btn=ttk.Frame(frm); btn.pack(fill='x')
        ttk.Button(btn,text='Reload Source',command=reload_source).pack(side='left')
        ttk.Button(btn,text='Cancel',command=win.destroy).pack(side='right',padx=3)
        ttk.Button(btn,text='Add as Barcode',command=add_barcode_field).pack(side='right',padx=3)
        ttk.Button(btn,text='Add as Text',command=add_text_fields).pack(side='right',padx=3)
        refresh(); ent.focus_set(); win.grab_set()
    def add_shape(self,kind):
        self._push_undo(); x,y=self._default_add_xy()
        if kind=='line': e={'type':'line','x':x,'y':y,'x2':x+20,'y2':y,'thickness':0.15}
        else: e={'type':kind,'x':x,'y':y,'w':20.0,'h':8.0,'thickness':0.15}
        self.cfg['elements'].append(e); i=len(self.cfg['elements'])-1; self.set_selection({i},i); self._commit_live('Shape added'); self.refresh_list(); self.render_canvas()
    def align_selected(self,mode):
        ids=[i for i in sorted(self.selected_indices) if not self.cfg['elements'][i].get('locked')]
        if len(ids)<2:return
        boxes={i:self._source_box(self.cfg['elements'][i]) for i in ids}; self._push_undo()
        if mode=='left': target=min(b[0] for b in boxes.values())
        elif mode=='top': target=min(b[1] for b in boxes.values())
        elif mode=='hcenter': target=sum(b[0]+b[2]/2 for b in boxes.values())/len(boxes)
        else: target=sum(b[1]+b[3]/2 for b in boxes.values())/len(boxes)
        for i in ids:
            e=self.cfg['elements'][i]; x,y,w,h=boxes[i]
            if mode=='left': dx=target-x; dy=0
            elif mode=='top': dx=0; dy=target-y
            elif mode=='hcenter': dx=target-(x+w/2); dy=0
            else: dx=0; dy=target-(y+h/2)
            e['x']=self._snap(float(e.get('x',0))+dx); e['y']=self._snap(float(e.get('y',0))+dy)
            if 'x2' in e:e['x2']=self._snap(float(e.get('x2',0))+dx)
            if 'y2' in e:e['y2']=self._snap(float(e.get('y2',0))+dy)
        self._commit_live('Aligned'); self.render_canvas()

    # ---------- virtual area & fold ----------
    def select_virtual_area(self):
        a=self._virtual_area(); a['show']=True; self.cfg['virtual_print_area']=a; self._commit_live('Virtual area visible'); self.render_canvas()
        self.coord_var.set('Drag the GREEN BORDER to move. Drag a green corner handle to resize. It is guide-only.')
    def _first_fold(self):
        for fr in self.cfg.get('fold_regions',[]):
            if fr.get('enabled',True) and int(fr.get('angle',180))%360==180:return fr
        return None
    def ensure_fold_line(self):
        fr=self._first_fold()
        if fr is None:
            self._push_undo(); pw=float(self.cfg.get('width_mm',56)); ph=float(self.cfg.get('height_mm',83)); y=ph/2
            fr={'name':'LOWER_FACE','x':0.0,'y':y,'w':pw,'h':ph-y,'angle':180,'enabled':True}; self.cfg.setdefault('fold_regions',[]).append(fr); self._commit_live('Fold region added'); self.render_canvas()
        self.coord_var.set('Drag the ORANGE FOLD line vertically. Back-face elements stay visually fixed; only the fold boundary changes.')

    # ---------- save/load/test ----------
    def test_print(self):
        self.app.set_template_cfg(self.cfg)
        try:self.app.save_working_copy(self.cfg)
        except Exception:pass
        self.app.print_test_current_one()
    def save_json_now(self):
        self.app.set_template_cfg(self.cfg); path=self.app.current_template_path
        try:
            if not path: return self.save_as()
            backup_template_file(path)
            with open(path,'w',encoding='utf-8') as f: json.dump(normalize_cfg(self.cfg),f,ensure_ascii=False,indent=2); f.write('\n')
            self.dirty=False; self.save_btn.config(text='Save Template'); self.app.clear_working_copy(); self.app.status.config(text=f'Saved template: {os.path.basename(path)}')
        except Exception as ex: messagebox.showerror('Save Template',str(ex),parent=self)
    def save_as(self):
        self.app.set_template_cfg(self.cfg); self.app.save_template_as_library()
        try:self.cfg=copy.deepcopy(self.app.get_template_cfg())
        except Exception:pass
        self.dirty=False; self.save_btn.config(text='Save Template'); self.app.clear_working_copy(); self.refresh_list(); self.render_canvas()
    def load_template_from_designer(self):
        if self.dirty and not messagebox.askyesno('Load Template','Current edits are live but unsaved. Load another template anyway?',parent=self): return
        path=self.app.import_template_to_library(parent=self)
        if not path:return
        self.cfg=copy.deepcopy(self.app.get_template_cfg()); self.dirty=False; self.save_btn.config(text='Save Template'); self.undo_stack.clear(); self.redo_stack.clear(); self.selected_indices=set(); self.primary_idx=None; self.refresh_list();
        if self.cfg.get('elements'): self.set_selection({0},0)
        self.app.clear_working_copy(); self.render_canvas(reset_view=True)
    def reload_saved(self):
        path=self.app.current_template_path
        if not path or not os.path.exists(path):return
        if self.dirty and not messagebox.askyesno('Reload','Discard live unsaved edits and reload saved template?',parent=self):return
        try:
            with open(path,'r',encoding='utf-8') as f:self.cfg=normalize_cfg(json.load(f))
            self.app.set_template_cfg(self.cfg); self.app.clear_working_copy(); self.dirty=False; self.save_btn.config(text='Save Template'); self.undo_stack.clear(); self.redo_stack.clear(); self.refresh_list(); self.selected_indices=set(); self.primary_idx=None
            if self.cfg.get('elements'):self.set_selection({0},0)
            self.render_canvas(); self.app.preview_current()
        except Exception as ex:messagebox.showerror('Reload',str(ex),parent=self)
    def close_dialog(self):
        try:
            self.app.workspace_state['designer_zoom']=int(self.zoom_percent.get()); self.app.workspace_state['designer_step']=float(self.snap_mm.get()); self.app.save_workspace()
        except Exception:pass
        if self.dirty:
            ans=messagebox.askyesnocancel('Unsaved template','Changes are already LIVE for printing. Save them permanently to the template before closing?',parent=self)
            if ans is None:return
            if ans:self.save_json_now()
        self.app.preview_current(); self.destroy()


# ----------------------------
# Modern look (ttk "clam" re-skinned)
# ----------------------------
UI = {
    "bg": "#f3f5f9", "card": "#ffffff", "ink": "#1b2333", "muted": "#6b7686", "line": "#d9dee8",
    "navy": "#111a2e", "accent": "#2563eb", "accent_hover": "#1d4fd0", "accent_soft": "#e6eeff",
    "ok": "#12805c", "ok_hover": "#0e6a4c", "btn": "#e9edf5", "btn_hover": "#dbe2ef", "sel": "#dbe7ff",
}

def apply_modern_theme(root):
    import tkinter.font as tkfont
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass
    families = set(tkfont.families())
    fam = next((f for f in ("Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans") if f in families), "TkDefaultFont")
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family=fam, size=10)
        except Exception:
            pass
    root.configure(background=UI["bg"])
    root.option_add("*TCombobox*Listbox.font", (fam, 10))
    root.option_add("*Menu.font", (fam, 10))
    root.option_add("*Toplevel.background", UI["bg"])
    root.option_add("*Listbox.background", "#ffffff")
    root.option_add("*Listbox.relief", "flat")
    root.option_add("*Listbox.highlightThickness", 1)
    root.option_add("*Listbox.highlightColor", UI["accent"])
    root.option_add("*Listbox.highlightBackground", UI["line"])
    root.option_add("*Listbox.selectBackground", UI["sel"])
    root.option_add("*Listbox.selectForeground", UI["ink"])
    root.option_add("*Menu.background", "#ffffff")
    root.option_add("*Menu.activeBackground", UI["sel"])
    root.option_add("*Menu.activeForeground", UI["ink"])
    st.configure(".", background=UI["bg"], foreground=UI["ink"], font=(fam, 10), bordercolor=UI["line"],
                 lightcolor=UI["bg"], darkcolor=UI["bg"], focuscolor=UI["accent"])
    st.configure("TFrame", background=UI["bg"])
    st.configure("Card.TFrame", background=UI["card"], relief="solid", borderwidth=1)
    st.configure("Header.TFrame", background=UI["navy"])
    st.configure("Header.TLabel", background=UI["navy"], foreground="#ffffff", font=(fam, 15, "bold"))
    st.configure("HeaderSub.TLabel", background=UI["navy"], foreground="#9db0d3", font=(fam, 9))
    st.configure("HeaderChip.TLabel", background="#1f2c4a", foreground="#d6e2ff", font=(fam, 9), padding=(10, 4))
    st.configure("TLabel", background=UI["bg"], foreground=UI["ink"])
    st.configure("Muted.TLabel", foreground=UI["muted"])
    st.configure("Heading.TLabel", font=(fam, 10, "bold"))
    st.configure("Status.TLabel", background=UI["card"], foreground=UI["muted"], padding=(10, 5), relief="flat")
    st.configure("TButton", background=UI["btn"], foreground=UI["ink"], padding=(10, 5), relief="flat", borderwidth=0, focusthickness=0)
    st.map("TButton", background=[("active", UI["btn_hover"]), ("pressed", UI["btn_hover"]), ("disabled", UI["bg"])],
           foreground=[("disabled", UI["muted"])])
    st.configure("Accent.TButton", background=UI["accent"], foreground="#ffffff", padding=(14, 6), font=(fam, 10, "bold"))
    st.map("Accent.TButton", background=[("active", UI["accent_hover"]), ("pressed", UI["accent_hover"])])
    st.configure("Print.TButton", background=UI["ok"], foreground="#ffffff", padding=(22, 9), font=(fam, 11, "bold"))
    st.map("Print.TButton", background=[("active", UI["ok_hover"]), ("pressed", UI["ok_hover"])])
    st.configure("TMenubutton", background=UI["btn"], foreground=UI["ink"], padding=(10, 5), relief="flat", arrowcolor=UI["ink"])
    st.map("TMenubutton", background=[("active", UI["btn_hover"])])
    st.configure("TEntry", fieldbackground="#ffffff", padding=5, bordercolor=UI["line"])
    st.configure("TCombobox", fieldbackground="#ffffff", padding=5, arrowcolor=UI["ink"])
    st.map("TCombobox", fieldbackground=[("readonly", "#ffffff")], bordercolor=[("focus", UI["accent"])])
    st.configure("TCheckbutton", background=UI["bg"])
    st.configure("TLabelframe", background=UI["bg"], bordercolor=UI["line"], relief="solid", borderwidth=1)
    st.configure("TLabelframe.Label", background=UI["bg"], foreground=UI["accent"], font=(fam, 9, "bold"))
    st.configure("TNotebook", background=UI["bg"], borderwidth=0, tabmargins=(0, 4, 0, 0))
    st.configure("TNotebook.Tab", padding=(16, 7), background=UI["btn"], foreground=UI["muted"], borderwidth=0)
    st.map("TNotebook.Tab", background=[("selected", UI["card"])], foreground=[("selected", UI["accent"])])
    st.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", rowheight=27, borderwidth=0, font=(fam, 10))
    st.configure("Treeview.Heading", background="#e8edf6", foreground=UI["ink"], font=(fam, 10, "bold"), padding=(8, 6), relief="flat")
    st.map("Treeview", background=[("selected", UI["sel"])], foreground=[("selected", UI["ink"])])
    st.map("Treeview.Heading", background=[("active", UI["btn_hover"])])
    st.configure("TScrollbar", background=UI["btn"], troughcolor=UI["bg"], bordercolor=UI["bg"], arrowcolor=UI["muted"])
    st.configure("TPanedwindow", background=UI["bg"])
    st.configure("TSeparator", background=UI["line"])
    return fam


class PaperSettingsDialog(tk.Toplevel):
    def __init__(self, parent, cfg, on_apply):
        super().__init__(parent)
        self.title("Paper / Print Settings")
        self.resizable(False, False)
        self.on_apply = on_apply
        cfg = normalize_cfg(cfg)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        self.vars = {
            "width_mm": tk.StringVar(value=str(cfg["width_mm"])),
            "height_mm": tk.StringVar(value=str(cfg["height_mm"])),
            "dpi": tk.StringVar(value=str(cfg["dpi"])),
            "orientation": tk.StringVar(value=str(cfg["orientation"])),
            "copies": tk.StringVar(value=str(cfg["copies"])),
            "offset_x_mm": tk.StringVar(value=str(cfg["offset_x_mm"])),
            "offset_y_mm": tk.StringVar(value=str(cfg["offset_y_mm"])),
        }

        fields = [
            ("Width (mm)", "width_mm"),
            ("Height (mm)", "height_mm"),
            ("DPI", "dpi"),
            ("Copies", "copies"),
            ("Offset X (mm)", "offset_x_mm"),
            ("Offset Y (mm)", "offset_y_mm"),
        ]
        for i, (label, key) in enumerate(fields):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=4)
            ttk.Entry(frm, textvariable=self.vars[key], width=24).grid(row=i, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Orientation").grid(row=6, column=0, sticky="w", pady=4)
        ttk.Combobox(frm, textvariable=self.vars["orientation"], state="readonly", values=["portrait", "landscape"], width=21).grid(row=6, column=1, sticky="ew", pady=4)

        ttk.Separator(frm).grid(row=7, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Label(frm, text="These settings affect print output.\nPreview guides are edited in Guide Settings and do not print.").grid(row=8, column=0, columnspan=2, sticky="w", pady=6)

        btns = ttk.Frame(frm)
        btns.grid(row=9, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Apply", command=self.apply).pack(side="right", padx=4)

        self.transient(parent)
        self.grab_set()

    def apply(self):
        try:
            vals = {
                "width_mm": float(self.vars["width_mm"].get()),
                "height_mm": float(self.vars["height_mm"].get()),
                "dpi": int(self.vars["dpi"].get()),
                "orientation": self.vars["orientation"].get(),
                "copies": max(1, int(self.vars["copies"].get())),
                "offset_x_mm": float(self.vars["offset_x_mm"].get()),
                "offset_y_mm": float(self.vars["offset_y_mm"].get()),
            }
            if vals["width_mm"] <= 0 or vals["height_mm"] <= 0:
                raise ValueError("Width and height must be positive.")
            if vals["dpi"] <= 0:
                raise ValueError("DPI must be positive.")
        except Exception as e:
            messagebox.showerror("Invalid settings", str(e), parent=self)
            return
        self.on_apply(vals)
        self.destroy()


class CalibrationDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Easy Calibration")
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text="No JSON editing needed. Choose what you want to move, then use the arrows."
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,10))

        self.target = tk.StringVar(value="Whole print")
        self.step = tk.StringVar(value="0.5")

        ttk.Label(frm, text="Move").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            frm,
            textvariable=self.target,
            state="readonly",
            values=["Whole print", "Top face", "Bottom face", "Guide overlay"],
            width=22
        ).grid(row=1, column=1, columnspan=3, sticky="ew", pady=4)

        ttk.Label(frm, text="Step").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Combobox(
            frm,
            textvariable=self.step,
            state="readonly",
            values=["0.1", "0.25", "0.5", "1.0", "2.0"],
            width=10
        ).grid(row=2, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="mm per click").grid(row=2, column=2, columnspan=2, sticky="w")

        arrows = ttk.Frame(frm)
        arrows.grid(row=3, column=0, columnspan=4, pady=12)

        ttk.Button(arrows, text="↑", width=7, command=lambda: self.move(0,-1)).grid(row=0,column=1,padx=3,pady=3)
        ttk.Button(arrows, text="←", width=7, command=lambda: self.move(-1,0)).grid(row=1,column=0,padx=3,pady=3)
        ttk.Button(arrows, text="●", width=7, command=self.reset_target).grid(row=1,column=1,padx=3,pady=3)
        ttk.Button(arrows, text="→", width=7, command=lambda: self.move(1,0)).grid(row=1,column=2,padx=3,pady=3)
        ttk.Button(arrows, text="↓", width=7, command=lambda: self.move(0,1)).grid(row=2,column=1,padx=3,pady=3)

        self.info = ttk.Label(frm, text="", justify="left")
        self.info.grid(row=4, column=0, columnspan=4, sticky="w", pady=(4,10))

        skewbar = ttk.Frame(frm)
        skewbar.grid(row=5, column=0, columnspan=4, sticky="w", pady=(0,8))
        ttk.Label(skewbar, text="Skew:").pack(side="left")
        ttk.Button(skewbar, text="↶ -0.1°", command=lambda: self.app.adjust_rotation(-0.1)).pack(side="left", padx=3)
        ttk.Button(skewbar, text="0°", command=lambda: self.app.set_rotation(0.0)).pack(side="left", padx=3)
        ttk.Button(skewbar, text="+0.1° ↷", command=lambda: self.app.adjust_rotation(0.1)).pack(side="left", padx=3)

        ttk.Separator(frm).grid(row=5, column=0, columnspan=4, sticky="ew", pady=8)

        ttk.Label(
            frm,
            text=(
                "Whole print = move everything physically after folding.\n"
                "Top/Bottom face = adjust only that face's design.\n"
                "Guide overlay = move the simulated die-cut guides only; it never prints.\n"
                "The center button resets Whole print offset or Guide overlay shift."
            ),
            justify="left"
        ).grid(row=6, column=0, columnspan=4, sticky="w")

        ttk.Button(frm, text="Close", command=self.destroy).grid(row=7, column=3, sticky="e", pady=(12,0))

        self.target.trace_add("write", lambda *_: self.refresh_info())
        self.refresh_info()

        self.transient(parent)
        self.grab_set()

    def current_step(self):
        return float(self.step.get())

    def refresh_info(self):
        try:
            cfg = self.app.get_template_cfg()
            target = self.target.get()
            if target == "Whole print":
                txt = (
                    f"Current whole-print offset: "
                    f"X {cfg.get('offset_x_mm',0):g} mm, "
                    f"Y {cfg.get('offset_y_mm',0):g} mm"
                )
            elif target == "Guide overlay":
                guides = cfg.get("preview_guides", [])
                txt = f"Preview-only guides: {len(guides)} item(s)"
            else:
                regions = infer_calibration_regions(cfg)
                r = regions.get(target)
                txt = (
                    f"{target}: x={r['x']:g}, y={r['y']:g}, "
                    f"w={r['w']:g}, h={r['h']:g} mm"
                    + (" (printed 180°)" if r.get("rotated") else "")
                )
            self.info.config(text=txt)
        except Exception as e:
            self.info.config(text=str(e))

    def move(self, sx, sy):
        step = self.current_step()
        self.app.calibrate_move(self.target.get(), sx*step, sy*step)
        self.refresh_info()

    def reset_target(self):
        self.app.calibrate_reset(self.target.get())
        self.refresh_info()


class GuideSettingsDialog(tk.Toplevel):
    def __init__(self, parent, cfg, on_apply):
        super().__init__(parent)
        self.title("Preview Guide Settings")
        self.geometry("920x520")
        self.on_apply = on_apply
        self.cfg = normalize_cfg(cfg)
        self.guides = copy.deepcopy(self.cfg.get("preview_guides", []))

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(main)
        right = ttk.Frame(main)
        main.add(left, weight=2)
        main.add(right, weight=3)

        ttk.Label(left, text="Preview guides (non-printing)").pack(anchor="w")

        self.listbox = tk.Listbox(left, height=20)
        self.listbox.pack(fill="both", expand=True, pady=6)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        btns = ttk.Frame(left)
        btns.pack(fill="x")
        ttk.Button(btns, text="Add Box", command=self.add_box).pack(side="left", padx=2)
        ttk.Button(btns, text="Add Line", command=self.add_line).pack(side="left", padx=2)
        ttk.Button(btns, text="Remove", command=self.remove_selected).pack(side="left", padx=2)

        form = ttk.Frame(right)
        form.pack(fill="both", expand=True)

        self.vars = {
            "name": tk.StringVar(),
            "type": tk.StringVar(value="box"),
            "color": tk.StringVar(value="red"),
            "show": tk.BooleanVar(value=True),
            "x": tk.StringVar(value="0"),
            "y": tk.StringVar(value="0"),
            "w": tk.StringVar(value="10"),
            "h": tk.StringVar(value="10"),
            "x2": tk.StringVar(value="0"),
            "y2": tk.StringVar(value="0"),
        }

        row = 0
        ttk.Label(form, text="Name").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["name"], width=28).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Type").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(form, textvariable=self.vars["type"], state="readonly", values=["box", "line"], width=25).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Color").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(form, textvariable=self.vars["color"], state="readonly", values=["red", "blue", "green", "orange", "purple", "gray", "black"], width=25).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Checkbutton(form, text="Show guide", variable=self.vars["show"]).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Separator(form).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        ttk.Label(form, text="Box / Line start X (mm)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["x"], width=28).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Box / Line start Y (mm)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["y"], width=28).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Box width (mm)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["w"], width=28).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Box height (mm)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["h"], width=28).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Line end X2 (mm)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["x2"], width=28).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Line end Y2 (mm)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["y2"], width=28).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Tip: box guides use x/y/w/h. Line guides use x/y/x2/y2.\nThese guides are preview-only and will never print.").grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 8))
        row += 1

        action = ttk.Frame(form)
        action.grid(row=row, column=0, columnspan=2, sticky="e")
        ttk.Button(action, text="Apply To Selected", command=self.apply_selected).pack(side="right", padx=4)
        ttk.Button(action, text="Done", command=self.done).pack(side="right", padx=4)

        form.columnconfigure(1, weight=1)
        self.refresh_list()

        self.transient(parent)
        self.grab_set()

    def refresh_list(self):
        self.listbox.delete(0, "end")
        for i, g in enumerate(self.guides):
            name = g.get("name") or f"Guide {i+1}"
            gtype = g.get("type", "box")
            self.listbox.insert("end", f"{i+1}. {name} [{gtype}]")
        if self.guides and not self.listbox.curselection():
            self.listbox.selection_set(0)
            self.on_select()

    def selected_index(self):
        cur = self.listbox.curselection()
        if not cur:
            return None
        return int(cur[0])

    def on_select(self, _event=None):
        idx = self.selected_index()
        if idx is None:
            return
        g = self.guides[idx]
        self.vars["name"].set(str(g.get("name", "")))
        self.vars["type"].set(str(g.get("type", "box")))
        self.vars["color"].set(str(g.get("color", "red")))
        self.vars["show"].set(bool(g.get("show", True)))
        self.vars["x"].set(str(g.get("x", 0)))
        self.vars["y"].set(str(g.get("y", 0)))
        self.vars["w"].set(str(g.get("w", 10)))
        self.vars["h"].set(str(g.get("h", 10)))
        self.vars["x2"].set(str(g.get("x2", 0)))
        self.vars["y2"].set(str(g.get("y2", 0)))

    def add_box(self):
        self.guides.append({
            "name": "New Box",
            "type": "box",
            "x": 0, "y": 0, "w": 10, "h": 10,
            "color": "red",
            "show": True
        })
        self.refresh_list()
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(len(self.guides)-1)
        self.on_select()

    def add_line(self):
        self.guides.append({
            "name": "New Line",
            "type": "line",
            "x": 0, "y": 0, "x2": 10, "y2": 0,
            "color": "blue",
            "show": True
        })
        self.refresh_list()
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(len(self.guides)-1)
        self.on_select()

    def remove_selected(self):
        idx = self.selected_index()
        if idx is None:
            return
        self.guides.pop(idx)
        self.refresh_list()

    def apply_selected(self):
        idx = self.selected_index()
        if idx is None:
            return
        try:
            g = {
                "name": self.vars["name"].get().strip(),
                "type": self.vars["type"].get().strip(),
                "color": self.vars["color"].get().strip(),
                "show": bool(self.vars["show"].get()),
                "x": float(self.vars["x"].get()),
                "y": float(self.vars["y"].get()),
                "w": float(self.vars["w"].get()),
                "h": float(self.vars["h"].get()),
                "x2": float(self.vars["x2"].get()),
                "y2": float(self.vars["y2"].get()),
            }
        except Exception as e:
            messagebox.showerror("Guide error", str(e), parent=self)
            return
        self.guides[idx] = g
        self.refresh_list()
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(idx)
        self.on_select()

    def done(self):
        self.cfg["preview_guides"] = self.guides
        self.on_apply(self.guides)
        self.destroy()


class BatchScanDialog(tk.Toplevel):
    """
    Scanner-first queue. It consumes self.app.rows already loaded from Excel/Google Sheets.
    It never fetches or modifies Google Sheets itself.
    """
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Batch Scan Queue")
        self.geometry("1240x720")
        self.minsize(980, 600)

        self.queue = []
        self.after_id = None
        self.auto_idle_ms = 350
        self.barcode_columns = []
        self.lookup = {}
        self.row_primary = {}

        self.auto_process_var = tk.BooleanVar(value=True)
        self.repeat_mode_var = tk.StringVar(value="Increase Qty")
        self.remove_after_print_var = tk.BooleanVar(value=False)
        self.scan_var = tk.StringVar()
        self.summary_var = tk.StringVar()
        self.data_info_var = tk.StringVar()

        self.build_ui()
        self.refresh_index()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<F8>", lambda e: self.scan_entry.focus_set())
        self.bind("<Escape>", lambda e: self.clear_scan_input())
        self.bind("<space>", self.space_toggle)
        self.after(80, self.scan_entry.focus_set)

    def build_ui(self):
        top = ttk.Frame(self, padding=(10, 10, 10, 4))
        top.pack(fill="x")

        ttk.Label(top, text="Scan / paste UPC:").pack(side="left")
        self.scan_entry = ttk.Entry(top, textvariable=self.scan_var, width=52, font=("Consolas", 13))
        self.scan_entry.pack(side="left", padx=(6, 5), fill="x", expand=True)
        self.scan_entry.bind("<Return>", self.on_enter)
        self.scan_entry.bind("<KeyRelease>", self.on_key_release)
        ttk.Button(top, text="Process", command=self.process_input).pack(side="left", padx=3)
        ttk.Button(top, text="Clear Input", command=self.clear_scan_input).pack(side="left", padx=3)

        options = ttk.Frame(self, padding=(10, 0, 10, 6))
        options.pack(fill="x")
        ttk.Checkbutton(options, text="Auto process after scanner idle", variable=self.auto_process_var).pack(side="left")
        ttk.Label(options, text="Repeated scan:").pack(side="left", padx=(18, 4))
        ttk.Combobox(options, textvariable=self.repeat_mode_var, state="readonly",
                     values=["Increase Qty", "Add Row"], width=14).pack(side="left")
        ttk.Checkbutton(options, text="Remove printed rows after success", variable=self.remove_after_print_var).pack(side="left", padx=(18, 4))
        ttk.Button(options, text="Refresh Data Index", command=self.refresh_index).pack(side="right")

        info = ttk.Frame(self, padding=(10, 0, 10, 6))
        info.pack(fill="x")
        ttk.Label(info, textvariable=self.data_info_var).pack(side="left")
        ttk.Label(info, textvariable=self.summary_var).pack(side="right")

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        left = ttk.Frame(main)
        right = ttk.Frame(main)
        main.add(left, weight=3)
        main.add(right, weight=2)

        cols = ("use", "barcode", "brand", "model", "price", "qty", "status")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
        headings = {
            "use": "Print", "barcode": "UPC / Barcode", "brand": "Brand", "model": "Model",
            "price": "Price", "qty": "Qty", "status": "Status"
        }
        widths = {"use":55, "barcode":150, "brand":145, "model":150, "price":125, "qty":60, "status":145}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="center" if c in ("use","qty","status") else "w")
        ysb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.double_click)

        qbar = ttk.Frame(left)
        qbar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6,0))
        ttk.Button(qbar, text="Select All", command=self.select_all).pack(side="left", padx=2)
        ttk.Button(qbar, text="Select None", command=self.select_none).pack(side="left", padx=2)
        ttk.Button(qbar, text="Toggle Print", command=self.toggle_selected).pack(side="left", padx=2)
        ttk.Button(qbar, text="Qty -", command=lambda:self.change_qty(-1)).pack(side="left", padx=(12,2))
        ttk.Button(qbar, text="Qty +", command=lambda:self.change_qty(1)).pack(side="left", padx=2)
        ttk.Button(qbar, text="Resolve Duplicate", command=self.resolve_duplicate).pack(side="left", padx=(12,2))
        ttk.Button(qbar, text="Remove", command=self.remove_selected).pack(side="left", padx=2)
        ttk.Button(qbar, text="Clear Queue", command=self.clear_queue).pack(side="left", padx=2)

        preview_top = ttk.Frame(right)
        preview_top.pack(fill="x")
        ttk.Label(preview_top, text="Selected label preview").pack(side="left")
        self.details_var = tk.StringVar(value="Scan a product to begin.")
        ttk.Label(right, textvariable=self.details_var, justify="left").pack(fill="x", pady=(5,3))
        self.preview_label = ttk.Label(right, anchor="center")
        self.preview_label.pack(fill="both", expand=True)

        bottom = ttk.Frame(self, padding=(10, 4, 10, 10))
        bottom.pack(fill="x")
        ttk.Label(bottom, text="Enter = process scan   Space = toggle selected   F8 = focus scanner   Esc = clear input").pack(side="left")
        ttk.Button(bottom, text="Close", command=self.close).pack(side="right", padx=3)
        ttk.Button(bottom, text="PRINT CHECKED", command=self.print_checked).pack(side="right", padx=3)

    def refresh_index(self):
        self.barcode_columns, self.lookup, self.row_primary = build_barcode_lookup(self.app.headers, self.app.rows)
        lengths = sorted({len(c) for c in self.lookup})
        self.data_info_var.set(
            f"Data: {len(self.app.rows)} row(s) | Barcode keys: {len(self.lookup)} | "
            f"Columns: {', '.join(map(str,self.barcode_columns)) or 'NOT FOUND'} | Lengths: {lengths or '-'}"
        )
        self.update_summary()

    def close(self):
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
        self.destroy()

    def on_enter(self, _event=None):
        if self.after_id:
            try: self.after_cancel(self.after_id)
            except Exception: pass
            self.after_id = None
        self.process_input()
        return "break"

    def on_key_release(self, event=None):
        if event and event.keysym in ("Return","Escape","Up","Down","Left","Right","Shift_L","Shift_R","Control_L","Control_R"):
            return
        if self.after_id:
            try: self.after_cancel(self.after_id)
            except Exception: pass
            self.after_id = None
        if not self.auto_process_var.get():
            return
        text = self.scan_var.get().strip()
        if not text or not self.lookup:
            return
        min_len = min((len(c) for c in self.lookup), default=8)
        # Avoid committing short manual partial input.
        if len(normalize_barcode_value(text)) < min_len:
            return
        self.after_id = self.after(self.auto_idle_ms, self.process_input)

    def clear_scan_input(self):
        self.scan_var.set("")
        self.scan_entry.focus_set()

    def process_input(self):
        if self.after_id:
            try: self.after_cancel(self.after_id)
            except Exception: pass
            self.after_id = None
        raw = self.scan_var.get()
        self.scan_var.set("")
        self.scan_entry.focus_set()
        if not raw.strip():
            return
        if not self.lookup:
            messagebox.showerror("Batch Scan", "No barcode index is available. Load Excel/Google Sheet first, then click Refresh Data Index.", parent=self)
            return

        # Explicit separators first. Each token may still itself be glued.
        tokens = [t for t in re.split(r"[\s,;|]+", raw.strip()) if t]
        if not tokens:
            tokens = [raw]
        for token in tokens:
            self.process_token(token)
        self.refresh_tree()

    def process_token(self, token):
        code = normalize_barcode_value(token)
        if not code:
            return
        if code in self.lookup:
            self.add_code(code)
            return
        status, seq = segment_concatenated_codes(code, set(self.lookup.keys()))
        if status == "unique" and seq:
            for c in seq:
                self.add_code(c)
        elif status == "ambiguous":
            self.add_unresolved(code, "AMBIGUOUS SPLIT")
        else:
            self.add_unresolved(code, "NOT FOUND")

    def add_code(self, code):
        ids = self.lookup.get(code, [])
        if len(ids) == 1:
            idx = ids[0]
            if self.repeat_mode_var.get() == "Increase Qty":
                for q in self.queue:
                    if q.get("row_index") == idx and q.get("status") == "READY":
                        q["qty"] += 1
                        q["checked"] = True
                        return
            self.queue.append({
                "code": code, "row_index": idx, "candidate_indices": [idx],
                "qty": 1, "checked": True, "status": "READY"
            })
        elif len(ids) > 1:
            self.queue.append({
                "code": code, "row_index": None, "candidate_indices": ids,
                "qty": 1, "checked": False, "status": f"DUPLICATE x{len(ids)}"
            })
        else:
            self.add_unresolved(code, "NOT FOUND")

    def add_unresolved(self, code, status):
        self.queue.append({
            "code": code, "row_index": None, "candidate_indices": [],
            "qty": 1, "checked": False, "status": status
        })

    def row_values(self, q):
        idx = q.get("row_index")
        row = self.app.rows[idx] if idx is not None and 0 <= idx < len(self.app.rows) else {}
        brand = row.get("Brand", row.get("Brand Name", ""))
        model = row.get("Model", row.get("SKU", ""))
        price = row.get("Price", "")
        return ("✓" if q.get("checked") else "", q.get("code",""), brand, model, price, q.get("qty",1), q.get("status",""))

    def refresh_tree(self):
        selected = [int(i) for i in self.tree.selection() if str(i).isdigit()]
        self.tree.delete(*self.tree.get_children())
        for i,q in enumerate(self.queue):
            self.tree.insert("", "end", iid=str(i), values=self.row_values(q))
        for i in selected:
            if i < len(self.queue) and self.tree.exists(str(i)):
                self.tree.selection_add(str(i))
        if self.queue and not self.tree.selection():
            last = str(len(self.queue)-1)
            self.tree.selection_set(last)
            self.tree.focus(last)
            self.tree.see(last)
        self.update_summary()
        self.update_preview()

    def update_summary(self):
        ready = sum(1 for q in self.queue if q.get("status") == "READY")
        checked = sum(1 for q in self.queue if q.get("checked") and q.get("status") == "READY")
        labels = sum(int(q.get("qty",1)) for q in self.queue if q.get("checked") and q.get("status") == "READY")
        issues = len(self.queue) - ready
        self.summary_var.set(f"Queue: {len(self.queue)} | Ready: {ready} | Checked: {checked} | Labels: {labels} | Issues: {issues}")

    def selected_indices(self):
        return sorted(int(i) for i in self.tree.selection() if str(i).isdigit())

    def on_tree_select(self, _event=None):
        self.update_preview()

    def update_preview(self):
        sels = self.selected_indices()
        if not sels:
            self.preview_label.config(image="")
            self.details_var.set("Select a queue row to preview.")
            return
        qi = sels[0]
        if qi >= len(self.queue):
            return
        q = self.queue[qi]
        idx = q.get("row_index")
        if idx is None:
            self.preview_label.config(image="")
            self.details_var.set(f"{q.get('code','')}\nStatus: {q.get('status','')}\nResolve or remove this row before printing.")
            return
        try:
            row = self.app.rows[idx]
            cfg = bind_row_to_template(self.app.get_template_cfg(), row)
            cfg["copies"] = max(1, int(q.get("qty",1)))
            img = render_preview_with_guides(cfg, scale=2, show_guides=False, show_fold=False)
            maxw,maxh = 440,520
            ratio = min(maxw/img.width, maxh/img.height, 1.0)
            show = img
            if ratio != 1:
                show = show.resize((int(show.width*ratio), int(show.height*ratio)), Image.Resampling.LANCZOS)
            self.tk_preview = ImageTk.PhotoImage(show)
            self.preview_label.config(image=self.tk_preview)
            brand = row.get("Brand", row.get("Brand Name", ""))
            model = row.get("Model", row.get("SKU", ""))
            self.details_var.set(f"{brand} | {model}\nUPC: {q.get('code','')} | Qty: {q.get('qty',1)} | {q.get('status','')}")
        except Exception as e:
            self.preview_label.config(image="")
            self.details_var.set(f"Preview error: {e}")

    def double_click(self, event=None):
        rowid = self.tree.identify_row(event.y) if event else ""
        if rowid:
            self.tree.selection_set(rowid)
            self.toggle_selected()

    def space_toggle(self, _event=None):
        if self.tree.focus_get() == self.scan_entry:
            return
        self.toggle_selected()
        return "break"

    def toggle_selected(self):
        for i in self.selected_indices():
            if i >= len(self.queue):
                continue
            q = self.queue[i]
            if q.get("status") == "READY":
                q["checked"] = not bool(q.get("checked"))
        self.refresh_tree()

    def select_all(self):
        for q in self.queue:
            q["checked"] = q.get("status") == "READY"
        self.refresh_tree()

    def select_none(self):
        for q in self.queue:
            q["checked"] = False
        self.refresh_tree()

    def change_qty(self, delta):
        for i in self.selected_indices():
            if i < len(self.queue) and self.queue[i].get("status") == "READY":
                self.queue[i]["qty"] = max(1, int(self.queue[i].get("qty",1)) + int(delta))
        self.refresh_tree()

    def remove_selected(self):
        ids = set(self.selected_indices())
        if not ids:
            return
        self.queue = [q for i,q in enumerate(self.queue) if i not in ids]
        self.refresh_tree()

    def clear_queue(self):
        if self.queue and not messagebox.askyesno("Clear Queue", "Remove all scanned rows?", parent=self):
            return
        self.queue = []
        self.refresh_tree()
        self.scan_entry.focus_set()

    def resolve_duplicate(self):
        sels = self.selected_indices()
        if len(sels) != 1:
            messagebox.showerror("Resolve Duplicate", "Select exactly one duplicate queue row.", parent=self)
            return
        qi = sels[0]
        q = self.queue[qi]
        candidates = q.get("candidate_indices", [])
        if len(candidates) <= 1:
            messagebox.showinfo("Resolve Duplicate", "This row is not an unresolved duplicate.", parent=self)
            return

        win = tk.Toplevel(self)
        win.title(f"Resolve UPC {q.get('code','')}")
        win.geometry("760x360")
        cols = ("row","brand","model","price")
        tree = ttk.Treeview(win, columns=cols, show="headings", selectmode="browse")
        for c,w in [("row",70),("brand",180),("model",200),("price",150)]:
            tree.heading(c,text=c.title()); tree.column(c,width=w)
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for idx in candidates:
            row = self.app.rows[idx]
            tree.insert("", "end", iid=str(idx), values=(idx+2, row.get("Brand",row.get("Brand Name","")), row.get("Model",row.get("SKU","")), row.get("Price","")))

        def choose():
            sel = tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            q["row_index"] = idx
            q["candidate_indices"] = [idx]
            q["status"] = "READY"
            q["checked"] = True
            win.destroy()
            self.refresh_tree()

        bar = ttk.Frame(win); bar.pack(fill="x", padx=10, pady=(0,10))
        ttk.Button(bar, text="Use Selected", command=choose).pack(side="right", padx=3)
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right", padx=3)
        tree.bind("<Double-1>", lambda e: choose())
        win.transient(self)
        win.grab_set()

    def checked_ready(self):
        return [q for q in self.queue if q.get("checked") and q.get("status") == "READY" and q.get("row_index") is not None]

    def print_checked(self):
        items = self.checked_ready()
        if not items:
            messagebox.showerror("Batch Scan", "No READY queue rows are checked for printing.", parent=self)
            return
        try:
            printer = self.app.validate_printer()
            base_cfg = self.app.get_template_cfg()

            errors = []
            warnings = []
            prepared = []
            for n,q in enumerate(items, start=1):
                row = self.app.rows[q["row_index"]]
                cfg = bind_row_to_template(base_cfg, row)
                # Batch scan Qty intentionally overrides the source row's Copies value.
                cfg["copies"] = max(1, int(q.get("qty",1)))
                es, ws = preflight_checks(cfg)
                if es:
                    errors.append(f"{q.get('code','')}: " + "; ".join(es[:3]))
                warnings.extend([f"{q.get('code','')}: {w}" for w in ws[:3]])
                prepared.append((q,row,cfg))

            if errors:
                messagebox.showerror("Batch preflight failed", "Cannot print:\n- " + "\n- ".join(errors[:12]), parent=self)
                return
            if warnings:
                msg = "Warnings:\n- " + "\n- ".join(warnings[:10])
                if len(warnings) > 10:
                    msg += f"\n...and {len(warnings)-10} more warning(s)."
                if not messagebox.askyesno("Batch preflight warnings", msg + "\n\nContinue?", parent=self):
                    return

            total_labels = sum(cfg.get("copies",1) for _,_,cfg in prepared)
            route_note = "Virtual/driver output may open one save/driver dialog per queued product." if is_virtual_printer_name(printer) else "Physical printer uses the existing highest-quality print route."
            if not messagebox.askyesno(
                "Print Batch Scan Queue",
                f"Printer: {printer}\nProducts: {len(prepared)}\nTotal labels: {total_labels}\n\n{route_note}\n\nContinue?",
                parent=self
            ):
                return

            printed_q_ids = set()
            for n,(q,row,cfg) in enumerate(prepared, start=1):
                self.app.print_cfg(cfg, printer)
                self.app.history_record(cfg, printer, row, "Batch Scan Queue")
                printed_q_ids.add(id(q))
                self.app.status.config(text=f"Batch Scan printing {n}/{len(prepared)}...")
                self.app.root.update_idletasks()
                self.update_idletasks()

            if self.remove_after_print_var.get():
                self.queue = [q for q in self.queue if id(q) not in printed_q_ids]
                self.refresh_tree()

            self.app.status.config(text=f"Batch Scan finished: {len(prepared)} product(s), {total_labels} label(s).")
            messagebox.showinfo("Batch Scan", f"Finished sending {len(prepared)} product(s) / {total_labels} label(s).", parent=self)
            self.scan_entry.focus_set()
        except Exception as e:
            messagebox.showerror("Batch Scan print error", str(e), parent=self)

# ----------------------------
# Main app
# ----------------------------
class App:
    def __init__(self, root):
        self.root = root
        apply_modern_theme(root)
        self.root.title("ECG Label Tool v21 — Rotate • Compare • Saved Sheets")
        self.workspace_state = load_workspace_state()
        try:
            self.root.geometry(self.workspace_state.get("window_geometry") or "1600x920")
        except Exception:
            self.root.geometry("1600x920")

        self.rows = []
        self.headers = []
        self.filtered_indices = []
        self.current_row_index = 0
        self.workbook = None
        self.google_sheet_url = self.workspace_state.get("google_sheet_url")
        if self.google_sheet_url and not any(_sheet_key(x["url"]) == _sheet_key(self.google_sheet_url) for x in load_sources()["sheets"]):
            remember_google_source(self.google_sheet_url, self.workspace_state.get("google_sheet_tab", "LABEL DATA"))
        self.template_files = []
        self.current_template_path = None
        self.session_dir = create_session_dir()
        self.save_history_var = tk.BooleanVar(value=bool(self.workspace_state.get("save_history", True)))
        self.history_rows = []
        self.last_printer_info = None
        self.quick_scan_var = tk.StringVar()
        self.quick_scan_status_var = tk.StringVar(value="Load data, then scan UPC/EAN.")
        self.instant_print_var = tk.BooleanVar(value=bool(self.workspace_state.get("instant_print", False)))
        self.quick_scan_auto_var = tk.BooleanVar(value=True)
        self.quick_scan_qty_var = tk.IntVar(value=1)
        self.quick_scan_after_id = None
        self.last_scanned_row_index = None

        # ---------------- Header ----------------
        header = ttk.Frame(root, style="Header.TFrame", padding=(16, 10))
        header.pack(fill="x")
        titlebox = ttk.Frame(header, style="Header.TFrame"); titlebox.pack(side="left")
        ttk.Label(titlebox, text="ECG Label Tool", style="Header.TLabel").pack(anchor="w")
        ttk.Label(titlebox, text="v21 · design, rotate, compare with the real printer", style="HeaderSub.TLabel").pack(anchor="w")
        self.source_chip_var = tk.StringVar(value="No data loaded")
        ttk.Label(header, textvariable=self.source_chip_var, style="HeaderChip.TLabel").pack(side="right")
        self.template_chip_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.template_chip_var, style="HeaderChip.TLabel").pack(side="right", padx=8)

        # ---------------- Quick setup bar ----------------
        top = ttk.Frame(root, padding=(12, 10, 12, 4))
        top.pack(fill="x")

        ttk.Label(top, text="Template").pack(side="left")
        self.template_combo = ttk.Combobox(top, width=24, state="readonly")
        self.template_combo.pack(side="left", padx=(5,3))
        self.template_combo.bind("<<ComboboxSelected>>", self.load_selected_template)
        ttk.Button(top, text="Open...", command=self.import_template_to_library).pack(side="left", padx=2)
        ttk.Button(top, text="Save", command=self.save_template_current).pack(side="left", padx=2)
        ttk.Button(top, text="Save As", command=self.save_template_as_library).pack(side="left", padx=2)
        ttk.Button(top, text="Library", command=self.open_template_library_folder).pack(side="left", padx=2)

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=8)
        data_btn = ttk.Menubutton(top, text="Data ▾", style="Accent.TButton")
        data_menu = tk.Menu(data_btn, tearoff=False, postcommand=lambda: self.build_sources_menu(data_menu))
        data_btn["menu"] = data_menu
        data_btn.pack(side="left", padx=2)
        ttk.Button(top, text="Reload Data", command=self.reload_current_data_source).pack(side="left", padx=2)
        self.data_fields_btn = ttk.Button(top, text="Fields (0)", command=self.show_data_fields)
        self.data_fields_btn.pack(side="left", padx=2)
        ttk.Label(top, text="Sheet").pack(side="left", padx=(8,3))
        self.sheet_combo = ttk.Combobox(top, width=13, state="readonly")
        self.sheet_combo.pack(side="left")
        self.sheet_combo.bind("<<ComboboxSelected>>", self.load_sheet)

        advanced = ttk.Menubutton(top, text="Advanced")
        advanced_menu = tk.Menu(advanced, tearoff=False)
        advanced_menu.add_command(label="Open JSON (temporary)...", command=self.open_json)
        advanced_menu.add_command(label="JSON Editor", command=lambda: self.tabs.select(1))
        advanced_menu.add_separator()
        advanced_menu.add_command(label="Paper Settings", command=self.paper_settings)
        advanced_menu.add_command(label="Virtual Print Area (Guide)", command=self.printable_area_settings)
        advanced_menu.add_command(label="Print Quality", command=self.print_quality_settings)
        advanced_menu.add_command(label="Guide Settings", command=self.guide_settings)
        advanced_menu.add_command(label="Designer", command=self.open_designer)
        advanced_menu.add_separator()
        advanced_menu.add_command(label="Calibration", command=self.open_calibration)
        advanced_menu.add_command(label="Calibration Profiles", command=self.printer_profiles)
        advanced_menu.add_command(label="Preflight", command=self.run_preflight)
        advanced_menu.add_separator()
        advanced_menu.add_command(label="History", command=self.show_history)
        advanced_menu.add_command(label="Print via Driver / Virtual", command=self.print_via_driver_current)
        advanced["menu"] = advanced_menu
        advanced.pack(side="right", padx=3)

        # ---------------- Printer + tests ----------------
        printbar = ttk.Frame(root, padding=(12, 2, 12, 6))
        printbar.pack(fill="x")
        ttk.Label(printbar, text="Printer").pack(side="left")
        self.printer_combo = ttk.Combobox(printbar, width=31, state="readonly")
        self.printer_combo.pack(side="left", padx=(5,3))
        ttk.Button(printbar, text="Refresh", command=self.refresh_printers).pack(side="left", padx=2)
        ttk.Button(printbar, text="Printer Info", command=self.sync_printer).pack(side="left", padx=2)
        ttk.Button(printbar, text="Calibration", command=self.open_calibration).pack(side="left", padx=(8,2))
        ttk.Button(printbar, text="Profiles", command=self.printer_profiles).pack(side="left", padx=2)

        tests = ttk.Menubutton(printbar, text="Test Print ▾")
        tests_menu = tk.Menu(tests, tearoff=False)
        tests_menu.add_command(label="Current Label - 1 copy", command=self.print_test_current_one)
        tests_menu.add_command(label="Calibration Grid", command=self.print_test_pattern)
        tests_menu.add_command(label="Text Quality", command=self.print_text_quality_test)
        tests_menu.add_command(label="Threshold Sweep (130/140/150/160)", command=self.print_threshold_sweep)
        tests_menu.add_command(label="Barcode Quality", command=self.print_barcode_quality_test)
        tests_menu.add_separator()
        tests_menu.add_command(label="Compare Sheet — raw printer (rulers, no compensation)", command=lambda: self.print_compare_sheet(False))
        tests_menu.add_command(label="Compare Sheet — with current compensation", command=lambda: self.print_compare_sheet(True))
        tests_menu.add_command(label="Current label + ruler overlay", command=self.print_ruler_overlay)
        tests_menu.add_command(label="Measure & Apply Compensation...", command=self.measure_compensation_dialog)
        tests_menu.add_separator()
        tests_menu.add_command(label="PDF Proof", command=self.pdf_proof_current)
        tests_menu.add_command(label="Printer Proof", command=self.printer_proof)
        tests["menu"] = tests_menu
        tests.pack(side="left", padx=(8,2))

        ttk.Button(printbar, text="🖨  PRINT CURRENT", style="Print.TButton", command=self.print_current).pack(side="right", padx=2)
        ttk.Button(printbar, text="Batch Scan (F8)", command=self.open_batch_scan).pack(side="right", padx=2)

        # ---------------- Scanner-first strip ----------------
        scanbar = ttk.LabelFrame(root, text="Quick Scan", padding=(10,8))
        scanbar.pack(fill="x", padx=12, pady=(1,8))
        ttk.Label(scanbar, text="UPC / EAN").pack(side="left")
        self.quick_scan_entry = ttk.Entry(scanbar, textvariable=self.quick_scan_var, width=32, font=("Consolas", 13))
        self.quick_scan_entry.pack(side="left", padx=(6,4))
        self.quick_scan_entry.bind("<Return>", self.quick_scan_enter)
        self.quick_scan_entry.bind("<KeyRelease>", self.quick_scan_key_release)
        ttk.Label(scanbar, text="Qty").pack(side="left", padx=(7,2))
        ttk.Spinbox(scanbar, from_=1, to=99, textvariable=self.quick_scan_qty_var, width=4).pack(side="left")
        ttk.Checkbutton(scanbar, text="Auto detect", variable=self.quick_scan_auto_var).pack(side="left", padx=(8,2))
        ttk.Checkbutton(scanbar, text="INSTANT PRINT", variable=self.instant_print_var).pack(side="left", padx=(8,2))
        ttk.Button(scanbar, text="Process", command=self.process_quick_scan).pack(side="left", padx=(8,2))
        ttk.Button(scanbar, text="Print Last", command=self.print_last_scanned).pack(side="left", padx=2)
        ttk.Label(scanbar, textvariable=self.quick_scan_status_var).pack(side="left", padx=(12,2), fill="x", expand=True)

        main = ttk.Panedwindow(root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        left = ttk.Frame(main)
        right = ttk.Frame(main)
        main.add(left, weight=3)
        main.add(right, weight=2)

        gridbar = ttk.Frame(left)
        gridbar.pack(fill="x", pady=(0, 4))
        ttk.Button(gridbar, text="◀ Previous", command=self.prev_row).pack(side="left", padx=2)
        ttk.Button(gridbar, text="Next ▶", command=self.next_row).pack(side="left", padx=2)
        ttk.Button(gridbar, text="Preview Current", command=self.preview_current).pack(side="left", padx=(12, 2))
        ttk.Button(gridbar, text="Batch Scan (F8)", command=self.open_batch_scan).pack(side="left", padx=(12, 2))
        self.row_label = ttk.Label(gridbar, text="No data loaded")
        self.row_label.pack(side="left", padx=12)

        searchbar = ttk.Frame(left)
        searchbar.pack(fill="x", pady=(0, 5))
        ttk.Label(searchbar, text="Search UPC / Model / Brand:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(searchbar, textvariable=self.search_var, width=42)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", self.apply_search)
        self.search_entry.bind("<Return>", self.search_enter)
        ttk.Button(searchbar, text="Clear", command=self.clear_search).pack(side="left", padx=2)
        self.search_status = ttk.Label(searchbar, text="")
        self.search_status.pack(side="left", padx=10)

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(tree_frame, show="headings", selectmode="extended")
        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.tag_configure("odd", background="#f6f8fc")
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.bind("<Double-1>", lambda e: self.preview_current())

        # Right area now uses tabs, so editor never covers preview.
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)

        preview_tab = ttk.Frame(self.tabs)
        json_tab = ttk.Frame(self.tabs)
        self.tabs.add(preview_tab, text="Preview")
        self.tabs.add(json_tab, text="JSON Editor")

        preview_top = ttk.Frame(preview_tab)
        preview_top.pack(fill="x", padx=6, pady=(6, 0))
        self.show_guides_var = tk.BooleanVar(value=True)
        self.show_fold_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(preview_top, text="Show preview guides", variable=self.show_guides_var, command=self.preview_current).pack(side="left", padx=4)
        ttk.Checkbutton(preview_top, text="Show fold regions", variable=self.show_fold_var, command=self.preview_current).pack(side="left", padx=4)
        self.show_rulers_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(preview_top, text="Rulers (mm)", variable=self.show_rulers_var, command=self.preview_current).pack(side="left", padx=4)
        ttk.Button(preview_top, text="Drag Edit Layout", style="Accent.TButton", command=self.open_designer).pack(side="right", padx=4)

        self.preview_label = ttk.Label(preview_tab, anchor="center")
        self.preview_label.pack(fill="both", expand=True, padx=6, pady=6)

        json_toolbar = ttk.Frame(json_tab)
        json_toolbar.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Label(json_toolbar, text="Template JSON editor").pack(side="left")
        ttk.Button(json_toolbar, text="Format JSON", command=self.format_json).pack(side="right", padx=3)
        ttk.Button(json_toolbar, text="Apply + Drag Edit", command=self.apply_json_and_design).pack(side="right", padx=3)

        self.json_text = tk.Text(json_tab, wrap="none", font=("Consolas", 10), undo=True, background="#ffffff", relief="flat", highlightthickness=1, highlightbackground=UI["line"])
        self.json_text.pack(fill="both", expand=True, padx=6, pady=6)

        self.status = ttk.Label(root, text="Ready", style="Status.TLabel")
        self.status.pack(fill="x", side="bottom")

        self.load_templates(select_name=self.workspace_state.get("last_template"))
        self.recover_working_copy()
        self.refresh_printers()
        last_printer = self.workspace_state.get("last_printer")
        if last_printer and last_printer in list(self.printer_combo["values"]):
            self.printer_combo.set(last_printer)
        self.printer_combo.bind("<<ComboboxSelected>>", lambda e: self.save_workspace())
        self.after_restore_last_data_source()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_app)
        self.root.bind("<Control-p>", lambda e: self.print_current())
        self.root.bind("<Control-P>", lambda e: self.print_current())
        self.root.bind("<F8>", lambda e: self.open_batch_scan())
        self.root.bind("<F7>", lambda e: self.quick_scan_entry.focus_set())



    def save_workspace(self):
        try:
            self.workspace_state['window_geometry']=self.root.geometry()
            self.workspace_state['last_template']=self.template_combo.get().strip()
            self.workspace_state['last_printer']=self.printer_combo.get().strip()
            self.workspace_state['instant_print']=bool(self.instant_print_var.get())
            self.workspace_state['save_history']=bool(self.save_history_var.get())
            if self.google_sheet_url:self.workspace_state['google_sheet_url']=self.google_sheet_url
            save_workspace_state(self.workspace_state)
        except Exception:
            pass

    def save_working_copy(self,cfg):
        try:
            with open(working_copy_path(),'w',encoding='utf-8') as f:
                json.dump(normalize_cfg(cfg),f,ensure_ascii=False,indent=2)
            self.workspace_state['working_dirty']=True
            self.workspace_state['working_template']=self.template_combo.get().strip()
            self.save_workspace()
        except Exception:
            pass

    def clear_working_copy(self):
        self.workspace_state['working_dirty']=False
        self.workspace_state.pop('working_template',None)
        try:
            if os.path.exists(working_copy_path()): os.remove(working_copy_path())
        except Exception: pass
        self.save_workspace()

    def recover_working_copy(self):
        if not self.workspace_state.get('working_dirty') or not os.path.exists(working_copy_path()): return
        wanted=self.workspace_state.get('working_template','')
        if wanted and wanted != self.template_combo.get().strip(): return
        try:
            with open(working_copy_path(),'r',encoding='utf-8') as f: cfg=normalize_cfg(json.load(f))
            self.set_template_cfg(cfg)
            self.status.config(text='Recovered unsaved live layout from the previous session. Save Template when ready.')
        except Exception: pass

    def after_restore_last_data_source(self):
        self.root.after(250,self.restore_last_data_source)

    def restore_last_data_source(self):
        source=self.workspace_state.get('data_source')
        if source=='google' and self.workspace_state.get('google_sheet_url'):
            try:
                self.reload_current_data_source(quiet=True)
                self.status.config(text=f"Restored Google Sheet: {self.workspace_state.get('google_sheet_tab','LABEL DATA')}")
                return
            except Exception as ex:
                self.status.config(text=f"Could not reach the saved Google Sheet ({ex}). Pick it again from Data ▾ when online.")
        p=self.workspace_state.get('last_excel_path')
        if p and os.path.exists(p):
            try:
                self.workbook=load_workbook(p,data_only=True,read_only=True)
                self.sheet_combo['values']=self.workbook.sheetnames
                sheet=self.workspace_state.get('last_sheet')
                if sheet in self.workbook.sheetnames:self.sheet_combo.set(sheet)
                elif self.workbook.sheetnames:self.sheet_combo.current(0)
                self.load_sheet(); self.update_data_fields_status(); self.status.config(text=f'Restored data source: {os.path.basename(p)}')
            except Exception: pass

    def on_close_app(self):
        self.save_workspace()
        self.root.destroy()

    def open_batch_scan(self):
        if not self.rows:
            messagebox.showerror(
                "Batch Scan",
                "Load Excel or Google Sheet first. Batch Scan uses the data already loaded in the main app."
            )
            return
        columns = detect_barcode_columns(self.headers)
        if not columns:
            messagebox.showerror(
                "Batch Scan",
                "No Barcode / UPC / EAN column was found in the loaded data."
            )
            return
        BatchScanDialog(self.root, self)

    # ---------- template ----------
    def template_dir(self):
        return ensure_persistent_library()

    def open_template_library_folder(self):
        td = self.template_dir()
        try:
            if os.name == "nt":
                os.startfile(td)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", td])
        except Exception as e:
            messagebox.showinfo("Template Library", td, parent=self.root)

    def import_template_to_library(self, parent=None):
        """Load a JSON template and copy it into the persistent library used across app updates."""
        parent = parent or self.root
        p = filedialog.askopenfilename(parent=parent, title="Load Template", filetypes=[("JSON template", "*.json"), ("All files", "*.*")])
        if not p:
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                cfg = normalize_cfg(json.load(f))
        except Exception as e:
            messagebox.showerror("Load Template", f"Invalid JSON template:\n{e}", parent=parent)
            return None

        td = self.template_dir()
        name = safe_filename(os.path.basename(p))
        if not name.lower().endswith(".json"):
            name += ".json"
        dest = os.path.join(td, name)
        if os.path.exists(dest) and os.path.abspath(dest) != os.path.abspath(p):
            ans = messagebox.askyesnocancel("Template already exists", f"'{name}' already exists in your persistent template library.\n\nYes = replace it\nNo = save as a new name", parent=parent)
            if ans is None:
                return None
            if not ans:
                stem, ext = os.path.splitext(name)
                new_name = simpledialog.askstring("Template name", "Save imported template as:", initialvalue=stem + "_copy", parent=parent)
                if not new_name:
                    return None
                name = safe_filename(new_name)
                if not name.lower().endswith(".json"):
                    name += ".json"
                dest = os.path.join(td, name)

        with open(dest, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        self.load_templates(select_name=name)
        self.current_template_path = dest
        self.template_combo.set(name)
        self.load_json_file(dest)
        self.preview_current()
        self.status.config(text=f"Template loaded into persistent library: {name}")
        return dest

    def save_template_current(self):
        """Save the active JSON back into the selected template file."""
        try:
            cfg = self.get_template_cfg()
            path = self.current_template_path
            if not path or os.path.dirname(os.path.abspath(path)) != os.path.abspath(self.template_dir()):
                return self.save_template_as_library()
            backup_template_file(path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
                f.write("\n")
            self.clear_working_copy()
            self.status.config(text=f"Template saved: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save Template", str(e))

    def save_template_as_library(self):
        try:
            cfg = self.get_template_cfg()
        except Exception as e:
            messagebox.showerror("Save Template", str(e))
            return
        initial = os.path.splitext(os.path.basename(self.current_template_path or "ECG_Label"))[0]
        name = simpledialog.askstring("Save Template As", "Template name:", initialvalue=initial, parent=self.root)
        if not name:
            return
        name = safe_filename(name)
        if not name.lower().endswith(".json"):
            name += ".json"
        path = os.path.join(self.template_dir(), name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
                f.write("\n")
            self.load_templates(select_name=name)
            self.current_template_path = path
            self.load_json_file(path)
            self.clear_working_copy()
            self.preview_current()
            self.status.config(text=f"Template saved to library: {name}")
        except Exception as e:
            messagebox.showerror("Save Template", str(e))

    def printable_area_settings(self):
        """Edit a virtual/reference area. This never clips print output."""
        try:
            cfg = self.get_template_cfg()
        except Exception as e:
            messagebox.showerror("Virtual Print Area", str(e)); return
        area = dict(cfg.get("virtual_print_area") or {})
        area.setdefault("show", True); area.setdefault("x",0.0); area.setdefault("y",0.0)
        area.setdefault("w", cfg.get("width_mm",50)); area.setdefault("h", cfg.get("height_mm",68))

        win = tk.Toplevel(self.root); win.title("Virtual Print Area (Guide Only)"); win.resizable(False, False)
        frm = ttk.Frame(win, padding=12); frm.pack(fill="both", expand=True)
        show = tk.BooleanVar(value=bool(area.get("show",True)))
        vals = {k: tk.StringVar(value=str(area.get(k,0))) for k in ("x","y","w","h")}
        ttk.Label(frm, text="Reference only — this area does NOT clip printing.", font=("Segoe UI",9,"bold")).grid(row=0,column=0,columnspan=2,sticky="w",pady=(0,8))
        ttk.Checkbutton(frm, text="Show virtual print area", variable=show).grid(row=1,column=0,columnspan=2,sticky="w",pady=(0,8))
        labels = [("X (mm)","x"),("Y (mm)","y"),("Width (mm)","w"),("Height (mm)","h")]
        for r,(lab,key) in enumerate(labels, start=2):
            ttk.Label(frm,text=lab).grid(row=r,column=0,sticky="w",pady=3)
            ttk.Entry(frm,textvariable=vals[key],width=12).grid(row=r,column=1,sticky="ew",pady=3)

        def use_printable_guide():
            guides = cfg.get("preview_guides",[])
            g = next((g for g in guides if str(g.get("type","")).lower()=="box" and "print" in str(g.get("name","")).lower()), None)
            if not g:
                messagebox.showerror("Virtual Print Area", "No preview box with 'print' in its name was found.", parent=win); return
            for key in ("x","y","w","h"):
                vals[key].set(str(g.get(key,0)))
            show.set(True)

        def apply():
            try:
                a={"show":bool(show.get())}
                for key in ("x","y","w","h"): a[key]=float(vals[key].get())
                if a["w"]<=0 or a["h"]<=0: raise ValueError("Width and height must be greater than 0.")
                c=self.get_template_cfg(); c["virtual_print_area"]=a; self.set_template_cfg(c); self.preview_current(); win.destroy()
                self.status.config(text=f"Virtual print guide: {'ON' if a['show'] else 'OFF'} | {a['x']:g},{a['y']:g} {a['w']:g}×{a['h']:g} mm | no clipping")
            except Exception as e: messagebox.showerror("Virtual Print Area", str(e), parent=win)

        ttk.Button(frm,text="Use existing Print preview guide",command=use_printable_guide).grid(row=6,column=0,columnspan=2,sticky="ew",pady=(8,3))
        bar=ttk.Frame(frm); bar.grid(row=7,column=0,columnspan=2,sticky="ew",pady=(8,0))
        ttk.Button(bar,text="Cancel",command=win.destroy).pack(side="right",padx=3)
        ttk.Button(bar,text="Apply",command=apply).pack(side="right",padx=3)
        win.transient(self.root); win.grab_set()

    def print_quality_settings(self):
        try:
            cfg=self.get_template_cfg()
        except Exception as e:
            messagebox.showerror("Print Quality",str(e)); return
        win=tk.Toplevel(self.root); win.title("Print Quality"); win.resizable(False,False)
        frm=ttk.Frame(win,padding=12); frm.pack(fill="both",expand=True)
        threshold=tk.IntVar(value=int(cfg.get("threshold",145)))
        oversample=tk.IntVar(value=int(cfg.get("oversample",4)))
        mode=tk.StringVar(value=str(cfg.get("render_mode","thermal_crisp")))
        ttk.Label(frm,text="Thermal render").grid(row=0,column=0,sticky="w",pady=4)
        ttk.Combobox(frm,textvariable=mode,state="readonly",values=["thermal_crisp","standard"],width=18).grid(row=0,column=1,sticky="ew")
        ttk.Label(frm,text="Threshold (lower = thinner)").grid(row=1,column=0,sticky="w",pady=4)
        ttk.Spinbox(frm,from_=90,to=220,textvariable=threshold,width=8).grid(row=1,column=1,sticky="w")
        ttk.Label(frm,text="Oversample").grid(row=2,column=0,sticky="w",pady=4)
        ttk.Spinbox(frm,from_=1,to=6,textvariable=oversample,width=8).grid(row=2,column=1,sticky="w")
        ttk.Label(frm,text="Recommended for 300 DPI: threshold 135–155, oversample 4.").grid(row=3,column=0,columnspan=2,sticky="w",pady=(8,4))
        def apply():
            c=self.get_template_cfg(); c["threshold"]=int(threshold.get()); c["oversample"]=int(oversample.get()); c["render_mode"]=mode.get(); self.set_template_cfg(c); self.preview_current(); win.destroy()
            self.status.config(text=f"Print quality: {mode.get()} | threshold {threshold.get()} | {oversample.get()}x")
        bar=ttk.Frame(frm); bar.grid(row=4,column=0,columnspan=2,sticky="ew",pady=(8,0))
        ttk.Button(bar,text="Cancel",command=win.destroy).pack(side="right",padx=3)
        ttk.Button(bar,text="Apply",command=apply).pack(side="right",padx=3)
        win.transient(self.root); win.grab_set()

    def load_templates(self, select_name=None):
        td = self.template_dir()
        self.template_files = sorted([f for f in os.listdir(td) if f.lower().endswith(".json")], key=str.lower)
        self.template_combo["values"] = self.template_files
        if not self.template_files:
            return
        current = select_name or self.template_combo.get()
        if current in self.template_files:
            self.template_combo.set(current)
        else:
            self.template_combo.current(0)
        self.load_selected_template()

    def load_selected_template(self, _event=None):
        name = self.template_combo.get()
        if not name:
            return
        path = os.path.join(self.template_dir(), name)
        self.current_template_path = path
        self.load_json_file(path)
        self.preview_current()
        self.workspace_state['last_template']=name; self.save_workspace()
        self.status.config(text=f"Template loaded: {name}")
        self.refresh_chips()

    def load_json_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            s = f.read()
        self.json_text.delete("1.0", "end")
        self.json_text.insert("1.0", s)

    def open_json(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not p:
            return
        self.current_template_path = p
        self.load_json_file(p)
        self.preview_current()
        self.status.config(text=f"JSON opened: {os.path.basename(p)}")

    def save_json(self):
        try:
            cfg = self.get_template_cfg()
        except Exception as e:
            messagebox.showerror("JSON error", str(e))
            return
        initial = os.path.basename(self.current_template_path) if self.current_template_path else "template.json"
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile=initial)
        if not p:
            return
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        self.current_template_path = p
        self.status.config(text=f"JSON saved: {p}")

    def format_json(self):
        try:
            cfg = self.get_template_cfg()
            self.json_text.delete("1.0", "end")
            self.json_text.insert("1.0", json.dumps(cfg, ensure_ascii=False, indent=2))
            self.status.config(text="JSON formatted.")
        except Exception as e:
            messagebox.showerror("JSON error", str(e))

    def get_template_cfg(self):
        text = self.json_text.get("1.0", "end").strip()
        return normalize_cfg(json.loads(text))

    # ---------- paper & guides ----------
    def paper_settings(self):
        try:
            cfg = self.get_template_cfg()
        except Exception as e:
            messagebox.showerror("JSON error", str(e))
            return

        def on_apply(vals):
            cfg2 = self.get_template_cfg()
            cfg2.update(vals)
            self.json_text.delete("1.0", "end")
            self.json_text.insert("1.0", json.dumps(cfg2, ensure_ascii=False, indent=2))
            self.preview_current()
            self.status.config(text=f"Paper updated: {cfg2['width_mm']}×{cfg2['height_mm']} mm | {cfg2['orientation']}")

        PaperSettingsDialog(self.root, cfg, on_apply)

    def guide_settings(self):
        try:
            cfg = self.get_template_cfg()
        except Exception as e:
            messagebox.showerror("JSON error", str(e))
            return

        def on_apply(guides):
            cfg2 = self.get_template_cfg()
            cfg2["preview_guides"] = guides
            self.json_text.delete("1.0", "end")
            self.json_text.insert("1.0", json.dumps(cfg2, ensure_ascii=False, indent=2))
            self.preview_current()
            self.tabs.select(0)
            self.status.config(text=f"Preview guides updated: {len(guides)} guide(s)")

        GuideSettingsDialog(self.root, cfg, on_apply)


    def set_template_cfg(self, cfg):
        self.json_text.delete("1.0", "end")
        self.json_text.insert("1.0", json.dumps(normalize_cfg(cfg), ensure_ascii=False, indent=2))

    def open_calibration(self):
        try:
            self.get_template_cfg()
        except Exception as e:
            messagebox.showerror("JSON error", str(e))
            return
        self.tabs.select(0)
        CalibrationDialog(self.root, self)

    def calibrate_move(self, target, dx, dy):
        cfg = self.get_template_cfg()

        if target == "Whole print":
            cfg["offset_x_mm"] = round(float(cfg.get("offset_x_mm",0)) + dx, 3)
            cfg["offset_y_mm"] = round(float(cfg.get("offset_y_mm",0)) + dy, 3)

        elif target == "Guide overlay":
            for g in cfg.get("preview_guides", []):
                if "x" in g:
                    g["x"] = round(float(g.get("x",0)) + dx, 3)
                if "y" in g:
                    g["y"] = round(float(g.get("y",0)) + dy, 3)
                if "x2" in g:
                    g["x2"] = round(float(g.get("x2",0)) + dx, 3)
                if "y2" in g:
                    g["y2"] = round(float(g.get("y2",0)) + dy, 3)

        elif target in ("Top face", "Bottom face"):
            regions = infer_calibration_regions(cfg)
            r = regions[target]

            # Buttons always mean movement as the user sees the final printed/folded face.
            # A 180° face needs inverse source-coordinate movement.
            source_dx = -dx if r.get("rotated") else dx
            source_dy = -dy if r.get("rotated") else dy

            moved = 0
            for e in cfg.get("elements", []):
                cx, cy = element_center_mm(e)
                if point_in_region(cx, cy, r):
                    shift_element(e, source_dx, source_dy)
                    moved += 1
            self.status.config(text=f"{target}: moved {moved} element(s) by {dx:g},{dy:g} mm as printed")

        self.set_template_cfg(cfg)
        self.preview_current()

    def calibrate_reset(self, target):
        cfg = self.get_template_cfg()
        if target == "Whole print":
            cfg["offset_x_mm"] = 0.0
            cfg["offset_y_mm"] = 0.0
            self.set_template_cfg(cfg)
            self.preview_current()
            self.status.config(text="Whole print offset reset to 0,0 mm")
        elif target == "Guide overlay":
            # Reload only guide positions from the saved template file if available.
            if self.current_template_path and os.path.exists(self.current_template_path):
                try:
                    with open(self.current_template_path, "r", encoding="utf-8") as f:
                        saved = normalize_cfg(json.load(f))
                    cfg["preview_guides"] = copy.deepcopy(saved.get("preview_guides", []))
                    self.set_template_cfg(cfg)
                    self.preview_current()
                    self.status.config(text="Guide overlay restored from saved JSON")
                except Exception as e:
                    messagebox.showerror("Reset guide error", str(e))
        else:
            messagebox.showinfo(
                "Face reset",
                "Top/Bottom face movement changes the element coordinates directly.\n"
                "To undo those changes, reload the saved template or use Ctrl+Z in JSON Editor."
            )



    def adjust_rotation(self, delta):
        cfg = self.get_template_cfg()
        cfg["rotation_deg"] = round(float(cfg.get("rotation_deg", 0.0)) + float(delta), 3)
        self.set_template_cfg(cfg)
        self.preview_current()
        self.status.config(text=f"Skew compensation: {cfg['rotation_deg']:.2f}°")

    def set_rotation(self, value):
        cfg = self.get_template_cfg()
        cfg["rotation_deg"] = float(value)
        self.set_template_cfg(cfg)
        self.preview_current()
        self.status.config(text=f"Skew compensation: {cfg['rotation_deg']:.2f}°")


    def apply_json_and_design(self):
        """Validate/apply JSON, refresh preview, then open the drag designer."""
        try:
            self.get_template_cfg()
        except Exception as e:
            messagebox.showerror("JSON error", str(e))
            return
        self.preview_current()
        self.tabs.select(0)
        self.open_designer()

    def open_designer(self):
        try:
            self.get_template_cfg()
        except Exception as e:
            messagebox.showerror("JSON error", str(e))
            return
        VisualDesignerDialog(self.root, self)

    def run_preflight(self, cfg=None, silent_ok=False):
        try:
            cfg = cfg or self.current_bound_cfg()
            errors, warnings = preflight_checks(cfg)
        except Exception as e:
            messagebox.showerror("Preflight error", str(e))
            return False

        if errors:
            msg = "ERRORS:\n- " + "\n- ".join(errors)
            if warnings:
                msg += "\n\nWARNINGS:\n- " + "\n- ".join(warnings[:12])
            messagebox.showerror("Preflight failed", msg)
            return False

        if warnings:
            msg = "WARNINGS:\n- " + "\n- ".join(warnings[:12])
            msg += "\n\nContinue anyway?"
            return messagebox.askyesno("Preflight warnings", msg)

        if not silent_ok:
            messagebox.showinfo("Preflight", "No blocking issues found.")
        return True

    def print_test_pattern(self):
        try:
            printer = self.validate_printer()
            cfg = make_calibration_test_cfg(self.get_template_cfg())
            if not messagebox.askyesno(
                "Calibration Test Pattern",
                f"Printer: {printer}\n"
                f"Paper: {cfg['width_mm']} x {cfg['height_mm']} mm\n"
                f"Offset: X {cfg.get('offset_x_mm',0)} / Y {cfg.get('offset_y_mm',0)} mm\n"
                f"Skew: {cfg.get('rotation_deg',0)}°\n\n"
                "This prints a 5 mm grid, border and center cross. Continue?"
            ):
                return
            self.print_cfg(cfg, printer)
            self.history_record(cfg, printer, {}, "Calibration Test")
            self.status.config(text="Calibration test pattern sent.")
        except Exception as e:
            messagebox.showerror("Test Pattern error", str(e))

    def printer_profiles(self):
        cfg = self.get_template_cfg()
        profiles = load_profiles()

        win = tk.Toplevel(self.root)
        win.title("Printer Profiles")
        win.geometry("720x460")

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)

        left = ttk.Frame(frm)
        right = ttk.Frame(frm)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right.pack(side="right", fill="y")

        ttk.Label(left, text="Saved profiles").pack(anchor="w")
        lb = tk.Listbox(left)
        lb.pack(fill="both", expand=True, pady=6)

        def refresh():
            lb.delete(0,"end")
            for name in sorted(profiles.keys()):
                lb.insert("end", name)

        name_var = tk.StringVar(value="")
        ttk.Label(right, text="Profile name").pack(anchor="w")
        ttk.Entry(right, textvariable=name_var, width=28).pack(fill="x", pady=(2,8))

        ttk.Label(
            right,
            text="A profile stores printer, paper, offset/skew, virtual print guide and thermal quality."
        ).pack(anchor="w", pady=(0,10))

        def selected_name():
            cur = lb.curselection()
            return lb.get(cur[0]) if cur else ""

        def save_current():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Profile", "Enter a profile name.", parent=win)
                return
            c = self.get_template_cfg()
            profiles[name] = {
                "printer": self.printer_combo.get().strip(),
                "width_mm": c.get("width_mm"),
                "height_mm": c.get("height_mm"),
                "dpi": c.get("dpi"),
                "orientation": c.get("orientation"),
                "offset_x_mm": c.get("offset_x_mm",0),
                "offset_y_mm": c.get("offset_y_mm",0),
                "rotation_deg": c.get("rotation_deg",0),
                "scale_x_pct": c.get("scale_x_pct",100.0),
                "scale_y_pct": c.get("scale_y_pct",100.0),
                "threshold": c.get("threshold",145),
                "render_mode": c.get("render_mode","thermal_crisp"),
                "oversample": c.get("oversample",4),
                "virtual_print_area": copy.deepcopy(c.get("virtual_print_area",{})),
            }
            save_profiles(profiles)
            refresh()
            self.status.config(text=f"Printer profile saved: {name}")

        def load_selected():
            name = selected_name()
            if not name:
                return
            p = profiles[name]
            c = self.get_template_cfg()
            for key in ("width_mm","height_mm","dpi","orientation","offset_x_mm","offset_y_mm","rotation_deg","scale_x_pct","scale_y_pct","threshold","render_mode","oversample","virtual_print_area"):
                if key in p:
                    c[key] = copy.deepcopy(p[key])
            self.set_template_cfg(c)
            if p.get("printer"):
                values = list(self.printer_combo["values"])
                if p["printer"] in values:
                    self.printer_combo.set(p["printer"])
            self.preview_current()
            self.status.config(text=f"Printer profile loaded: {name}")

        def delete_selected():
            name = selected_name()
            if not name:
                return
            if messagebox.askyesno("Delete profile", f"Delete '{name}'?", parent=win):
                profiles.pop(name, None)
                save_profiles(profiles)
                refresh()

        ttk.Button(right, text="Save Current", command=save_current).pack(fill="x", pady=3)
        ttk.Button(right, text="Load Selected", command=load_selected).pack(fill="x", pady=3)
        ttk.Button(right, text="Delete Selected", command=delete_selected).pack(fill="x", pady=3)
        ttk.Button(right, text="Close", command=win.destroy).pack(fill="x", pady=(16,3))

        lb.bind("<<ListboxSelect>>", lambda e: name_var.set(selected_name()))
        refresh()
        win.transient(self.root)
        win.grab_set()



    def _proof_pdf_path(self, cfg, prefix="proof"):
        now = datetime.datetime.now()
        row = self.rows[self.current_row_index] if self.rows else {}
        brand = row.get("Brand", row.get("Brand Name", ""))
        model = row.get("Model", row.get("SKU", ""))
        barcode_value = row.get("Barcode", row.get("UPC/EAN", row.get("UPC", row.get("EAN", ""))))
        filename = (
            prefix + "_" +
            now.strftime("%H%M%S_%f")[:10] + "_" +
            safe_filename(brand) + "_" +
            safe_filename(model) + "_" +
            safe_filename(barcode_value) + ".pdf"
        )
        return os.path.join(self.session_dir, filename)

    def pdf_proof_current(self):
        """
        Create and open the exact 1:1 PDF that corresponds to the final print raster.
        Nothing is sent to the printer.
        """
        try:
            cfg = self.current_bound_cfg()
            if not self.run_preflight(cfg, silent_ok=True):
                return

            path = self._proof_pdf_path(cfg, "PDF_PROOF")
            direct_img = save_exact_print_pdf(cfg, path)

            # Round-trip verify at exact printer DPI.
            pdf_img = rasterize_exact_print_pdf(
                path,
                int(cfg.get("dpi", DEFAULT_DPI)),
                int(cfg.get("threshold", 180))
            )
            same_size, diff, total = compare_print_rasters(direct_img, pdf_img)

            if same_size:
                pct = (diff / total * 100.0) if total else 0.0
                verification = (
                    f"Vector PDF rasterized at printer DPI: {pdf_img.width} x {pdf_img.height} dots\n"
                    f"Difference vs direct RAW path: {diff:,} / {total:,} ({pct:.4f}%)"
                )
            else:
                verification = (
                    f"Warning: PDF raster size {pdf_img.size} differs from RAW raster {direct_img.size}."
                )

            try:
                os.startfile(path)
            except Exception:
                pass

            messagebox.showinfo(
                "PDF Proof created",
                f"Vector 1:1 proof saved:\n{path}\n\n"
                f"Physical page size is exact and the master PDF is vector at {cfg.get('dpi',DEFAULT_DPI)} dpi.\n"
                f"{verification}\n\n"
                "Nothing was printed."
            )
            self.status.config(text=f"PDF Proof created: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("PDF Proof error", str(e))

    def print_via_pdf_current(self):
        """
        Optional canonical pipeline:
        bound template -> exact PDF -> rasterize PDF at printer DPI -> RAW spooler.
        Existing direct RAW Print Current is intentionally untouched.
        """
        try:
            printer = self.validate_printer()
            cfg = self.current_bound_cfg()

            if not self.run_preflight(cfg, silent_ok=True):
                return

            path = self._proof_pdf_path(cfg, "PRINT_PDF")
            direct_img = save_exact_print_pdf(cfg, path)
            pdf_img = rasterize_exact_print_pdf(
                path,
                int(cfg.get("dpi", DEFAULT_DPI)),
                int(cfg.get("threshold", 180))
            )

            same_size, diff, total = compare_print_rasters(direct_img, pdf_img)
            if not same_size:
                raise RuntimeError(
                    f"PDF round-trip changed raster dimensions: "
                    f"RAW {direct_img.size} vs PDF {pdf_img.size}. Print cancelled."
                )

            pct = (diff / total * 100.0) if total else 0.0

            if not messagebox.askyesno(
                "Print via PDF",
                f"Printer: {printer}\n"
                f"PDF: {os.path.basename(path)}\n"
                f"Paper: {cfg.get('width_mm')} x {cfg.get('height_mm')} mm\n"
                f"DPI: {cfg.get('dpi')}\n"
                f"PDF raster: {pdf_img.width} x {pdf_img.height} dots\n"
                f"PDF vs direct raster difference: {pct:.4f}%\n\n"
                "Pipeline:\nTemplate -> VECTOR PDF 1:1 -> one rasterization at printer DPI -> RAW GoDEX\n\n"
                "Continue?"
            ):
                return

            if is_virtual_printer_name(printer):
                # Keep the vector PDF intact for virtual printers.
                print_pdf_via_windows_driver(path, printer)
                mode_note = "vector PDF via Windows driver"
            else:
                # Physical label printer: rasterize exactly once at its real DPI, then RAW.
                raw_print(printer, build_raw_gzpl(cfg, pdf_img))
                mode_note = "one-raster PDF -> RAW"

            row = self.rows[self.current_row_index] if self.rows else {}
            self.history_record(cfg, printer, row, "Print via PDF")

            self.status.config(
                text=f"Printed via PDF to {printer} | {mode_note} | parity diff {pct:.4f}%"
            )
        except Exception as e:
            messagebox.showerror("Print via PDF error", str(e))


    # ---------- printers ----------
    def refresh_printers(self):
        current = self.printer_combo.get().strip()
        printers = enum_printers()
        self.printer_combo["values"] = printers
        if current in printers:
            self.printer_combo.set(current)
        else:
            pref = preferred_printer(printers)
            if pref:
                self.printer_combo.set(pref)
        if printers:
            self.status.config(text=f"Printers found: {len(printers)}")
        else:
            self.status.config(text="No printers found by Windows.")

    def validate_printer(self):
        p = self.printer_combo.get().strip()
        if not p:
            self.refresh_printers()
            p = self.printer_combo.get().strip()
        if not p:
            raise RuntimeError("No Windows printer is selected. Select a physical or virtual printer first.")
        return p


    def sync_printer(self):
        try:
            p = self.validate_printer()
            info = printer_info(p)
            self.last_printer_info = info
            lines = [
                f"Printer: {info['name']}",
                f"Driver: {info['driver']}",
                f"Port: {info['port']}",
                f"Status: {status_text(info['status'])}",
            ]
            if info.get("paper_width_mm"): lines.append(f"Driver paper width: {info['paper_width_mm']} mm")
            if info.get("paper_length_mm"): lines.append(f"Driver paper length: {info['paper_length_mm']} mm")
            if info.get("orientation"): lines.append(f"Driver orientation: {info['orientation']}")
            if info.get("print_quality"): lines.append(f"Driver print-quality/DPI field: {info['print_quality']}")
            lines += ["", "Windows cannot report the actual physical skew of the loaded paper."]
            messagebox.showinfo("Printer Sync", "\n".join(lines))
        except Exception as e:
            messagebox.showerror("Printer Sync error", str(e))

    def printer_proof(self):
        try:
            p = self.validate_printer()
            info = printer_info(p)
            cfg = self.current_bound_cfg()
            lines = [
                "SOFT PROOF — nothing will be printed",
                "",
                f"Printer: {p}",
                f"Status: {status_text(info['status'])}",
                f"Template: {cfg['width_mm']} × {cfg['height_mm']} mm @ {cfg['dpi']} dpi",
                f"Orientation: {cfg.get('orientation','portrait')}",
                f"Offset: X {cfg.get('offset_x_mm',0)} / Y {cfg.get('offset_y_mm',0)} mm",
                f"Skew compensation: {cfg.get('rotation_deg',0)}°",
            ]
            if info.get("paper_width_mm") or info.get("paper_length_mm"):
                lines.append(f"Driver paper: {info.get('paper_width_mm','?')} × {info.get('paper_length_mm','?')} mm")
            lines += ["", "This verifies the selected Windows printer profile only.", "Mechanical paper skew still needs one physical calibration print."]
            messagebox.showinfo("Printer Proof", "\n".join(lines))
            self.preview_current()
        except Exception as e:
            messagebox.showerror("Printer Proof error", str(e))

    def history_record(self, cfg, printer, row=None, action="Print Current"):
        if not self.save_history_var.get():
            return
        row = row or {}
        now = datetime.datetime.now()
        record = {
            "timestamp": now.isoformat(timespec="seconds"),
            "action": action,
            "template": os.path.basename(self.current_template_path or self.template_combo.get() or ""),
            "printer": printer,
            "brand": row.get("Brand", row.get("Brand Name", "")),
            "model": row.get("Model", row.get("SKU", "")),
            "barcode": row.get("Barcode", row.get("UPC/EAN", row.get("UPC", row.get("EAN", "")))),
            "price": row.get("Price", ""),
            "copies": cfg.get("copies", 1),
            "paper_width_mm": cfg.get("width_mm"),
            "paper_height_mm": cfg.get("height_mm"),
            "offset_x_mm": cfg.get("offset_x_mm", 0),
            "offset_y_mm": cfg.get("offset_y_mm", 0),
            "rotation_deg": cfg.get("rotation_deg", 0),
        }
        stem = now.strftime("%H%M%S_%f")[:10] + "_" + safe_filename(record["brand"]) + "_" + safe_filename(record["model"]) + "_" + safe_filename(record["barcode"])
        try:
            exact_img = render_print_hq(cfg, self.session_dir)
            exact_img.convert("L").save(os.path.join(self.session_dir, stem + ".png"))
            record["preview_png"] = stem + ".png"
            raw_name = stem + ".zpl"
            with open(os.path.join(self.session_dir, raw_name), "wb") as rf:
                rf.write(build_raw_gzpl(cfg, exact_img))
            record["raw_file"] = raw_name
            pdf_name = stem + ".pdf"
            save_exact_print_pdf(cfg, os.path.join(self.session_dir, pdf_name))
            record["vector_pdf"] = pdf_name
        except Exception:
            record["preview_png"] = ""
            record["raw_file"] = ""
            record["vector_pdf"] = ""
        with open(os.path.join(self.session_dir, "history.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        csv_path = os.path.join(self.session_dir, "history.csv")
        exists = os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csvmod.DictWriter(f, fieldnames=list(record.keys()))
            if not exists: writer.writeheader()
            writer.writerow(record)
        self.history_rows.append(record)

    def show_history(self):
        win = tk.Toplevel(self.root)
        win.title("Print History — Current Session")
        win.geometry("1160x560")

        top = ttk.Frame(win, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text=f"Session folder: {self.session_dir}").pack(side="left")

        cols = ("timestamp","brand","model","barcode","copies","printer","action")
        tree = ttk.Treeview(win, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            tree.heading(c, text=c.title())
            tree.column(c, width=140 if c != "printer" else 180)
        tree.pack(fill="both", expand=True, padx=8, pady=(0,8))

        for i,r in enumerate(self.history_rows):
            tree.insert("", "end", iid=str(i), values=[r.get(c,"") for c in cols])

        def selected_record():
            cur = tree.selection()
            if not cur:
                return None
            return self.history_rows[int(cur[0])]

        def open_folder():
            os.startfile(self.session_dir)

        def reprint_selected():
            r = selected_record()
            if not r:
                messagebox.showerror("Reprint", "Select a history row.", parent=win)
                return
            raw_file = r.get("raw_file","")
            raw_path = os.path.join(self.session_dir, raw_file) if raw_file else ""
            if not raw_path or not os.path.exists(raw_path):
                messagebox.showerror("Reprint", "Exact RAW job was not saved for this entry.", parent=win)
                return
            printer = self.printer_combo.get().strip() or r.get("printer","")
            if not printer:
                messagebox.showerror("Reprint", "Select a printer in the main window.", parent=win)
                return
            if not messagebox.askyesno(
                "Reprint exact label",
                f"Printer: {printer}\n"
                f"Model: {r.get('model','')}\n"
                f"UPC: {r.get('barcode','')}\n\n"
                "This re-sends the exact saved RAW print job. Continue?",
                parent=win
            ):
                return
            if is_virtual_printer_name(printer):
                pdf_file = r.get("vector_pdf", "")
                pdf_path = os.path.join(self.session_dir, pdf_file) if pdf_file else ""
                if not pdf_path or not os.path.exists(pdf_path):
                    messagebox.showerror("Reprint", "Saved vector PDF is unavailable for this history entry.", parent=win)
                    return
                print_pdf_via_windows_driver(pdf_path, printer)
            else:
                with open(raw_path, "rb") as f:
                    raw_print(printer, f.read())
            self.status.config(text=f"Exact history reprint sent to {printer}")

        btnbar = ttk.Frame(win)
        btnbar.pack(fill="x", padx=8, pady=(0,8))
        ttk.Button(btnbar, text="Open Folder", command=open_folder).pack(side="left", padx=3)
        ttk.Button(btnbar, text="Reprint Selected", command=reprint_selected).pack(side="left", padx=3)
        ttk.Button(btnbar, text="Close", command=win.destroy).pack(side="right", padx=3)

        if not self.history_rows:
            ttk.Label(win, text="No labels have been recorded in this session yet.").pack(pady=8)


    # ---------- data ----------
    def update_data_fields_status(self):
        try:
            self.data_fields_btn.config(text=f"Fields ({len(self.headers)})")
        except Exception:
            pass
        self.refresh_chips()

    def refresh_chips(self):
        """Header chips: which data source / template is active right now."""
        try:
            ws = self.workspace_state
            if not self.headers:
                src = "No data loaded"
            elif ws.get("data_source") == "google":
                name = next((x.get("name") for x in load_sources()["sheets"] if x["url"] == self.google_sheet_url), None)
                src = f"Google Sheet · {name or ws.get('google_sheet_tab', '')}"
            else:
                src = "Excel · " + os.path.basename(ws.get("last_excel_path", "") or "file")
            self.source_chip_var.set(f"{src} · {len(self.headers)} fields")
            self.template_chip_var.set("Template: " + (self.template_combo.get() or "—"))
        except Exception:
            pass

    def show_data_fields(self):
        win=tk.Toplevel(self.root); win.title('Loaded Data Fields'); win.geometry('620x520'); win.transient(self.root)
        frm=ttk.Frame(win,padding=10); frm.pack(fill='both',expand=True)
        ttk.Label(frm,text=f'{len(self.headers)} column(s) loaded',font=('Segoe UI',10,'bold')).pack(anchor='w')
        ttk.Label(frm,text='Templates can use any column directly as {{Column Name}}. The list is not fixed.',foreground='#555').pack(anchor='w',pady=(2,8))
        tree=ttk.Treeview(frm,columns=('field','sample'),show='headings')
        tree.heading('field',text='Column'); tree.heading('sample',text='Current row sample')
        tree.column('field',width=260); tree.column('sample',width=320)
        row=self.rows[self.current_row_index] if self.rows else {}
        for i,h in enumerate(self.headers):
            tree.insert('', 'end', iid=str(i), values=(h, format_binding_value(str(h),resolve_row_value(row,h)) if row else ''))
        y=ttk.Scrollbar(frm,orient='vertical',command=tree.yview); tree.configure(yscrollcommand=y.set)
        body=ttk.Frame(frm); body.pack(fill='both',expand=True)
        tree.pack(in_=body,side='left',fill='both',expand=True); y.pack(in_=body,side='right',fill='y')
        bar=ttk.Frame(frm); bar.pack(fill='x',pady=(8,0))
        def copy_placeholder():
            sel=tree.selection()
            if not sel:return
            h=tree.item(sel[0],'values')[0]; self.root.clipboard_clear(); self.root.clipboard_append('{{'+str(h)+'}}')
        ttk.Button(bar,text='Reload Source',command=lambda:[self.reload_current_data_source(),win.destroy(),self.show_data_fields()]).pack(side='left')
        ttk.Button(bar,text='Copy {{Field}}',command=copy_placeholder).pack(side='left',padx=4)
        ttk.Button(bar,text='Close',command=win.destroy).pack(side='right')

    def reload_current_data_source(self, quiet=False):
        source=self.workspace_state.get('data_source')
        if source=='google':
            url=self.workspace_state.get('google_sheet_url') or self.google_sheet_url
            tab=self.workspace_state.get('google_sheet_tab') or self.sheet_combo.get() or None
            if not url:
                if quiet:return False
                raise RuntimeError('No Google Sheet source is saved. Use Load Google Sheet first.')
            headers,rows=fetch_google_sheet_rows(url,tab or None)
            if not headers:
                raise RuntimeError('No data found in the Google Sheet.')
            self.google_sheet_url=url; self.headers=headers; self.rows=rows; self.filtered_indices=list(range(len(rows))); self.current_row_index=0
            self.sheet_combo['values']=[tab or 'Google Sheet']; self.sheet_combo.set(tab or 'Google Sheet')
            self.populate_tree(); self.preview_current(); self.update_data_fields_status()
            self.search_var.set(''); self.search_status.config(text=f'{len(rows)} rows')
            self.status.config(text=f'Google Sheet reloaded: {len(rows)} rows, {len(headers)} fields')
            return True
        p=self.workspace_state.get('last_excel_path')
        if p and os.path.exists(p):
            self.workbook=load_workbook(p,data_only=True,read_only=True)
            self.sheet_combo['values']=self.workbook.sheetnames
            sheet=self.workspace_state.get('last_sheet')
            if sheet in self.workbook.sheetnames:self.sheet_combo.set(sheet)
            elif self.workbook.sheetnames:self.sheet_combo.current(0)
            self.load_sheet(); self.update_data_fields_status(); self.status.config(text=f'Excel reloaded: {os.path.basename(p)} — {len(self.headers)} fields')
            return True
        if quiet:return False
        messagebox.showinfo('Reload Data','No saved data source. Load Excel or Google Sheet first.',parent=self.root)
        return False

    def load_excel(self):
        p = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")])
        if p:
            self.open_excel_path(p)

    def open_excel_path(self, p):
        try:
            self.workbook = load_workbook(p, data_only=True, read_only=True)
            remember_excel_source(p)
            self.workspace_state['last_excel_path']=p
            self.workspace_state['data_source']='excel'
            self.save_workspace()
            self.sheet_combo["values"] = self.workbook.sheetnames
            if self.workbook.sheetnames:
                self.sheet_combo.current(0)
                self.load_sheet()
            self.search_var.set("")
            self.status.config(text=f"Excel loaded: {os.path.basename(p)}")
        except Exception as e:
            messagebox.showerror("Excel error", str(e))

    def load_google_source(self, url, tab, name=None, parent=None):
        """Fetch a Google Sheet tab, make it the active data source and remember it."""
        headers, rows = fetch_google_sheet_rows(url, tab or None)
        if not headers:
            raise RuntimeError("No data found.")
        self.google_sheet_url = url
        self.workspace_state['google_sheet_url'] = url
        self.workspace_state['google_sheet_tab'] = tab or 'LABEL DATA'
        self.workspace_state['data_source'] = 'google'
        remember_google_source(url, tab or 'LABEL DATA', name)
        self.save_workspace()
        self.headers = headers
        self.rows = rows
        self.update_data_fields_status()
        self.filtered_indices = list(range(len(rows)))
        self.current_row_index = 0
        self.sheet_combo["values"] = [tab or "Google Sheet"]
        self.sheet_combo.set(tab or "Google Sheet")
        self.populate_tree()
        self.preview_current()
        self.search_var.set("")
        self.search_status.config(text=f"{len(rows)} rows")
        self.status.config(text=f"Google Sheet loaded: {len(rows)} rows")

    def load_google_sheet(self):
        """Dialog with the list of previously linked Google Sheets (nothing to retype)."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Google Sheets")
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Saved Google Sheets", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        lst = tk.Listbox(frm, height=6, width=70, exportselection=False, activestyle="none")
        lst.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 10))
        saved = []

        name_var = tk.StringVar()
        url_var = tk.StringVar(value=self.google_sheet_url or "")
        tab_var = tk.StringVar(value=self.workspace_state.get("google_sheet_tab", "LABEL DATA"))

        def refresh_list(select_url=None):
            saved[:] = load_sources()["sheets"]
            lst.delete(0, "end")
            for it in saved:
                lst.insert("end", f"{it.get('name')}   [{it.get('tab') or '-'}]")
            if select_url:
                for i, it in enumerate(saved):
                    if it["url"] == select_url:
                        lst.selection_set(i)

        def on_pick(_e=None):
            sel = lst.curselection()
            if not sel:
                return
            it = saved[sel[0]]
            name_var.set(it.get("name", "")); url_var.set(it["url"]); tab_var.set(it.get("tab") or "LABEL DATA")

        lst.bind("<<ListboxSelect>>", on_pick)
        lst.bind("<Double-1>", lambda e: do_load())
        refresh_list(self.google_sheet_url)

        ttk.Label(frm, text="Name (optional)").grid(row=2, column=0, sticky="w")
        ttk.Entry(frm, textvariable=name_var, width=40).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        ttk.Label(frm, text="Google Sheet URL or ID").grid(row=4, column=0, sticky="w")
        url_entry = ttk.Entry(frm, textvariable=url_var, width=64)
        url_entry.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        ttk.Label(frm, text="Sheet tab name").grid(row=6, column=0, sticky="w")
        ttk.Entry(frm, textvariable=tab_var, width=32).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        ttk.Label(frm, text="The sheet must be shared as 'Anyone with the link - Viewer'. Links are remembered automatically.",
                  style="Muted.TLabel").grid(row=8, column=0, columnspan=2, sticky="w", pady=(0, 10))

        def do_load():
            try:
                self.load_google_source(url_var.get().strip(), tab_var.get().strip(), name_var.get().strip() or None, dlg)
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Google Sheet error", str(e), parent=dlg)

        def do_delete():
            sel = lst.curselection()
            if not sel:
                return
            it = saved[sel[0]]
            data = load_sources()
            data["sheets"] = [x for x in data["sheets"] if not (x["url"] == it["url"] and (x.get("tab") or "") == (it.get("tab") or ""))]
            save_sources(data)
            refresh_list()

        btns = ttk.Frame(frm)
        btns.grid(row=9, column=0, columnspan=2, sticky="ew")
        ttk.Button(btns, text="Remove from list", command=do_delete).pack(side="left")
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Load", style="Accent.TButton", command=do_load).pack(side="right", padx=4)

        url_entry.focus_set()
        dlg.transient(self.root)
        dlg.grab_set()

    def build_sources_menu(self, menu):
        """Rebuilt every time it opens: one click to switch between saved sheets / recent Excel files."""
        menu.delete(0, "end")
        data = load_sources()
        if data["sheets"]:
            menu.add_command(label="Google Sheets", state="disabled")
            for it in data["sheets"][:12]:
                menu.add_command(label=f"   {it.get('name')}  [{it.get('tab') or '-'}]",
                                 command=lambda it=it: self.quick_load_google(it))
        else:
            menu.add_command(label="No saved Google Sheets yet", state="disabled")
        menu.add_command(label="Add / manage Google Sheets...", command=self.load_google_sheet)
        menu.add_separator()
        recents = [p for p in data["excel"] if os.path.exists(p)]
        if recents:
            menu.add_command(label="Recent Excel files", state="disabled")
            for p in recents[:8]:
                menu.add_command(label="   " + os.path.basename(p), command=lambda p=p: self.open_excel_path(p))
        menu.add_command(label="Open Excel file...", command=self.load_excel)

    def quick_load_google(self, it):
        try:
            self.status.config(text=f"Loading {it.get('name')}...")
            self.root.update_idletasks()
            self.load_google_source(it["url"], it.get("tab") or None, it.get("name"))
        except Exception as e:
            messagebox.showerror("Google Sheet error", str(e), parent=self.root)

    def load_sheet(self, _event=None):
        if not self.workbook:
            return
        self.workspace_state['last_sheet']=self.sheet_combo.get()
        self.save_workspace()
        ws = self.workbook[self.sheet_combo.get()]
        values = list(ws.iter_rows(values_only=True))
        if not values:
            self.headers, self.rows = [], []
            self.update_data_fields_status()
            self.filtered_indices = []
            self.populate_tree()
            return

        self.headers = make_unique_headers(values[0])
        self.update_data_fields_status()
        self.rows = []
        for r in values[1:]:
            row = {}
            has_value = False
            for i, h in enumerate(self.headers):
                v = r[i] if i < len(r) else None
                row[h] = v
                if v not in (None, ""):
                    has_value = True
            if has_value:
                self.rows.append(row)

        self.current_row_index = 0
        self.filtered_indices = list(range(len(self.rows)))
        self.populate_tree()
        self.preview_current()

    # ---------- table/search ----------
    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = self.headers
        for h in self.headers:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=max(90, min(180, len(h) * 12)), stretch=True)

        if self.rows and not self.filtered_indices and not self.search_var.get().strip():
            self.filtered_indices = list(range(len(self.rows)))

        for n, idx in enumerate(self.filtered_indices):
            row = self.rows[idx]
            vals = ["" if row.get(h) is None else row.get(h) for h in self.headers]
            self.tree.insert("", "end", iid=str(idx), values=vals, tags=("odd" if n % 2 else "even",))

        if self.filtered_indices:
            first = str(self.filtered_indices[0])
            self.tree.selection_set(first)
            self.tree.focus(first)
            self.tree.see(first)
            self.current_row_index = self.filtered_indices[0]
        self.update_row_label()

    def update_row_label(self):
        if not self.rows:
            self.row_label.config(text="No data rows")
        else:
            self.row_label.config(text=f"Row {self.current_row_index + 1} / {len(self.rows)}")

    def apply_search(self, _event=None):
        q = normalize_search_text(self.search_var.get())
        if not q:
            self.filtered_indices = list(range(len(self.rows)))
        else:
            matches = []
            preferred = ["Barcode", "UPC", "UPC/EAN", "EAN", "Model", "SKU", "Brand", "Brand Name"]
            for i, row in enumerate(self.rows):
                values = []
                seen = set()
                for c in preferred:
                    if c in row:
                        values.append(normalize_search_text(row.get(c)))
                        seen.add(c)
                for c, v in row.items():
                    if c not in seen:
                        values.append(normalize_search_text(v))
                if any(q in v for v in values):
                    matches.append(i)
            self.filtered_indices = matches
        self.populate_tree()
        self.search_status.config(text=f"{len(self.filtered_indices)} match(es)")

    def clear_search(self):
        self.search_var.set("")
        self.filtered_indices = list(range(len(self.rows)))
        self.populate_tree()
        self.search_status.config(text=f"{len(self.rows)} rows" if self.rows else "")
        self.search_entry.focus_set()

    def search_enter(self, _event=None):
        if not self.filtered_indices:
            return
        q = normalize_search_text(self.search_var.get())
        exact = None
        for i in self.filtered_indices:
            row = self.rows[i]
            for c in ("Barcode", "UPC", "UPC/EAN", "EAN"):
                if c in row and normalize_search_text(row.get(c)) == q:
                    exact = i
                    break
            if exact is not None:
                break
        idx = exact if exact is not None else self.filtered_indices[0]
        self.current_row_index = idx
        iid = str(idx)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
        self.preview_current()

    def on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if sel:
            self.current_row_index = int(sel[0])
            self.update_row_label()
            self.preview_current()

    def prev_row(self):
        if not self.rows:
            return
        pool = self.filtered_indices if self.filtered_indices else list(range(len(self.rows)))
        if not pool:
            return
        try:
            pos = pool.index(self.current_row_index)
        except ValueError:
            pos = 0
        self.current_row_index = pool[max(0, pos - 1)]
        iid = str(self.current_row_index)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
        self.preview_current()

    def next_row(self):
        if not self.rows:
            return
        pool = self.filtered_indices if self.filtered_indices else list(range(len(self.rows)))
        if not pool:
            return
        try:
            pos = pool.index(self.current_row_index)
        except ValueError:
            pos = 0
        self.current_row_index = pool[min(len(pool) - 1, pos + 1)]
        iid = str(self.current_row_index)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
        self.preview_current()

    # ---------- binding / preview ----------
    def current_bound_cfg(self):
        cfg = self.get_template_cfg()
        if self.rows:
            return bind_row_to_template(cfg, self.rows[self.current_row_index])
        return cfg

    def preview_current(self):
        try:
            cfg = self.current_bound_cfg()
            if getattr(self, "show_rulers_var", None) is not None and self.show_rulers_var.get():
                cfg = make_ruler_overlay_cfg(cfg)
            img = render_preview_with_guides(
                cfg,
                scale=3,
                show_guides=bool(self.show_guides_var.get()),
                show_fold=bool(self.show_fold_var.get())
            )
            maxw, maxh = 720, 820
            ratio = min(maxw / img.width, maxh / img.height, 1.0)
            show = img
            if ratio != 1:
                show = show.resize((int(show.width * ratio), int(show.height * ratio)), Image.Resampling.LANCZOS)
            self.tkimg = ImageTk.PhotoImage(show)
            self.preview_label.config(image=self.tkimg)

            if self.rows:
                row = self.rows[self.current_row_index]
                b = row.get("Brand", row.get("Brand Name", ""))
                m = row.get("Model", row.get("SKU", ""))
                self.status.config(text=f"Preview: {b} {m}")
            else:
                self.status.config(text="Template preview (no data row loaded)")
        except Exception as e:
            messagebox.showerror("Preview error", str(e))

    def print_test_current_one(self):
        try:
            printer=self.validate_printer()
            cfg=self.current_bound_cfg(); cfg["copies"]=1
            errors,warnings=preflight_checks(cfg)
            if errors:
                messagebox.showerror("Test Print", "\n".join(errors)); return
            self.print_cfg(cfg,printer)
            row=self.rows[self.current_row_index] if self.rows else {}
            self.history_record(cfg,printer,row,"Test Current Label")
            self.status.config(text="Test current label sent: 1 copy")
        except Exception as e:
            messagebox.showerror("Test Print",str(e))

    # ---------- compare app vs. real printer ----------
    def print_compare_sheet(self, compensated=False):
        try:
            printer = self.validate_printer()
            base = self.get_template_cfg()
            cfg = make_compare_sheet_cfg(base, compensated=compensated)
            self.print_cfg(cfg, printer)
            self.history_record(cfg, printer, {}, "Compare Sheet " + ("compensated" if compensated else "raw"))
            self.workspace_state["last_compare"] = {
                "compensated": bool(compensated),
                "scale_x": float(cfg.get("scale_x_pct", 100.0)), "scale_y": float(cfg.get("scale_y_pct", 100.0)),
                "off_x": float(cfg.get("offset_x_mm", 0.0)), "off_y": float(cfg.get("offset_y_mm", 0.0)),
                "geometry": compare_sheet_geometry(cfg),
            }
            self.save_workspace()
            self.status.config(text="Compare sheet sent. Measure it with a ruler, then use Test Print > Measure & Apply.")
        except Exception as e:
            messagebox.showerror("Compare Sheet", str(e))

    def print_ruler_overlay(self):
        try:
            printer = self.validate_printer()
            cfg = make_ruler_overlay_cfg(self.current_bound_cfg())
            self.print_cfg(cfg, printer)
            self.history_record(cfg, printer, {}, "Ruler Overlay")
            self.status.config(text="Label + ruler overlay sent. Turn on 'Rulers' in Preview to compare with the screen.")
        except Exception as e:
            messagebox.showerror("Ruler overlay", str(e))

    def measure_compensation_dialog(self):
        """Turn ruler measurements of the compare sheet into scale + offset compensation."""
        last = self.workspace_state.get("last_compare")
        cfg0 = self.get_template_cfg()
        dlg = tk.Toplevel(self.root)
        dlg.title("Measure & Apply Compensation")
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg, padding=14); frm.pack(fill="both", expand=True)
        geo = (last or {}).get("geometry") or compare_sheet_geometry(cfg0)
        inset = geo["inset"]
        if last:
            mode = "WITH compensation" if last.get("compensated") else "RAW"
            info = f"Based on the last compare sheet printed: {mode}."
        else:
            info = "Print a Compare Sheet first (Test Print menu), measure it, then come back."
        ttk.Label(frm, text=info, style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(frm, text="Measure on the PAPER with a ruler / caliper (mm):", style="Heading.TLabel").grid(row=1, column=0, columnspan=3, sticky="w")
        mv = {k: tk.StringVar() for k in ("mx", "my", "ml", "mt")}
        rows = [("mx", f"Horizontal line length  (nominal {geo['ref_x']:g})"),
                ("my", f"Vertical line length  (nominal {geo['ref_y']:g})"),
                ("ml", f"Label left edge → frame left line  (nominal {inset:g})"),
                ("mt", f"Label top edge → frame top line  (nominal {inset:g})")]
        for i, (k, lab) in enumerate(rows):
            ttk.Label(frm, text=lab).grid(row=2 + i, column=0, sticky="w", pady=3)
            ttk.Entry(frm, textvariable=mv[k], width=10).grid(row=2 + i, column=1, padx=8)
            ttk.Label(frm, text="mm").grid(row=2 + i, column=2, sticky="w")
        ttk.Separator(frm).grid(row=7, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(frm, text="Compensation applied to every print:", style="Heading.TLabel").grid(row=8, column=0, columnspan=3, sticky="w")
        cv = {"scale_x_pct": tk.StringVar(value=f"{float(cfg0.get('scale_x_pct',100)):g}"),
              "scale_y_pct": tk.StringVar(value=f"{float(cfg0.get('scale_y_pct',100)):g}"),
              "offset_x_mm": tk.StringVar(value=f"{float(cfg0.get('offset_x_mm',0)):g}"),
              "offset_y_mm": tk.StringVar(value=f"{float(cfg0.get('offset_y_mm',0)):g}")}
        labels = {"scale_x_pct": "Width scale %", "scale_y_pct": "Height scale %", "offset_x_mm": "Offset X (mm, + = right)", "offset_y_mm": "Offset Y (mm, + = down)"}
        for i, k in enumerate(cv):
            ttk.Label(frm, text=labels[k]).grid(row=9 + i, column=0, sticky="w", pady=3)
            ttk.Entry(frm, textvariable=cv[k], width=10).grid(row=9 + i, column=1, padx=8)

        def compute():
            if not last:
                messagebox.showinfo("Measure", "Print a Compare Sheet first.", parent=dlg); return
            try:
                out = {}
                for axis, ref, meas, marg, s0, o0 in (("x", geo["ref_x"], mv["mx"], mv["ml"], last["scale_x"], last["off_x"]),
                                                      ("y", geo["ref_y"], mv["my"], mv["mt"], last["scale_y"], last["off_y"])):
                    m = meas.get().strip().replace(",", ".")
                    g = marg.get().strip().replace(",", ".")
                    if not m or not g:
                        raise ValueError("Fill in all four measurements.")
                    k = float(m) / (float(ref) * s0 / 100.0)          # printer's real size factor
                    a = float(g) - k * (inset * s0 / 100.0 + o0)       # printer's real position error
                    out[axis] = (round(100.0 / k, 2), round(-a / k, 2))
                cv["scale_x_pct"].set(f"{out['x'][0]:g}"); cv["offset_x_mm"].set(f"{out['x'][1]:g}")
                cv["scale_y_pct"].set(f"{out['y'][0]:g}"); cv["offset_y_mm"].set(f"{out['y'][1]:g}")
            except Exception as ex:
                messagebox.showerror("Measure", str(ex), parent=dlg)

        def apply(reprint=False):
            try:
                c = self.get_template_cfg()
                for k, v in cv.items():
                    c[k] = float(v.get().strip().replace(",", "."))
                self.set_template_cfg(c)
                self.preview_current()
                self.status.config(text="Compensation applied: width %g%%, height %g%%, offset %g / %g mm. Save the template (or a Profile) to keep it."
                                   % (c["scale_x_pct"], c["scale_y_pct"], c["offset_x_mm"], c["offset_y_mm"]))
                dlg.destroy()
                if reprint:
                    self.print_compare_sheet(compensated=True)
            except Exception as ex:
                messagebox.showerror("Apply", str(ex), parent=dlg)

        def reset():
            cv["scale_x_pct"].set("100"); cv["scale_y_pct"].set("100"); cv["offset_x_mm"].set("0"); cv["offset_y_mm"].set("0")

        bt = ttk.Frame(frm); bt.grid(row=13, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Button(bt, text="Calculate from measurements", command=compute).pack(side="left")
        ttk.Button(bt, text="Reset", command=reset).pack(side="left", padx=6)
        ttk.Button(bt, text="Apply", style="Accent.TButton", command=apply).pack(side="right")
        ttk.Button(bt, text="Apply + verify print", command=lambda: apply(True)).pack(side="right", padx=6)
        dlg.transient(self.root); dlg.grab_set()

    def print_text_quality_test(self):
        try:
            printer=self.validate_printer(); cfg=make_text_quality_test_cfg(self.get_template_cfg())
            self.print_cfg(cfg,printer); self.history_record(cfg,printer,{},"Text Quality Test")
            self.status.config(text="Text quality test sent.")
        except Exception as e:
            messagebox.showerror("Text Quality Test",str(e))

    def print_threshold_sweep(self):
        try:
            printer=self.validate_printer()
            if not messagebox.askyesno("Threshold Sweep", "Print 4 text-quality labels at thresholds 130, 140, 150 and 160?", parent=self.root):
                return
            for th in (130,140,150,160):
                cfg=make_text_quality_test_cfg(self.get_template_cfg())
                cfg["threshold"]=th
                area=cfg.get("virtual_print_area") or {}
                if area.get("show",True): ox=float(area.get("x",0)); oy=float(area.get("y",0)); w=float(area.get("w",cfg["width_mm"]))
                else: ox=0.0; oy=0.0; w=float(cfg["width_mm"])
                cfg["elements"].append({"type":"text","text":f"THRESHOLD {th}","x":ox+1.5,"y":oy+0.2,"w":max(8,w-3),"h":2.0,"font":"Tahoma","font_size":3.4,"bold":True,"align":"right","wrap":False})
                self.print_cfg(cfg,printer)
                self.history_record(cfg,printer,{},f"Threshold Test {th}")
            self.status.config(text="Threshold sweep sent: 130 / 140 / 150 / 160")
        except Exception as e:
            messagebox.showerror("Threshold Sweep",str(e))

    def print_barcode_quality_test(self):
        try:
            printer=self.validate_printer(); cfg=make_barcode_quality_test_cfg(self.get_template_cfg())
            self.print_cfg(cfg,printer); self.history_record(cfg,printer,{},"Barcode Quality Test")
            self.status.config(text="Barcode quality test sent.")
        except Exception as e:
            messagebox.showerror("Barcode Quality Test",str(e))

    # ---------- quick scanner ----------
    def quick_scan_enter(self, _event=None):
        if self.quick_scan_after_id:
            try: self.root.after_cancel(self.quick_scan_after_id)
            except Exception: pass
            self.quick_scan_after_id=None
        self.process_quick_scan()
        return "break"

    def quick_scan_key_release(self, event=None):
        if event and event.keysym in ("Return","Escape","Up","Down","Left","Right","Shift_L","Shift_R","Control_L","Control_R"):
            return
        if self.quick_scan_after_id:
            try: self.root.after_cancel(self.quick_scan_after_id)
            except Exception: pass
            self.quick_scan_after_id=None
        if not self.quick_scan_auto_var.get() or not self.quick_scan_var.get().strip():
            return
        if self.rows:
            _, lookup, _ = build_barcode_lookup(self.headers, self.rows)
            min_len = min((len(c) for c in lookup), default=8)
            if len(normalize_barcode_value(self.quick_scan_var.get())) < min_len:
                return
        self.quick_scan_after_id=self.root.after(280,self.process_quick_scan)

    def _select_row_index(self, idx):
        self.current_row_index=idx
        iid=str(idx)
        if self.tree.exists(iid):
            self.tree.selection_set(iid); self.tree.focus(iid); self.tree.see(iid)
        self.preview_current()

    def _instant_print_row(self, idx, qty=1):
        printer=self.validate_printer()
        row=self.rows[idx]
        cfg=bind_row_to_template(self.get_template_cfg(),row)
        cfg["copies"]=max(1,int(qty))
        errors,warnings=preflight_checks(cfg)
        if errors:
            raise RuntimeError("Preflight: " + "; ".join(errors[:4]))
        self.print_cfg(cfg,printer)
        self.history_record(cfg,printer,row,"Instant Scan Print")
        return cfg

    def process_quick_scan(self):
        if self.quick_scan_after_id:
            try: self.root.after_cancel(self.quick_scan_after_id)
            except Exception: pass
            self.quick_scan_after_id=None
        raw=self.quick_scan_var.get().strip()
        if not raw:
            return
        if not self.rows:
            self.quick_scan_status_var.set("Load Excel / Google Sheet first."); self.root.bell(); return
        columns,lookup,_=build_barcode_lookup(self.headers,self.rows)
        if not columns:
            self.quick_scan_status_var.set("No UPC / EAN / Barcode column found."); self.root.bell(); return
        code=normalize_barcode_value(raw)
        status,seq=segment_concatenated_codes(code,set(lookup.keys()))
        if status in ("exact","unique") and seq:
            resolved=[]
            for c in seq:
                ids=lookup.get(c,[])
                if len(ids)!=1:
                    self.quick_scan_status_var.set(f"{c}: duplicate x{len(ids)}. Not printed."); self.root.bell(); return
                resolved.append((c,ids[0]))
            try:
                qty=max(1,int(self.quick_scan_qty_var.get()))
            except Exception:
                qty=1
            printed=0
            try:
                for c,idx in resolved:
                    self.last_scanned_row_index=idx
                    self._select_row_index(idx)
                    if self.instant_print_var.get():
                        self._instant_print_row(idx,qty); printed += qty
                last_code,last_idx=resolved[-1]
                row=self.rows[last_idx]
                brand=row.get("Brand",row.get("Brand Name","")); model=row.get("Model",row.get("SKU",""))
                if self.instant_print_var.get():
                    self.quick_scan_status_var.set(f"PRINTED {printed} label(s) | {last_code} | {brand} {model}")
                else:
                    self.quick_scan_status_var.set(f"FOUND | {last_code} | {brand} {model}")
                self.quick_scan_var.set("")
                self.quick_scan_entry.focus_set()
            except Exception as e:
                self.quick_scan_status_var.set(f"PRINT ERROR: {e}"); self.root.bell()
            return
        if status == "ambiguous":
            self.quick_scan_status_var.set("Ambiguous glued scan. Nothing printed.")
        else:
            self.quick_scan_status_var.set(f"NOT FOUND: {code}")
        self.root.bell(); self.quick_scan_var.set(""); self.quick_scan_entry.focus_set()

    def print_last_scanned(self):
        idx=self.last_scanned_row_index
        if idx is None or not self.rows:
            messagebox.showerror("Print Last", "No resolved scan yet."); return
        try:
            qty=max(1,int(self.quick_scan_qty_var.get()))
            self._instant_print_row(idx,qty)
            row=self.rows[idx]
            self.quick_scan_status_var.set(f"PRINTED {qty} | {row.get('Brand',row.get('Brand Name',''))} {row.get('Model',row.get('SKU',''))}")
            self.quick_scan_entry.focus_set()
        except Exception as e:
            messagebox.showerror("Print Last",str(e))

    # ---------- printing ----------
    def print_cfg(self, cfg, printer):
        """
        Highest-quality default output.
        Physical label printers: vector master -> one rasterization -> RAW dots.
        Virtual printers: vector PDF -> Windows driver (never send ZPL to PDF/XPS).
        """
        if is_virtual_printer_name(printer):
            path = self._proof_pdf_path(cfg, "VIRTUAL_PRINT")
            save_exact_print_pdf(cfg, path)
            print_pdf_via_windows_driver(path, printer)
            return {"mode": "virtual", "pdf": path, "img": None}

        img = render_print_hq(cfg, self.session_dir)
        raw = build_raw_gzpl(cfg, img)
        raw_print(printer, raw)
        return {"mode": "hq_raw", "pdf": None, "img": img}

    def print_via_driver_current(self):
        """Explicit Windows-driver route for physical or virtual printers."""
        try:
            printer = self.validate_printer()
            cfg = self.current_bound_cfg()
            if not self.run_preflight(cfg, silent_ok=True):
                return

            path = self._proof_pdf_path(cfg, "DRIVER_PRINT")
            save_exact_print_pdf(cfg, path)

            if not messagebox.askyesno(
                "Print via Driver / Virtual",
                f"Printer: {printer}\n"
                f"PDF: {os.path.basename(path)}\n"
                f"Paper: {cfg.get('width_mm')} x {cfg.get('height_mm')} mm\n\n"
                "This sends the VECTOR PDF through the Windows printer driver.\n"
                "For Microsoft Print to PDF, Windows should ask where to save the PDF.\n\n"
                "Continue?"
            ):
                return

            print_pdf_via_windows_driver(path, printer)
            row = self.rows[self.current_row_index] if self.rows else {}
            self.history_record(cfg, printer, row, "Print via Driver/Virtual")
            self.status.config(text=f"Vector PDF sent via Windows driver to {printer}")
        except Exception as e:
            messagebox.showerror("Driver / Virtual print error", str(e))

    def print_current(self):
        try:
            printer = self.validate_printer()
            cfg = self.current_bound_cfg()
            if not self.run_preflight(cfg, silent_ok=True):
                return
            route = "VECTOR PDF -> Windows Driver" if is_virtual_printer_name(printer) else "VECTOR master -> 1 raster @ printer DPI -> RAW"
            if not messagebox.askyesno(
                "Print current",
                f"Printer: {printer}\nCopies: {cfg.get('copies', 1)}\nPaper: {cfg.get('width_mm')} x {cfg.get('height_mm')} mm\n"
                f"Route: {route}\n\nContinue?"
            ):
                return
            self.print_cfg(cfg, printer)
            row = self.rows[self.current_row_index] if self.rows else {}
            self.history_record(cfg, printer, row, "Print Current")
            self.status.config(text=f"Printed current label to {printer}")
        except Exception as e:
            messagebox.showerror("Print error", str(e))

    def selected_indices(self):
        return sorted([int(i) for i in self.tree.selection()])

    def print_selected(self):
        try:
            if not self.rows:
                raise RuntimeError("Load Excel or Google Sheet first.")
            idxs = self.selected_indices()
            if not idxs:
                raise RuntimeError("Select one or more rows.")
            printer = self.validate_printer()
            first_cfg = bind_row_to_template(self.get_template_cfg(), self.rows[idxs[0]])
            if not self.run_preflight(first_cfg, silent_ok=True):
                return
            if not messagebox.askyesno("Print selected", f"Printer: {printer}\nRows selected: {len(idxs)}\n\nContinue?"):
                return
            base_cfg = self.get_template_cfg()
            for n, i in enumerate(idxs, 1):
                cfg = bind_row_to_template(base_cfg, self.rows[i])
                self.print_cfg(cfg, printer)
                self.history_record(cfg, printer, self.rows[i], "Print Selected")
                self.status.config(text=f"Printing selected {n}/{len(idxs)}...")
                self.root.update_idletasks()
            self.status.config(text=f"Printed {len(idxs)} selected rows.")
        except Exception as e:
            messagebox.showerror("Print selected error", str(e))

    def print_all(self):
        try:
            if not self.rows:
                raise RuntimeError("Load Excel or Google Sheet first.")
            printer = self.validate_printer()
            first_cfg = bind_row_to_template(self.get_template_cfg(), self.rows[0])
            if not self.run_preflight(first_cfg, silent_ok=True):
                return
            if not messagebox.askyesno("Print all", f"Printer: {printer}\nRows: {len(self.rows)}\n\nContinue?"):
                return
            base_cfg = self.get_template_cfg()
            for n, row in enumerate(self.rows, 1):
                cfg = bind_row_to_template(base_cfg, row)
                self.print_cfg(cfg, printer)
                self.history_record(cfg, printer, row, "Print All")
                self.status.config(text=f"Printing {n}/{len(self.rows)}...")
                self.root.update_idletasks()
            self.status.config(text=f"Printed all {len(self.rows)} rows.")
        except Exception as e:
            messagebox.showerror("Print all error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
