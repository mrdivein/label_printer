"""Units shared by the label model, the renderer and the printer code."""

DEFAULT_DPI = 300


def mm_to_px(v, dpi):
    return int(round(float(v) * float(dpi) / 25.4))
