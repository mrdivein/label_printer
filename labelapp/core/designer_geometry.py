"""Designer geometry in *display* millimetres.

Template coordinates are "source" coordinates. Elements inside a 180 degree fold region are shown mirrored
(as they will physically appear after folding), so every editing operation needs a source <-> display mapping.
Ported from the Tk VisualDesignerDialog, now free of any UI toolkit and independent of zoom.
"""
import copy
import math

from .geometry import _element_angle, rotate_point_cw
from .label_engine import render_preview_with_guides

PREVIEW_MARGIN_PX = 36      # grey margin render_preview_with_guides() adds around the page
WORKSPACE_PAD_MM = 8.0


def source_box(e):
    t = str(e.get('type', '')).lower()
    x = float(e.get('x', 0) or 0)
    y = float(e.get('y', 0) or 0)
    if t == 'line':
        x2 = float(e.get('x2', x) or x)
        y2 = float(e.get('y2', y) or y)
        return min(x, x2), min(y, y2), max(abs(x2 - x), 0.5), max(abs(y2 - y), 0.5)
    return x, y, max(float(e.get('w', 1) or 1), 0.5), max(float(e.get('h', 1) or 1), 0.5)


def first_fold(cfg):
    for fr in cfg.get('fold_regions', []):
        if fr.get('enabled', True) and int(fr.get('angle', 180)) % 360 == 180:
            return fr
    return None


def element_in_fold_region(e, fr):
    if not fr or not fr.get('enabled', True) or int(fr.get('angle', 180)) % 360 != 180:
        return False
    x, y, w, h = source_box(e)
    cx, cy = x + w / 2, y + h / 2
    rx = float(fr.get('x', 0)); ry = float(fr.get('y', 0)); rw = float(fr.get('w', 0)); rh = float(fr.get('h', 0))
    return ry <= cy <= ry + rh      # horizontal band: x is ignored (see geometry.in_fold_band)


def fold_for_element(cfg, e):
    for fr in cfg.get('fold_regions', []):
        if element_in_fold_region(e, fr):
            return fr
    return None


def fold_at(cfg, y):
    """The enabled 180 degree fold whose horizontal band contains display (or source) height y, else None."""
    for fr in cfg.get('fold_regions', []):
        if fr.get('enabled', True) and int(fr.get('angle', 180)) % 360 == 180:
            ry = float(fr.get('y', 0))
            if ry <= y <= ry + float(fr.get('h', 0)):
                return fr
    return None


def flip_point(fr, x, y):
    """Point mirrored through the centre of a fold region (its own inverse: source <-> display)."""
    return (2 * float(fr.get('x', 0)) + float(fr.get('w', 0)) - x,
            2 * float(fr.get('y', 0)) + float(fr.get('h', 0)) - y)


def _flip_box(fr, x, y, w, h):
    rx = float(fr.get('x', 0)); ry = float(fr.get('y', 0)); rw = float(fr.get('w', 0)); rh = float(fr.get('h', 0))
    return rx + rw - (x - rx) - w, ry + rh - (y - ry) - h, w, h


def display_box_mm(cfg, e):
    x, y, w, h = source_box(e)
    fr = fold_for_element(cfg, e)
    return _flip_box(fr, x, y, w, h) if fr is not None else (x, y, w, h)


def display_to_source_box(cfg, e, box):
    x, y, w, h = box
    fr = fold_for_element(cfg, e)
    return _flip_box(fr, x, y, w, h) if fr is not None else (x, y, w, h)


def virtual_area(cfg):
    a = dict(cfg.get('virtual_print_area') or {})
    a.setdefault('show', True)
    a.setdefault('x', 0.0)
    a.setdefault('y', 0.0)
    a.setdefault('w', cfg.get('width_mm', 56))
    a.setdefault('h', cfg.get('height_mm', 83))
    return a


def visual_frame(cfg, e):
    """(cx, cy, w, h, theta) of the element as shown in the preview (theta clockwise degrees)."""
    fr = fold_for_element(cfg, e)
    fold = 180.0 if fr is not None else 0.0
    if str(e.get('type', '')).lower() == 'line':
        x1 = float(e.get('x', 0) or 0); y1 = float(e.get('y', 0) or 0)
        x2 = float(e.get('x2', x1) or x1); y2 = float(e.get('y2', y1) or y1)
        cx = (x1 + x2) / 2; cy = (y1 + y2) / 2
        if fr is not None:
            rx = float(fr.get('x', 0)); ry = float(fr.get('y', 0)); rw = float(fr.get('w', 0)); rh = float(fr.get('h', 0))
            cx = 2 * (rx + rw / 2) - cx
            cy = 2 * (ry + rh / 2) - cy
        ln = max(math.hypot(x2 - x1, y2 - y1), 0.5)
        return (cx, cy, ln, max(float(e.get('thickness', 0.2) or 0.2), 0.8),
                math.degrees(math.atan2(y2 - y1, x2 - x1)) + _element_angle(e) + fold)
    x, y, w, h = display_box_mm(cfg, e)
    return x + w / 2, y + h / 2, w, h, _element_angle(e) + fold


def frame_corners(frame):
    cx, cy, w, h, th = frame
    return [rotate_point_cw(cx + dx, cy + dy, cx, cy, th)
            for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


def element_is_rotated(e):
    return abs(_element_angle(e) % 360) > 0.0001


def element_outline(cfg, e):
    """Outline polygon (4 display-mm points) used for drawing and hit testing."""
    if element_is_rotated(e):
        return frame_corners(visual_frame(cfg, e))
    x, y, w, h = display_box_mm(cfg, e)
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def outline_bbox(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def point_near_poly(pts, x, y, pad):
    inside = False
    n = len(pts)
    for k in range(n):
        x1, y1 = pts[k]; x2, y2 = pts[(k + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1:
            inside = not inside
        dx = x2 - x1; dy = y2 - y1
        sq = dx * dx + dy * dy
        t = 0 if sq == 0 else max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / sq))
        if math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)) <= pad:
            return True
    return inside


