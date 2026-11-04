"""Qt bridge: controllers driven the way QML drives them (no window needed)."""
import os

import pytest
from PySide6.QtTest import QTest

from labelapp.bridge.app_bridge import AppBridge
from labelapp.services import print_service as ps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "Example_Label_Data.xlsx")


def wait_for(cond, timeout=8.0):
    """Pump the event loop while yielding the GIL (QTest.qWait would starve the worker threads)."""
    import time
    from PySide6.QtCore import QCoreApplication
    end = time.time() + timeout
    while not cond() and time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)
    assert cond(), "timed out"


@pytest.fixture
def app(qapp, monkeypatch):
    b = AppBridge()
    b.library.refresh()
    assert b.document.openTemplate("Hang_Tag_50x68.json") == ""
    return b


@pytest.fixture
def printer_log(monkeypatch):
    log = {"raw": [], "fail_rows": set()}

    def fake_raw(printer, raw):
        if log["fail_rows"] and len(log["raw"]) in log["fail_rows"]:
            log["fail_rows"].discard(len(log["raw"]))
            raise RuntimeError("spooler offline")
        log["raw"].append((printer, raw))

    monkeypatch.setattr(ps, "raw_print", fake_raw)
    return log


def load_data(b):
    b.data.loadExcel(XLSX)
    wait_for(lambda: b.data.hasData)


def test_document_commands_emit_state_and_render(app, qapp):
    d = app.document
    seen = []
    d.committed.connect(lambda: seen.append(1))
    assert d.wait_for_render()
    assert d.previewSource.startswith("image://preview/workspace") and d.workspaceRect["w"] > 50
    d.selectIndex(1, False)
    assert d.selectionCount == 1 and d.selectionTitle.startswith("Chữ")
    d.setProp("font_size", 9.5)
    assert d.dirty and seen and d.canUndo
    assert d.wait_for_render()
    assert app.provider._images["workspace"].width() > 100
    d.undo()
    assert d.canRedo


def test_inspector_model_updates_in_place_while_editing(app, qapp):
    d = app.document
    d.selectIndex(1, False)
    m = d.inspectorModel
    resets = []
    m.modelReset.connect(lambda: resets.append(1))
    d.setProp("x", 3.5)
    d.setProp("font_size", 7)
    assert not resets                                           # delegates keep focus: no model reset on commit


def test_pointer_api_in_millimetres_is_zoom_independent(app, qapp):
    d = app.document
    out = []
    for px_per_mm in (3.78, 11.3, 40.0):
        d.openTemplate("Hang_Tag_50x68.json")
        d.setViewScale(px_per_mm)
        o = d.overlay["elements"][1]["poly"]
        cx, cy = (o[0][0] + o[2][0]) / 2, (o[0][1] + o[2][1]) / 2
        assert d.pointerPress(cx, cy, False) == "move"
        d.pointerMove(cx + 2, cy + 1, False)
        assert d.ghost["mode"] == "move"
        d.pointerRelease(cx + 2, cy + 1, False)
        out.append((d.cfg["elements"][1]["x"], d.cfg["elements"][1]["y"]))
    assert out[0] == out[1] == out[2]


def test_template_save_as_library_and_dirty_flag(app, qapp):
    d = app.document
    d.addText("Hello")
    assert d.dirty
    assert d.saveTemplate() == ""
    assert not d.dirty
    assert d.saveTemplateAs("variant") == "" and d.templateName == "variant.json"
    app.library.refresh()
    assert "variant.json" in app.library.names
    assert app.library.createTemplate("Small", 40, 30, 203) == ""
    assert d.cfg["width_mm"] == 40.0 and d.cfg["dpi"] == 203


def test_working_copy_recovery_after_restart(app, qapp):
    d = app.document
    d.addText("recover me")
    d.flush()
    QTest.qWait(700)
    app2 = AppBridge()
    app2.library.refresh()
    app2.document.restore_session(app2.library.names)
    assert app2.document.dirty and any(e.get("text") == "recover me" for e in app2.document.cfg["elements"])


