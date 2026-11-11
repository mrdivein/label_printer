"""Conservative template validation before printing."""
from .models import is_printed, normalize_cfg

def preflight_checks(cfg):
    """
    Conservative validation. It does not change data or Google Sheets behavior.
    Returns (errors, warnings).
    """
    cfg = normalize_cfg(cfg)
    # Elements switched off for printing are not checked: they never reach the paper.
    cfg["elements"] = [e for e in cfg.get("elements", []) if is_printed(e)]
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
