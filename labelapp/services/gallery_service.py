"""Template gallery: the ready-made templates bundled in ``templates/gallery`` (built by tools/make_gallery.py).

A gallery template is a normal label template plus a ``gallery`` block (category, names and descriptions in
Vietnamese and English, sample data). "Use template" copies it into the user's library without that block.
"""
import copy
import json
import os
import re

from PIL import Image, ImageDraw

from ..core.binding import bind_row_to_template
from ..core.label_engine import render_label
from ..core.models import PLACEHOLDER_RE, normalize_cfg
from ..paths import app_root
from .template_service import write_template

GALLERY_KEY = "gallery"
CATEGORIES_FILE = "_categories.json"
CODE_KINDS = {"code128": "Code 128", "ean13": "EAN-13", "ean8": "EAN-8", "upca": "UPC-A", "code39": "Code 39",
              "itf": "ITF"}


def gallery_dir():
    return os.path.join(app_root(), "templates", "gallery")


def template_fields(cfg):
    """{{Field}} names used by a template, in first-use order."""
    seen = []
    for e in cfg.get("elements", []):
        for k in ("text", "value", "path", "show_if"):
            for m in PLACEHOLDER_RE.finditer(str(e.get(k, "") or "")):
                name = m.group(1).strip()
                if name not in seen:
                    seen.append(name)
    return seen


def code_kinds(cfg):
    kinds = []
    for e in cfg.get("elements", []):
        t = str(e.get("type", "")).lower()
        k = "QR" if t == "qr" else CODE_KINDS.get(str(e.get("symbology", "code128")).lower(), "Barcode") if t == "barcode" else None
        if k and k not in kinds:
            kinds.append(k)
    return kinds


def _fit_dpi(cfg, long_side_px):
    longest = max(float(cfg.get("width_mm", 50)), float(cfg.get("height_mm", 50)), 1.0)
    return int(max(72, min(1200, long_side_px / longest * 25.4)))


def original_view(cfg):
    """The template as designed, drawable without data: a numeric barcode (EAN / UPC / ITF) whose value is still a
    {{Field}} cannot be encoded, so the original view draws it as Code 128 of the placeholder text."""
    cfg = copy.deepcopy(normalize_cfg(cfg))
    for e in cfg["elements"]:
        if str(e.get("type", "")).lower() == "barcode" and PLACEHOLDER_RE.search(str(e.get("value", ""))) \
                and str(e.get("symbology", "code128")).lower() not in ("code128", "code39"):
            e["symbology"] = "code128"
    return cfg


def render_card(cfg, long_side_px=420):
    """White label (thin grey outline) rendered so its longest side is about `long_side_px`."""
    cfg = original_view(cfg)
    # Barcodes need printer-like resolution (a module must be >= 1 px): render at >= 300 dpi, then scale down.
    img = render_label({**cfg, "dpi": max(300, _fit_dpi(cfg, long_side_px)), "virtual_print_area": {"show": False}})
    img = img.convert("RGB")
    if max(img.size) > long_side_px:
        img.thumbnail((long_side_px, long_side_px), Image.Resampling.LANCZOS)
    ImageDraw.Draw(img).rectangle((0, 0, img.width - 1, img.height - 1), outline=(176, 182, 194), width=1)
    return img