def test_data_loading_search_and_row_binding(app, qapp):
    load_data(app)
    assert app.data.rowCount == 2 and app.data.headers[:2] == ["Brand", "Model"]
    seen = []
    app.data.rowChanged.connect(lambda: seen.append(1))
    app.data.search("NW-1041")
    assert app.data.filteredCount == 1
    app.data.search("")
    app.data.step(1)
    wait_for(lambda: seen)
    assert app.data.currentIndex == 1
    assert app.document.bound_cfg()["elements"][1]["text"] == "NORTHWIND"
    assert [r["field"] for r in app.data.fieldSamples("bar")] == ["Barcode"]
    # workspace keys identical to the original app
    assert app.workspace.get("data_source") == "excel" and app.workspace.get("last_excel_path") == XLSX


def test_print_current_goes_through_service_and_records_history(app, printer_log, qapp):
    load_data(app)
    p = app.printing
    p.printer = "Godex G530"
    pre = p.preparePrint()
    assert pre["ok"] and pre["printer"] == "Godex G530" and "RAW" in pre["route"]
    p.copies = 3
    p.printCurrent()
    assert len(printer_log["raw"]) == 1 and b"^PQ3,0,1,N" in printer_log["raw"][0][1]
    assert app.workspace.get("last_printer") == "Godex G530"
    assert os.path.exists(os.path.join(app.print_service.session_dir, "history.csv"))


def test_print_without_printer_is_blocked(app, qapp):
    p = app.printing
    p.printer = ""
    assert p.preparePrint()["ok"] is False


def test_copies_follow_row_copies_column(app, qapp):
    load_data(app)
    app.data.step(1)                                            # row 2 has Copies = 2
    wait_for(lambda: app.printing.copies == 2)


def test_queue_batch_with_skip_and_retry(app, printer_log, qapp):
    load_data(app)
    p = app.printing
    p.printer = "Godex G530"
    assert p.openQueue("all")
    p.setQty(0, 2)
    assert p.queueSummary.endswith("4 labels") or "labels" in p.queueSummary
    errors, finished = [], []
    p.batchError.connect(lambda row, msg: errors.append((row, msg)))
    p.batchFinished.connect(finished.append)
    printer_log["fail_rows"] = {1}                              # second job fails once
    assert p.prepareQueuePrint()["ok"]
    p.startQueue()
    wait_for(lambda: errors)
    assert errors[0][0] == 2 and "spooler offline" in errors[0][1]
    p.batchDecision("retry")
    wait_for(lambda: finished)
    assert len(printer_log["raw"]) == 2 and "printed 2 rows" in finished[0]
    zpl = [r[1].decode("ascii") for r in printer_log["raw"]]
    assert "^PQ2,0,1,N" in zpl[0] and "^PQ2,0,1,N" in zpl[1]      # row 1 qty 2 (set), row 2 Copies column = 2


def test_queue_batch_cancel_and_skip(app, printer_log, qapp):
    load_data(app)
    p = app.printing
    p.printer = "X"
    p.openQueue("all")
    printer_log["fail_rows"] = {0}
    errors, finished = [], []
    p.batchError.connect(lambda r, m: errors.append(r))
    p.batchFinished.connect(finished.append)
    p.startQueue()
    wait_for(lambda: errors)
    p.batchDecision("skip")
    wait_for(lambda: finished)
    assert "1 skipped" in finished[0] and len(printer_log["raw"]) == 1


def test_export_queue_pdf(app, tmp_path, qapp):
    load_data(app)
    app.printing.openQueue("all")
    out = str(tmp_path / "labels.pdf")
    assert app.printing.exportQueuePdf(out) == ""
    import fitz
    with fitz.open(out) as d:
        assert len(d) == 3                                      # qty 1 + qty 2


