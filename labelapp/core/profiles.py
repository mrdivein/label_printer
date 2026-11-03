"""Printer profile content: which document settings a profile carries (pure functions)."""
import copy

PROFILE_KEYS = ("width_mm", "height_mm", "dpi", "orientation", "offset_x_mm", "offset_y_mm", "rotation_deg",
                "scale_x_pct", "scale_y_pct", "threshold", "render_mode", "oversample", "virtual_print_area")


def profile_from_cfg(cfg, printer=""):
    """Same fields (and defaults) the original profile dialog stored."""
    return {
        "printer": printer,
        "width_mm": cfg.get("width_mm"), "height_mm": cfg.get("height_mm"), "dpi": cfg.get("dpi"),
        "orientation": cfg.get("orientation"),
        "offset_x_mm": cfg.get("offset_x_mm", 0), "offset_y_mm": cfg.get("offset_y_mm", 0),
        "rotation_deg": cfg.get("rotation_deg", 0),
        "scale_x_pct": cfg.get("scale_x_pct", 100.0), "scale_y_pct": cfg.get("scale_y_pct", 100.0),
        "threshold": cfg.get("threshold", 145), "render_mode": cfg.get("render_mode", "thermal_crisp"),
        "oversample": cfg.get("oversample", 4),
        "virtual_print_area": copy.deepcopy(cfg.get("virtual_print_area", {})),
    }


def apply_profile(cfg, profile):
    """Copy a profile's settings onto `cfg` (in place) and return it."""
    for key in PROFILE_KEYS:
        if key in profile:
            cfg[key] = copy.deepcopy(profile[key])
    return cfg
