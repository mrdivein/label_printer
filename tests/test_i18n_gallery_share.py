"""Interface language switch, template gallery and the share check (original template / cleaned copy)."""
import glob
import json
import os
import re

import pytest

from labelapp import i18n
from labelapp.core.share_check import detect, neutralize, sanitize, scan
from labelapp.i18n_en import EN
from labelapp.services.gallery_service import GalleryService, template_fields
from labelapp.services.template_service import TemplateService

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QML = os.path.join(ROOT, "labelapp", "ui", "qml")
VI = re.compile("[\u00c0-\u1ef9\u0110\u0111]")
QSTR = re.compile(r'qsTr\("((?:[^"\\]|\\.)*)"\)')


def _unescape(s):
    return s.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')


@pytest.fixture(autouse=True)
def vietnamese():
    i18n.set_language("vi")
    yield
    i18n.set_language("vi")


# ------------------------------------------------------------------ i18n
def test_every_qml_string_has_an_english_translation():
    missing = []
    for f in glob.glob(os.path.join(QML, "**", "*.qml"), recursive=True):
        for m in QSTR.finditer(open(f, encoding="utf-8").read()):
            key = _unescape(m.group(1))
            if key not in EN:
                missing.append((os.path.basename(f), key))
    assert not missing, missing


def test_no_untranslated_vietnamese_literal_left_in_qml():
    lit = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
    allowed = re.compile(r'(\bt:\s*|vi:\s*)$')        # symbol names / gallery chips carry both languages themselves
    left = []
    for f in glob.glob(os.path.join(QML, "**", "*.qml"), recursive=True):
        for line in open(f, encoding="utf-8"):
            if line.strip().startswith("//"):
                continue
            code = line
            for m in lit.finditer(code):
                before = code[:m.start()]
                if VI.search(m.group(1)) and not before.endswith("qsTr(") and not allowed.search(before):
                    left.append((os.path.basename(f), m.group(1)))
    assert not left, left


def test_tr_exact_template_and_formatted_messages():
    assert i18n.tr("Sẵn sàng") == "Sẵn sàng"
    i18n.set_language("en")
    assert i18n.tr("Sẵn sàng") == "Ready"
    assert i18n.tr("Đã mở mẫu: Tem_60x40.json") == "Opened template: Tem_60x40.json"
    assert i18n.tr("Trang tính: Sheet1 — 42 dòng") == "Sheet: Sheet1 — 42 rows"
    assert i18n.tr("Nhóm · 3 phần tử") == "Group · 3 elements"
    assert i18n.trf("Đã lưu mẫu: {}", "A") == "Saved template: A"
    assert i18n.tr("không có trong bảng") == "không có trong bảng"     # unknown text passes through


def test_language_switch_retranslates_live_qml(qapp, tmp_path):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from labelapp.bridge.app_bridge import AppBridge
    from labelapp.paths import qml_dir

    bridge = AppBridge()
    engine = QQmlApplicationEngine()
    engine.addImageProvider("preview", bridge.provider)
    engine.addImportPath(qml_dir())
    ctx = engine.rootContext()
    for name, obj in (("App", bridge), ("Doc", bridge.document), ("Lib", bridge.library), ("Data", bridge.data),
                      ("Printing", bridge.printing), ("Scan", bridge.scan), ("Profiles", bridge.profiles),
                      ("Updates", bridge.updates), ("Gallery", bridge.gallery), ("I18n", bridge.i18n)):
        ctx.setContextProperty(name, obj)
    bridge.i18n.attach(qapp, engine)
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.load(QUrl.fromLocalFile(os.path.join(qml_dir(), "Main.qml")))
    assert engine.rootObjects(), warnings
    root = engine.rootObjects()[0]
    lang = root.findChild(object, "langButton")
    assert lang.property("text") == "VI"
    bridge.i18n.setLanguage("en")
    assert lang.property("text") == "EN"
    assert bridge.status == "Ready"
    bridge.document.addSymbol("fragile")                        # element list rows re-describe in English
    model = bridge.document.elementsModel
    summaries = [model.data(model.index(i), model.SummaryRole) for i in range(model.rowCount())]
    assert "Symbol fragile" in summaries, summaries
    assert bridge.document.typeLabel("text") == "Text"
    assert bridge.workspace.get("qt_language") == "en"
    assert bridge.status == "Symbol added — used when printing, not saved to the template yet."
    bridge.i18n.setLanguage("vi")
    assert bridge.status == "Symbol added — đã áp dụng khi in, chưa lưu vào mẫu."
    errors = [w for w in warnings if "TypeError" in w or "ReferenceError" in w or "is not a type" in w]
    assert not errors, errors
    root.close()