def test_zoom_and_view_state_never_reach_the_print_config(app, printer_log, qapp):
    load_data(app)
    app.printing.printer = "Godex G530"
    app.printing.printCurrent()
    first = printer_log["raw"][0][1]
    app.document.setViewScale(77.0)
    app.document.setViewScale(0.5)
    app.printing.printCurrent()
    assert printer_log["raw"][1][1] == first                    # byte-identical job regardless of zoom


def test_compensation_math_identity_and_known_error():
    from labelapp.core.compensation import compensation_from_measurements
    from labelapp.core.test_patterns import compare_sheet_geometry
    geo = compare_sheet_geometry({"width_mm": 50, "height_mm": 68})
    last = {"scale_x": 100.0, "scale_y": 100.0, "off_x": 0.0, "off_y": 0.0}
    ideal = {"mx": geo["ref_x"], "my": geo["ref_y"], "ml": geo["inset"], "mt": geo["inset"]}
    r = compensation_from_measurements(geo, last, ideal)
    assert r == {"scale_x_pct": 100.0, "offset_x_mm": 0.0, "scale_y_pct": 100.0, "offset_y_mm": 0.0}
    # printer prints 1 % too small and 1 mm too far left: measured length 99 % of nominal
    r = compensation_from_measurements(geo, last, {"mx": geo["ref_x"] * 0.99, "my": geo["ref_y"], "ml": "1,0", "mt": geo["inset"]})
    assert r["scale_x_pct"] == pytest.approx(101.01, abs=0.01) and r["offset_x_mm"] > 0
    with pytest.raises(ValueError):
        compensation_from_measurements(geo, last, {"mx": "", "my": "1", "ml": "1", "mt": "1"})


def test_test_prints_and_compare_sheet_state(app, printer_log, qapp):
    p = app.printing
    p.printer = "Godex G530"
    assert p.prepareTest("calibration")["ok"]
    p.printTest("calibration")
    assert b"^PQ1,0,1,N" in printer_log["raw"][-1][1]
    assert p.computeCompensation({"mx": 1, "my": 1, "ml": 1, "mt": 1})["ok"] is False      # no compare sheet yet
    p.printTest("compare_raw")
    info = p.compareInfo()
    assert info["hasSheet"] and not info["compensated"]
    r = p.computeCompensation({"mx": info["refX"], "my": info["refY"], "ml": info["inset"], "mt": info["inset"]})
    assert r["ok"] and r["scale_x_pct"] == 100.0
    app.document.setDocMany({k: r[k] for k in ("scale_x_pct", "scale_y_pct", "offset_x_mm", "offset_y_mm")})
    assert app.document.cfg["scale_x_pct"] == 100.0
    p.printer = ""
    assert p.prepareTest("ruler")["ok"] is False


def test_printer_profiles_round_trip_in_original_format(app, qapp):
    from labelapp.services.settings_service import profiles_path
    import json
    d = app.document
    d.setDocMany({"offset_x_mm": 0.7, "scale_x_pct": 101.2, "threshold": 150})
    app.printing.printer = "Godex G530"
    assert app.profiles.save("G530 56x83") == ""
    saved = json.load(open(profiles_path(), encoding="utf-8"))["G530 56x83"]
    assert saved["printer"] == "Godex G530" and saved["offset_x_mm"] == 0.7 and saved["scale_x_pct"] == 101.2
    assert set(saved) >= {"width_mm", "height_mm", "dpi", "orientation", "rotation_deg", "render_mode", "oversample", "virtual_print_area"}
    d.setDocMany({"offset_x_mm": 0, "scale_x_pct": 100})
    assert app.profiles.load("G530 56x83") == "" and d.cfg["offset_x_mm"] == 0.7 and d.cfg["scale_x_pct"] == 101.2
    assert app.profiles.save("") != ""
    app.profiles.delete("G530 56x83")
    assert "G530 56x83" not in app.profiles.names


