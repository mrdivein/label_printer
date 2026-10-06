"""Printer size/position compensation from ruler measurements of the compare sheet."""


def compensation_from_measurements(geo, last, measured):
    """Turn four ruler measurements of the compare sheet into scale % and offset mm.

    geo      -- compare_sheet_geometry(): nominal ref_x / ref_y / inset
    last     -- what was active when the sheet was printed: scale_x, scale_y, off_x, off_y
    measured -- {'mx': horizontal line length, 'my': vertical line length,
                 'ml': left edge -> frame left line, 'mt': top edge -> frame top line}  (mm, strings or numbers)

    Returns {'scale_x_pct', 'offset_x_mm', 'scale_y_pct', 'offset_y_mm'}. Raises ValueError on missing input.
    """
    inset = geo["inset"]
    out = {}
    for axis, ref, meas_key, marg_key, s0, o0 in (("x", geo["ref_x"], "mx", "ml", last["scale_x"], last["off_x"]),
                                                  ("y", geo["ref_y"], "my", "mt", last["scale_y"], last["off_y"])):
        m = str(measured.get(meas_key, "")).strip().replace(",", ".")
        g = str(measured.get(marg_key, "")).strip().replace(",", ".")
        if not m or not g:
            raise ValueError("Fill in all four measurements.")
        k = float(m) / (float(ref) * s0 / 100.0)          # printer's real size factor
        a = float(g) - k * (inset * s0 / 100.0 + o0)       # printer's real position error
        out["scale_%s_pct" % axis] = round(100.0 / k, 2)
        out["offset_%s_mm" % axis] = round(-a / k, 2)
    return out
