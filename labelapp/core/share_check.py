"""Check a template before sharing it, and build the cleaned copy that is sent out.

A template file can carry more than what is visible on a preview filled with data: fixed texts (company name,
hotline, address…), fixed barcode / QR values (company website), logo files referenced by a local path (which
also reveals the Windows user name), elements switched to "do not print" that are still inside the file, and
the sender's own printer compensation. scan() lists those as findings; sanitize() applies one action per
finding and also drops every top-level key that is not needed to render the label.
"""
import copy
import re

from .models import PLACEHOLDER_RE, normalize_cfg

# Top-level keys a shared template keeps (everything else — history, data source details, gallery/origin info,
# designer flags — is dropped).
SHARE_KEYS = ("width_mm", "height_mm", "dpi", "orientation", "copies", "elements", "fold_regions", "preview_guides",
              "virtual_print_area", "threshold", "render_mode", "oversample", "data_bindings")
PRINTER_DEFAULTS = {"offset_x_mm": 0.0, "offset_y_mm": 0.0, "scale_x_pct": 100.0, "scale_y_pct": 100.0,
                    "rotation_deg": 0.0, "skew_deg": 0.0}

# (kind, label, regex, neutral replacement). Order matters: the first match names the finding.
PATTERNS = [
    ("email", "Email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I), "email@example.com"),
    ("url", "Trang web / liên kết",
     re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com\.vn|com|vn|net|org|io|shop|store|online|biz|info)\b(?:/\S*)?", re.I),
     "www.example.com"),
    ("phone", "Số điện thoại",
     re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?!\d)|(?<!\d)1[89]00(?:[\s.\-]?\d){4,6}(?!\d)"),
     "0900 000 000"),
    ("tax", "Mã số thuế", re.compile(r"\b(?:mst|mã số thuế|tax\s*(?:code|id)|vat\s*(?:no|id))\b\s*:?\s*[\d\-]*", re.I),
     "MST: 0000000000"),
    ("bank", "Tài khoản ngân hàng",
     re.compile(r"\b(?:stk|số tài khoản|account\s*no|bank|vietcombank|vcb|techcombank|tcb|bidv|vietinbank|"
                r"agribank|acb|mb\s?bank|vpbank|tpbank|sacombank)\b\s*:?\s*[\d\s.\-]*", re.I), "STK: 0000000000"),
    ("company", "Tên công ty",
     re.compile(r"\b(?:công ty|cty|tnhh|cổ phần|cp|jsc|co\.?,?\s*ltd\.?|ltd|corp(?:oration)?|inc\.?|llc|tập đoàn|"
                r"chi nhánh|hộ kinh doanh|hkd|doanh nghiệp|dntn)\b", re.I), "{{Company}}"),
    ("address", "Địa chỉ",
     re.compile(r"\b(?:địa chỉ|đ/c|đc|phường|p\.|quận|q\.|huyện|tỉnh|thành phố|tp\.?|thị xã|xã|kcn|khu công nghiệp|"
                r"street|st\.|ward|district|province)\s", re.I), "{{Address}}"),
]
WHOLE_TEXT_KINDS = ("company", "address")      # these replace the whole fixed text with a data field

ACTION_LABELS = {"keep": "Giữ nguyên trong bản gửi đi", "replace": "Thay bằng", "remove": "Xoá phần tử",
                 "logo_box": "Thay bằng khung LOGO", "reset": "Đặt về mặc định"}


def static_text(s):
    """The fixed part of a text: placeholders removed."""
    return PLACEHOLDER_RE.sub(" ", str(s or "")).strip()


def detect(s):
    """[(kind, label)] for every sensitive pattern found in the fixed part of `s`."""
    fixed = static_text(s)
    out = []
    for kind, label, rx, _ in PATTERNS:
        if fixed and rx.search(fixed):
            out.append((kind, label))
    return out


def neutralize(s, kinds):
    """Replace the sensitive parts of a text (placeholders are kept)."""
    if any(k in WHOLE_TEXT_KINDS for k in kinds):
        k = next(k for k in kinds if k in WHOLE_TEXT_KINDS)
        return dict((p[0], p[3]) for p in PATTERNS)[k]
    pieces = re.split(r"(\{\{[^{}]+\}\})", str(s or ""))
    for i, piece in enumerate(pieces):
        if PLACEHOLDER_RE.fullmatch(piece):
            continue
        spans = []                               # one pass: earlier patterns win, overlapping matches are skipped
        for kind, _label, rx, repl in PATTERNS:
            if kind in kinds:
                for m in rx.finditer(piece):
                    if not any(m.start() < b and a < m.end() for a, b, _ in spans):
                        spans.append((m.start(), m.end(), repl))
        for a, b, repl in sorted(spans, reverse=True):
            piece = piece[:a] + repl + piece[b:]
        pieces[i] = piece
    return "".join(pieces)


def _snippet(s, n=80):
    s = str(s or "").replace("\n", " ⏎ ")
    return s if len(s) <= n else s[: n - 1] + "…"


