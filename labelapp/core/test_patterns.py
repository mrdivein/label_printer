"""Calibration / quality / comparison test label generators."""
import copy

from .models import normalize_cfg

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
    cfg["elements"].append({"type":"text","text":"TEXT QUALITY","x":left,"y":top,"w":max(8,w-3),"h":4,"font":"Tahoma","font_size":7.0,"bold":True,"align":"left","wrap":False,"auto_fit":True,"min_font_size":5.0})
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
    cfg["elements"].append({"type":"text","text":"BARCODE QUALITY","x":ox+1.5,"y":oy+1.5,"w":max(8,w-3),"h":4,"font":"Tahoma","font_size":6.5,"bold":True,"align":"left","wrap":False,"auto_fit":True,"min_font_size":4.5})
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
        text("Text 8pt: Label 0123456789", inset + 2, sy, w - 2 * inset - 4, size=8.0)
        text("Text 5pt: Label 0123456789", inset + 2, sy + 3.6, w - 2 * inset - 4, size=5.0)
        els.append({"type": "barcode", "value": "1234567890", "x": inset + 2, "y": sy + 7.2, "w": min(30.0, w - 2 * inset - 4), "h": 8.0,
                    "symbology": "code128", "barcode_height_mm": 7.0, "module_width": 0.25, "quiet_zone": 1.0, "physical": True})
    mode = "WITH compensation" if compensated else "RAW (no compensation)"
    text(f"COMPARE {w:g}x{h:g}mm  {mode}", inset + 1, inset + 4.0, w - 2 * inset - 2, th=2.4, size=3.4, bold=True)
    cfg["elements"] = els
    return cfg