def line_display_endpoints(cfg, e):
    """Display-space end points of an (unrotated) line element, honouring fold mirroring."""
    x1 = float(e.get('x', 0) or 0); y1 = float(e.get('y', 0) or 0)
    x2 = float(e.get('x2', x1) or x1); y2 = float(e.get('y2', y1) or y1)
    fr = fold_for_element(cfg, e)
    if fr is not None:
        rx = float(fr.get('x', 0)); ry = float(fr.get('y', 0)); rw = float(fr.get('w', 0)); rh = float(fr.get('h', 0))
        x1 = 2 * (rx + rw / 2) - x1; y1 = 2 * (ry + rh / 2) - y1
        x2 = 2 * (rx + rw / 2) - x2; y2 = 2 * (ry + rh / 2) - y2
    return (x1, y1), (x2, y2)


# ---------------------------------------------------------------- workspace preview

def workspace_preview_cfg(cfg, bound_cfg=None):
    """Template enlarged by a margin so elements outside the paper stay visible while designing.

    Returns (workspace_cfg, min_x_mm, min_y_mm). Geometry of the workspace is shifted by (-min_x, -min_y).
    `bound_cfg` is the template with a data row applied (same geometry as `cfg`).
    """
    cfg_b = copy.deepcopy(bound_cfg if bound_cfg is not None else cfg)
    pw = float(cfg_b.get('width_mm', 56)); ph = float(cfg_b.get('height_mm', 83)); pad = WORKSPACE_PAD_MM
    min_x, min_y, max_x, max_y = -pad, -pad, pw + pad, ph + pad
    a = virtual_area(cfg_b)
    if a.get('show', True):
        ax = float(a.get('x', 0)); ay = float(a.get('y', 0)); aw = float(a.get('w', pw)); ah = float(a.get('h', ph))
        min_x = min(min_x, ax - pad); min_y = min(min_y, ay - pad)
        max_x = max(max_x, ax + aw + pad); max_y = max(max_y, ay + ah + pad)
    for e in cfg_b.get('elements', []):
        try:
            x1, y1, x2, y2 = outline_bbox(element_outline(cfg_b, e))
            min_x = min(min_x, x1 - pad); min_y = min(min_y, y1 - pad)
            max_x = max(max_x, x2 + pad); max_y = max(max_y, y2 + pad)
        except Exception:
            pass
    min_x = max(-300.0, min_x); min_y = max(-300.0, min_y); max_x = min(500.0, max_x); max_y = min(500.0, max_y)
    sx = -min_x; sy = -min_y
    wc = cfg_b
    wc['width_mm'] = max(20, max_x - min_x); wc['height_mm'] = max(20, max_y - min_y); wc['orientation'] = 'portrait'
    wc['offset_x_mm'] = 0; wc['offset_y_mm'] = 0; wc['rotation_deg'] = 0
    wc['scale_x_pct'] = 100.0; wc['scale_y_pct'] = 100.0
    wc['printable_area'] = {'enabled': False, 'x': 0, 'y': 0, 'w': wc['width_mm'], 'h': wc['height_mm']}
    wc['virtual_print_area'] = {'show': False, 'x': 0, 'y': 0, 'w': 1, 'h': 1}
    for e in wc.get('elements', []):
        for k in ('x', 'x2'):
            if k in e: e[k] = float(e.get(k, 0)) + sx
        for k in ('y', 'y2'):
            if k in e: e[k] = float(e.get(k, 0)) + sy
    for fr in wc.get('fold_regions', []):
        fr['x'] = float(fr.get('x', 0)) + sx; fr['y'] = float(fr.get('y', 0)) + sy
    shifted = []
    for g in wc.get('preview_guides', []):
        gg = copy.deepcopy(g)
        for k in ('x', 'x2'):
            if k in gg: gg[k] = float(gg.get(k, 0)) + sx
        for k in ('y', 'y2'):
            if k in gg: gg[k] = float(gg.get(k, 0)) + sy
        shifted.append(gg)
    shifted.append({'name': 'Nominal paper', 'type': 'box', 'x': sx, 'y': sy, 'w': pw, 'h': ph, 'color': 'gray', 'show': True})
    if a.get('show', True):
        shifted.append({'name': 'Virtual print area', 'type': 'box', 'x': float(a.get('x', 0)) + sx, 'y': float(a.get('y', 0)) + sy,
                        'w': float(a.get('w', pw)), 'h': float(a.get('h', ph)), 'color': 'green', 'show': True})
    wc['preview_guides'] = shifted
    return wc, min_x, min_y


def render_workspace(cfg, bound_cfg=None, scale=2, show_guides=True, show_fold=True):
    """Render the design workspace. Returns (PIL image, metrics).

    metrics['x'], ['y'], ['w'], ['h'] give the image rectangle in *label millimetres* so a view can place the
    picture at its true physical position, independent of zoom.
    """
    wc, min_x, min_y = workspace_preview_cfg(cfg, bound_cfg)
    img = render_preview_with_guides(wc, scale=scale, show_guides=show_guides, show_fold=show_fold)
    px_per_mm = int(wc['dpi']) * scale / 25.4
    margin_mm = PREVIEW_MARGIN_PX / px_per_mm
    metrics = {
        'x': min_x - margin_mm, 'y': min_y - margin_mm,
        'w': img.width / px_per_mm, 'h': img.height / px_per_mm,
        'px_w': img.width, 'px_h': img.height, 'min_x': min_x, 'min_y': min_y,
    }
    return img, metrics