def scan(cfg):
    """Findings for a template, most important first. Each finding:
    {id, index, kind, title, reason, detail, actions: [...], action: default, replacement}"""
    cfg = normalize_cfg(cfg)
    found = []

    def add(index, kind, title, reason, detail, actions, action, replacement="", severity=1):
        found.append({"id": f"{kind}:{index}:{len(found)}", "index": index, "kind": kind, "title": title,
                      "reason": reason, "detail": _snippet(detail), "actions": list(actions), "action": action,
                      "replacement": _snippet(replacement), "severity": severity})

    for i, e in enumerate(cfg.get("elements", [])):
        t = str(e.get("type", "")).lower()
        if e.get("print", True) is False:
            add(i, "hidden", "Phần tử không in", "Vẫn nằm trong tệp dù không in",
                e.get("text") or e.get("value") or e.get("path") or t, ("remove", "keep"), "remove", severity=3)
            continue
        if t == "text":
            text_parts = " ".join(str(e.get(k, "") or "") for k in ("text", "prefix", "suffix"))
            hits = detect(text_parts)
            if hits:
                kinds = [k for k, _ in hits]
                new_text = neutralize(e.get("text", ""), kinds)
                add(i, "text_sensitive", " · ".join(lbl for _, lbl in hits), "Chữ cố định",
                    text_parts.strip(), ("replace", "remove", "keep"), "replace", new_text, severity=3)
            elif static_text(text_parts) and len(static_text(text_parts)) > 1:
                add(i, "text_fixed", "Chữ cố định", "Chữ cố định — hãy tự đọc lại", text_parts.strip(),
                    ("keep", "remove"), "keep", severity=0)
        elif t in ("barcode", "qr"):
            v = str(e.get("value", "") or "")
            if v and not PLACEHOLDER_RE.search(v):
                hits = detect(v)
                repl = "{{QR}}" if t == "qr" else "{{Barcode}}"
                add(i, "code_fixed", " · ".join(lbl for _, lbl in hits) or "Mã cố định", "Mã cố định", v,
                    ("replace", "keep", "remove"), "replace" if hits or t == "qr" else "keep", repl,
                    severity=3 if hits else 1)
        elif t == "image":
            p = str(e.get("path", "") or "")
            if p and not p.lower().startswith("symbol:") and not PLACEHOLDER_RE.search(p):
                add(i, "image", "Ảnh / logo từ máy", "Đường dẫn trên máy (lộ tên người dùng Windows)", p,
                    ("logo_box", "remove", "keep"), "logo_box", severity=3)

    changed = {k: cfg.get(k) for k, d in PRINTER_DEFAULTS.items() if k in cfg and _num(cfg.get(k)) != d}
    if changed:
        add(-1, "printer", "Cài đặt riêng máy in", "Bù lệch / tỉ lệ / hồ sơ của máy in của bạn",
            ", ".join(f"{k}={v}" for k, v in changed.items()), ("reset", "keep"), "reset", severity=1)
    found.sort(key=lambda f: -f["severity"])
    return found


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def sanitize(cfg, findings, actions=None):
    """The cleaned copy: apply `actions` ({finding id: action}, defaults from the findings) and drop extra keys."""
    src = normalize_cfg(copy.deepcopy(cfg))
    actions = dict(actions or {})
    elements = [dict(e) for e in src.get("elements", [])]
    drop = set()
    out = {k: src[k] for k in SHARE_KEYS if k in src}
    for f in findings:
        act = actions.get(f["id"], f["action"])
        i = f["index"]
        if f["kind"] == "printer":
            if act == "reset":
                out.update(PRINTER_DEFAULTS)
            else:
                out.update({k: src[k] for k in PRINTER_DEFAULTS if k in src})
            continue
        if not (0 <= i < len(elements)) or act == "keep":
            continue
        e = elements[i]
        if act == "remove":
            drop.add(i)
        elif act == "replace":
            if f["kind"] == "text_sensitive":
                kinds = [k for k, _ in detect(" ".join(str(e.get(x, "") or "") for x in ("text", "prefix", "suffix")))]
                e["text"] = neutralize(e.get("text", ""), kinds)
                for k in ("prefix", "suffix"):
                    if e.get(k):
                        e[k] = neutralize(e[k], kinds)
            elif f["kind"] == "code_fixed":
                e["value"] = "{{QR}}" if str(e.get("type")).lower() == "qr" else "{{Barcode}}"
        elif act == "logo_box":
            elements[i] = {"type": "box", "x": e.get("x", 0), "y": e.get("y", 0), "w": e.get("w", 10),
                           "h": e.get("h", 10), "thickness": 0.2}
            elements.append({"type": "text", "text": "LOGO", "x": e.get("x", 0), "y": e.get("y", 0),
                             "w": e.get("w", 10), "h": e.get("h", 10), "font": "Arial",
                             "font_size": max(4.0, min(12.0, float(e.get("h", 10) or 10) * 1.2)), "bold": True,
                             "align": "center", "wrap": False, "auto_fit": True, "min_font_size": 3})
    out["elements"] = [e for j, e in enumerate(elements) if j not in drop]
    for e in out["elements"]:                    # designer-only keys never travel
        e.pop("locked", None)
    return out
