"""Pure element geometry in label millimetres (rotation, centres, fold regions, calibration helpers)."""
import math

from .models import normalize_cfg

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