# ---------------------------------------------------------------------- scan -> print
def test_quick_scan_selects_and_instant_prints(app, qapp, printer_log):
    load_data(app)
    app.printing.printer = "Godex EZ530+"
    s = app.scan
    assert s.quickScan("012345678905") and s.statusKind == "ok" and s.status.startswith("FOUND")
    assert app.data.currentIndex == 0 and not printer_log["raw"]       # instant print is off
    s.instantPrint = True
    s.qty = 3
    assert s.quickScan(" 012345678905 ")
    assert s.status.startswith("PRINTED 3") and len(printer_log["raw"]) == 1
    assert b"^PQ3," in printer_log["raw"][0][1]
    s.printLast()
    assert len(printer_log["raw"]) == 2
    assert s.quickScan("000") and s.status.startswith("NOT FOUND") and len(printer_log["raw"]) == 2


def test_scan_suggest_only_when_instant_print_is_off(app, qapp, printer_log):
    load_data(app)
    app.printing.printer = "Godex EZ530+"
    s = app.scan
    row0 = app.data.ds.rows[0]
    assert s.suggest("012345") and s.suggest("012345")[0]["index"] == 0   # partial UPC suggests
    assert s.suggest(str(row0["Brand"])[:3])                                # brand
    assert not s.isExactCode("012345")
    assert s.submit("012345", -1) and app.data.currentIndex == 0 and not printer_log["raw"]
    s.pick(1)
    assert app.data.currentIndex == 1 and s.hasLast and s.status.startswith("FOUND")
    assert not s.submit("no-such-thing-xyz", -1) and s.status.startswith("NO MATCH")
    s.instantPrint = True
    assert s.suggest("012345") == []                                        # exact-only while instant print is on
    assert not s.submit("012345", -1) or s.status.startswith("NOT FOUND")   # partial UPC is not printed
    assert not printer_log["raw"]


def test_instant_print_blocks_rows_with_missing_fields(app, qapp, printer_log):
    load_data(app)
    app.printing.printer = "Godex EZ530+"
    app.document.cfg["elements"] = [
        {"type": "text", "x": 1, "y": 1, "w": 30, "h": 5, "text": "{{Brand}} {{Price}}"},
        {"type": "text", "x": 1, "y": 8, "w": 30, "h": 5, "text": "{{Origin}}", "show_if": "{{Origin}}"},    # optional
    ]
    rows = app.data.ds.rows
    code0, code1 = str(rows[0]["Barcode"]), str(rows[1]["Barcode"])
    rows[0]["Price"] = ""
    rows[1]["Origin"] = ""
    s = app.scan
    s.instantPrint = True
    assert s.quickScan(code0) and s.statusKind == "error"
    assert "missing data: Price" in s.status and not printer_log["raw"]
    assert app.data.currentIndex == 0                                    # row is still shown so it can be fixed
    s.printLast()
    assert "missing data: Price" in s.status and not printer_log["raw"]
    assert s.quickScan(code1) and s.status.startswith("PRINTED") and len(printer_log["raw"]) == 1   # optional field ok
    s.quickScan(code0 + code1)                                           # glued scan: one bad row blocks all
    assert s.statusKind == "error" and len(printer_log["raw"]) == 1


def test_quick_scan_shows_row_hidden_by_search_and_reports_print_errors(app, qapp, printer_log):
    load_data(app)
    app.printing.printer = "Godex EZ530+"
    app.data.search("NW-1041")
    other = app.data.ds.rows[0]["Barcode"] if app.data.currentIndex == 1 else app.data.ds.rows[1]["Barcode"]
    app.scan.quickScan(str(other))
    assert app.data.filteredCount == app.data.rowCount                  # filter cleared so the row is visible
    printer_log["fail_rows"].add(0)
    app.scan.instantPrint = True
    app.scan.quickScan(str(other))
    assert app.scan.statusKind == "error" and "spooler offline" in app.scan.status


