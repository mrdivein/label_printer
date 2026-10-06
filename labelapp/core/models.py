"""Label document model helpers: template (cfg dict) normalisation and printer size compensation.

The on-disk template schema is intentionally unchanged: a template is a plain dict / JSON file.
"""
import re

from .units import DEFAULT_DPI

PLACEHOLDER_RE = re.compile(r"\{\{([^{}]+)\}\}")


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