# ------------------------------------------------------------------ gallery
def test_gallery_templates_render_and_are_categorised():
    g = GalleryService()
    items = g.items()
    assert len(items) >= 40
    cats = {c["id"] for c in g.categories()}
    assert {"eyewear", "shipping", "price", "qr", "barcode"} <= cats
    for it in items:
        assert it["category"] in cats, it["id"]
        assert it["name"]["vi"] and it["name"]["en"] and it["description"]["en"], it["id"]
        sample = g.sample(it["id"])
        missing = [f for f in it["fields"] if f not in sample]
        assert not missing, (it["id"], missing)          # the sample fills every field of the preview
        assert g.render(it["id"], True, 200).size[0] > 10
        assert g.render(it["id"], False, 200).size[0] > 10


def test_gallery_search_is_accent_insensitive():
    g = GalleryService()
    assert "eyewear_temple_tag" in g.search("kinh mat")
    assert "eyewear_temple_tag" in g.search("Kính")
    assert "ship_100x150" in g.search("100x150")
    assert g.search("zzzz-not-there") == []


def test_gallery_install_copies_a_clean_template(tmp_path):
    g = GalleryService()
    ts = TemplateService(str(tmp_path))
    a = g.install("product_60x40", ts, "vi")
    b = g.install("product_60x40", ts, "en")
    c = g.install("product_60x40", ts, "vi")
    assert a != c and a.endswith(".json") and b.startswith("Product_label")
    cfg = ts.load(a)
    assert "gallery" not in cfg and "{{Barcode}}" in json.dumps(cfg)


# ------------------------------------------------------------------ share check
COMPANY = {"width_mm": 60, "height_mm": 40, "offset_x_mm": 0.6, "last_data": "C:/Users/someone/data.xlsx", "elements": [
    {"type": "text", "text": "CÔNG TY TNHH ABC"},
    {"type": "text", "text": "Hotline: 0909 123 456 · info@abc.vn"},
    {"type": "text", "text": "{{Product}}"},
    {"type": "text", "text": "Xuất xứ: {{Origin}}"},
    {"type": "qr", "value": "https://abc.vn/p", "x": 40, "y": 2, "w": 15, "h": 15},
    {"type": "barcode", "value": "{{Barcode}}"},
    {"type": "image", "path": "C:/Users/someone/logo.png", "x": 1, "y": 1, "w": 10, "h": 5},
    {"type": "image", "path": "symbol:fragile"},
    {"type": "text", "text": "giá nhập 120k", "print": False},
]}


def test_detect_and_neutralize():
    kinds = [k for k, _ in detect("Hotline: 0909 123 456 · info@abc.vn")]
    assert {"phone", "email"} <= set(kinds)
    assert neutralize("Hotline: 0909 123 456 · info@abc.vn", kinds) == "Hotline: 0900 000 000 · email@example.com"
    assert detect("{{Company}} · {{Phone}}") == []          # placeholders are not company data
    assert detect("Size M") == [] and detect("Giá: 289.000") == []


def test_scan_finds_company_details_and_sanitize_cleans_them():
    found = scan(COMPANY)
    kinds = {f["kind"] for f in found}
    assert {"text_sensitive", "code_fixed", "image", "hidden", "printer", "text_fixed"} <= kinds
    assert found[0]["severity"] == 3                            # most important first
    out = sanitize(COMPANY, found)
    dump = json.dumps(out, ensure_ascii=False)
    for leak in ("ABC", "0909", "abc.vn", "someone", "giá nhập", "last_data"):
        assert leak not in dump, leak
    assert out["offset_x_mm"] == 0.0
    assert "{{Product}}" in dump and "symbol:fragile" in dump and "Xuất xứ: {{Origin}}" in dump
    assert "LOGO" in dump


def test_sanitize_respects_keep_actions():
    found = scan(COMPANY)
    keep = {f["id"]: "keep" for f in found}
    out = sanitize(COMPANY, found, keep)
    dump = json.dumps(out, ensure_ascii=False)
    assert "CÔNG TY TNHH ABC" in dump and "giá nhập" in dump and out["offset_x_mm"] == 0.6
    assert "last_data" not in dump                              # unknown keys never travel


def test_library_share_flow_and_raw_preview(qapp, tmp_path):
    from labelapp.bridge.app_bridge import AppBridge
    b = AppBridge()
    TemplateService(b.templates.library_dir).save_as("Company", COMPANY)
    b.library.refresh()
    assert b.library.rawPreview is True
    b.library.showPreview("Company.json")
    assert "Company.json" in b.library.previewInfo
    assert b.library.shareCheck("Company.json") == ""
    findings = b.library.shareFindings
    assert findings and all(f["actionLabels"] for f in findings)
    dest = tmp_path / "shared.json"
    assert b.library.exportShared(str(dest)) == ""
    assert "abc.vn" not in dest.read_text(encoding="utf-8")


def test_template_fields_order():
    assert template_fields({"elements": [{"text": "{{A}} {{B}}"}, {"value": "{{A}}"}, {"show_if": "{{C}}"}]}) == ["A", "B", "C"]