def test_batch_scan_queue_prints_checked_rows_and_removes_them(app, qapp, printer_log):
    load_data(app)
    app.printing.printer = "Godex EZ530+"
    s = app.scan
    codes = [str(r["Barcode"]) for r in app.data.ds.rows]
    s.removeAfterPrint = True
    s.process(f"{codes[0]} {codes[0]} {codes[1]} 123")
    assert s.queueModel.rowCount() == 3 and s.checkedLabels == 3
    pre = s.prepareBatch()
    assert pre["ok"] and pre["products"] == 2 and pre["labels"] == 3
    s.printChecked()
    wait_for(lambda: not app.printing.busy and len(printer_log["raw"]) == 2)
    assert [b"^PQ2," in printer_log["raw"][0][1], b"^PQ1," in printer_log["raw"][1][1]] == [True, True]
    wait_for(lambda: s.queueModel.rowCount() == 1)                      # only the NOT FOUND entry is left
    assert s.queueModel.rows[0]["status"] == "NOT FOUND"


def test_preview_renders_off_the_ui_thread_and_coalesces_bursts(app, qapp, monkeypatch):
    import threading
    from labelapp.bridge import document_controller as dc
    d = app.document
    assert d.wait_for_render()
    calls = []
    real = dc.render_workspace

    def spy(*a, **k):
        calls.append(threading.current_thread() is threading.main_thread())
        return real(*a, **k)

    monkeypatch.setattr(dc, "render_workspace", spy)
    d.selectIndex(1, False)
    for size in (7, 7.5, 8, 8.5, 9, 9.5, 10):     # a burst of edits, e.g. holding a spin-box arrow
        d.setProp("font_size", size)
        qapp.processEvents()
    assert d.wait_for_render()
    assert calls and not any(calls), "preview must render in a worker thread"
    assert len(calls) <= 3, f"edits were not coalesced: {len(calls)} renders"
    v = d.previewSource
    d.setProp("x", 4.0)
    assert d.wait_for_render() and d.previewSource != v and d.previewError == ""


def test_palette_text_presets_and_vietnamese_status(app):
    d = app.document
    msgs = []
    d.message.connect(msgs.append)
    n = len(d.cfg["elements"])
    d.addTextStyled("Tiêu đề", 10, True, 40, 6)
    e = d.cfg["elements"][n]
    assert (e["text"], e["font_size"], e["bold"], e["w"], e["h"]) == ("Tiêu đề", 10.0, True, 40.0, 6.0)
    assert d.selection == [n] and d.selectionTitle == "Chữ" and d.elementBold(n)
    assert msgs[-1].startswith("Đã thêm chữ")
    d.setProp("bold", False)
    assert not d.elementBold(n) and msgs[-1].startswith("Đã đổi in đậm")
    fields = {f["key"]: f for f in d.editor.inspector_fields()}
    assert fields["align"]["choice_labels"] == ["Trái", "Giữa", "Phải"]


def test_new_fold_tag_template_gets_a_saved_fold_region(app):
    assert app.library.createTemplate("Tem_gap_test", 50, 68, 300) == ""
    d = app.document
    assert d.templateName == "Tem_gap_test.json" and not d.cfg["fold_regions"]
    d.ensureFoldLine()
    assert d.saveTemplate() == "" and not d.dirty
    saved = app.library.templates.load("Tem_gap_test.json")
    assert saved["fold_regions"][0]["angle"] == 180 and saved["fold_regions"][0]["y"] == 34


def test_element_list_describes_shapes_by_geometry():
    from labelapp.bridge.models import ElementListModel as M
    assert M.describe({"type": "box", "x": 0, "y": 1.25, "w": 50, "h": 25}) == "50 × 25 mm  tại 0, 1.25"
    assert M.describe({"type": "line", "x": 1, "y": 20, "x2": 49, "y2": 20}) == "— 48 mm  tại y 20"
    assert M.describe({"type": "line", "x": 30, "y": 2, "x2": 30, "y2": 20}) == "| 18 mm  tại x 30"
    assert M.describe({"type": "text", "text": "{{Brand}}"}) == "{{Brand}}"
