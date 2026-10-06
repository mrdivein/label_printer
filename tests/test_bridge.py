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
    assert b.document.openTemplate("ECG_H_TAG_50x68.json") == ""
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
    QTest.qWait(30)
    assert d.previewSource.startswith("image://preview/workspace") and d.workspaceRect["w"] > 50
    d.selectIndex(1, False)
    assert d.selectionCount == 1 and d.selectionTitle.startswith("Text")
    d.setProp("font_size", 9.5)
    assert d.dirty and seen and d.canUndo
    QTest.qWait(30)
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
        d.openTemplate("ECG_H_TAG_50x68.json")
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
    app.data.search("FT1041")
    assert app.data.filteredCount == 1
    app.data.search("")
    app.data.step(1)
    wait_for(lambda: seen)
    assert app.data.currentIndex == 1
    assert app.document.bound_cfg()["elements"][1]["text"] == "TOM FORD"
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