class GalleryService:
    def __init__(self, directory=None):
        self.dir = directory or gallery_dir()
        self._items = None
        self._cfgs = {}

    # ------------------------------------------------------------------ catalogue
    def categories(self):
        try:
            with open(os.path.join(self.dir, CATEGORIES_FILE), "r", encoding="utf-8") as f:
                cats = json.load(f)
        except (OSError, ValueError):
            cats = []
        counts = {}
        for it in self.items():
            counts[it["category"]] = counts.get(it["category"], 0) + 1
        return [dict(c, count=counts.get(c["id"], 0)) for c in cats if counts.get(c["id"])]

    def items(self):
        if self._items is None:
            items = []
            names = sorted(os.listdir(self.dir)) if os.path.isdir(self.dir) else []
            for fn in names:
                if not fn.lower().endswith(".json") or fn.startswith("_"):
                    continue
                try:
                    cfg = self._read(fn)
                except (OSError, ValueError):
                    continue
                meta = cfg.get(GALLERY_KEY) or {}
                tid = meta.get("id") or os.path.splitext(fn)[0]
                self._cfgs[tid] = cfg
                items.append({
                    "id": tid, "file": fn, "category": meta.get("category", "other"), "popular": bool(meta.get("popular")),
                    "name": meta.get("name") or {"vi": tid, "en": tid},
                    "description": meta.get("description") or {"vi": "", "en": ""},
                    "w": float(cfg.get("width_mm", 0)), "h": float(cfg.get("height_mm", 0)),
                    "size": f"{float(cfg.get('width_mm', 0)):g}×{float(cfg.get('height_mm', 0)):g} mm",
                    "fields": template_fields(cfg), "codes": code_kinds(cfg),
                    "fold": any(fr.get("enabled", True) for fr in cfg.get("fold_regions", []) or []),
                })
            try:                                     # category order of _categories.json, popular first, then size
                with open(os.path.join(self.dir, CATEGORIES_FILE), "r", encoding="utf-8") as f:
                    order = {c["id"]: i for i, c in enumerate(json.load(f))}
            except (OSError, ValueError):
                order = {}
            items.sort(key=lambda it: (order.get(it["category"], 99), not it["popular"], it["w"] * it["h"]))
            self._items = items
        return self._items

    def _read(self, fn):
        with open(os.path.join(self.dir, fn), "r", encoding="utf-8") as f:
            return json.load(f)

    def item(self, tid):
        return next((it for it in self.items() if it["id"] == tid), None)

    def load(self, tid):
        """The gallery template as a library template (no gallery block)."""
        self.items()
        cfg = copy.deepcopy(self._cfgs[tid])
        cfg.pop(GALLERY_KEY, None)
        return normalize_cfg(cfg)

    def sample(self, tid):
        self.items()
        return dict((self._cfgs[tid].get(GALLERY_KEY) or {}).get("sample") or {})

    def search(self, query, lang="vi"):
        """Ids whose name / description / size / codes / fields contain every word of `query` (accent-insensitive)."""
        words = [w for w in _fold(query).split() if w]
        out = []
        for it in self.items():
            hay = _fold(" ".join([it["name"].get("vi", ""), it["name"].get("en", ""), it["description"].get("vi", ""),
                                  it["description"].get("en", ""), it["size"], it["size"].replace("×", "x"),
                                  " ".join(it["codes"]), " ".join(it["fields"]), it["category"]]))
            if all(w in hay for w in words):
                out.append(it["id"])
        return out

    # ------------------------------------------------------------------ preview / install
    def render(self, tid, with_sample=True, long_side_px=420):
        cfg = self.load(tid)
        if with_sample:
            cfg = bind_row_to_template(cfg, self.sample(tid))
        return render_card(cfg, long_side_px)

    def install(self, tid, templates, lang="vi"):
        """Copy a gallery template into the user's library under a free name; returns that file name."""
        it = self.item(tid)
        base = (it["name"].get(lang) or it["name"].get("vi") or tid) if it else tid
        base = re.sub(r"\s+", "_", base.replace("×", "x")).strip("_") or tid
        cfg = self.load(tid)
        name, n = base, 2
        while os.path.exists(templates.path_for(name + ".json")):
            name, n = f"{base}_{n}", n + 1
        write_template(templates.path_for(name + ".json"), cfg)
        return name + ".json"


def _fold(s):
    """Lower-case, accent-free text for search ("Tem giá" matches "tem gia")."""
    import unicodedata
    s = str(s or "").lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def contact_sheet(service, path, cols=6, cell=260):
    """Debug / docs helper: every gallery template on one PNG."""
    items = service.items()
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 30)), (236, 239, 244))
    d = ImageDraw.Draw(sheet)
    for i, it in enumerate(items):
        img = service.render(it["id"], True, cell - 24)
        img.thumbnail((cell - 24, cell - 24))
        x, y = (i % cols) * cell, (i // cols) * (cell + 30)
        sheet.paste(img, (x + (cell - img.width) // 2, y + 12 + (cell - 24 - img.height) // 2))
        d.text((x + 8, y + cell - 4), it["id"], fill=(40, 40, 40))
    sheet.save(path)
    return path
