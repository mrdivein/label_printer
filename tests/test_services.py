"""Storage-compatible services: template library, workspace state, data sets, print pipeline (printer mocked)."""
import json
import os

import pytest

from labelapp.core.models import normalize_cfg
from labelapp.services import print_service as ps
from labelapp.services import settings_service as ss
from labelapp.services.datasource_service import DataSet
from labelapp.services.template_service import TemplateError, TemplateService
from labelapp.services.workspace_service import Workspace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "Example_Label_Data.xlsx")


def test_storage_location_and_seeding_unchanged(isolated_appdata):
    d = ss.app_data_dir()
    assert d == os.path.join(str(isolated_appdata), "Temly")
    lib = ss.ensure_persistent_library()
    assert lib == os.path.join(d, "templates")
    assert sorted(os.listdir(lib)) == sorted(n for n in os.listdir(os.path.join(ROOT, "templates")) if n.endswith(".json"))
    # user files are never overwritten by seeding
    p = os.path.join(lib, "Hang_Tag_50x68.json")
    open(p, "w").write("{}")
    ss.ensure_persistent_library()
    assert open(p).read() == "{}"


def test_deleted_example_templates_are_not_seeded_again(isolated_appdata):
    lib = ss.ensure_persistent_library()
    for n in os.listdir(lib):
        if n != "Hang_Tag_50x68.json":
            os.remove(os.path.join(lib, n))
    ss.ensure_persistent_library()
    assert os.listdir(lib) == ["Hang_Tag_50x68.json"]


def test_previous_data_folder_is_copied_once_found_by_its_contents(isolated_appdata):
    old = os.path.join(str(isolated_appdata), "Old_Label_App")
    os.makedirs(os.path.join(old, "templates"))
    os.makedirs(os.path.join(str(isolated_appdata), "Unrelated"))
    json.dump({"last_printer": "Godex G530"}, open(os.path.join(old, "workspace_v20.json"), "w"))
    open(os.path.join(old, "templates", "Mine.json"), "w").write("{}")
    d = ss.app_data_dir()
    assert os.path.basename(d) == "Temly"
    assert open(os.path.join(d, "templates", "Mine.json")).read() == "{}"
    assert json.load(open(os.path.join(d, "workspace_v20.json")))["last_printer"] == "Godex G530"
    assert os.path.isdir(old)                                                    # the old folder is left as it was
    os.remove(os.path.join(d, "templates", "Mine.json"))
    ss.app_data_dir()                                                            # copied only once
    assert not os.path.exists(os.path.join(d, "templates", "Mine.json"))


def test_label_printer_data_folder_moves_to_temly(isolated_appdata):
    """Users of the app under its former name keep their templates and settings."""
    old = os.path.join(str(isolated_appdata), "LabelPrinter")
    os.makedirs(os.path.join(old, "templates"))
    json.dump({"last_printer": "Xprinter XP-365B"}, open(os.path.join(old, "workspace_v20.json"), "w"))
    open(os.path.join(old, "templates", "Mine.json"), "w").write("{}")
    d = ss.app_data_dir()
    assert d == os.path.join(str(isolated_appdata), "Temly")
    assert os.path.isfile(os.path.join(d, "templates", "Mine.json"))
    assert json.load(open(os.path.join(d, "workspace_v20.json")))["last_printer"] == "Xprinter XP-365B"


def test_existing_workspace_file_is_read_and_extended(isolated_appdata):
    os.makedirs(os.path.join(str(isolated_appdata), "Temly"))
    old = {"last_template": "Hang_Tag_50x68.json", "last_printer": "Godex G530", "data_source": "excel", "window_geometry": "1600x920+0+0"}
    json.dump(old, open(ss.workspace_path(), "w"))
    ws = Workspace()
    assert ws.get("last_printer") == "Godex G530"
    ws.set("qt_dark", True)
    saved = json.load(open(ss.workspace_path()))
    assert saved["window_geometry"] == "1600x920+0+0" and saved["qt_dark"] is True      # old keys preserved


def test_template_service_round_trip_backup_and_errors(isolated_appdata, templates):
    t = TemplateService()
    names = t.list_templates()
    assert "Hang_Tag_50x68.json" in names
    cfg = t.load("Hang_Tag_50x68.json")
    cfg["width_mm"] = 51
    t.save("Hang_Tag_50x68.json", cfg)
    assert t.load("Hang_Tag_50x68.json")["width_mm"] == 51
    backups = os.path.join(ss.app_data_dir(), "template_backups", "Hang_Tag_50x68")
    assert len(os.listdir(backups)) == 1                                           # previous version kept
    new = t.create("My label", 40, 30, 203)
    assert new == "My_label.json" and t.load(new)["dpi"] == 203
    with pytest.raises(TemplateError):
        t.create("My label", 40, 30)
    assert t.duplicate(new, "copy") == "copy.json"
    assert t.rename("copy.json", "renamed") == "renamed.json"
    t.delete("renamed.json")
    assert "renamed.json" not in t.list_templates()
    assert os.listdir(os.path.join(ss.app_data_dir(), "template_backups", "renamed"))   # delete keeps a backup


def test_template_service_import_and_schema_untouched(isolated_appdata, tmp_path):
    t = TemplateService()
    src = tmp_path / "ext.json"
    src.write_text(json.dumps({"width_mm": 30, "height_mm": 20, "elements": [{"type": "text", "text": "a", "x": 1, "y": 1}]}))
    name = t.import_file(str(src))
    saved = json.load(open(t.path_for(name), encoding="utf-8"))
    assert saved["width_mm"] == 30 and saved["elements"][0]["text"] == "a"       # known keys intact
    with pytest.raises(TemplateError):
        t.import_file(str(src))
    t.import_file(str(src), overwrite=True)
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    with pytest.raises(TemplateError):
        t.import_file(str(bad))


def test_shipped_templates_load_and_normalise_without_losing_keys(templates):
    for name, raw in templates.items():
        n = normalize_cfg(raw)
        for k, v in raw.items():
            assert n[k] == v, (name, k)


def test_dataset_excel_search_and_barcode_match():
    ds = DataSet()
    ds.load_excel(XLSX)
    assert ds.kind == "excel" and len(ds.rows) == 2 and "Barcode" in ds.headers
    ds.search("nw-1041")
    assert ds.filtered == [1] and ds.current == 1
    ds.search("")
    assert ds.best_match("012345678905") == 0
    ds.close()


def test_print_service_physical_route_sends_exact_zpl(monkeypatch, templates, sample_row, tmp_path):
    sent = []
    monkeypatch.setattr(ps, "raw_print", lambda printer, raw: sent.append((printer, raw)))
    svc = ps.PrintService(session_dir=str(tmp_path / "session"))
    os.makedirs(svc.session_dir)
    from labelapp.core.binding import bind_row_to_template
    cfg = bind_row_to_template(normalize_cfg(templates["Hang_Tag_56x83_Thermal.json"]), sample_row)
    res = svc.print_cfg(cfg, "Godex G530", sample_row)
    assert res["mode"] == "hq_raw" and len(sent) == 1
    printer, raw = sent[0]
    text = raw.decode("ascii")
    assert printer == "Godex G530"
    assert f"^PW{res['img'].width}" in text and f"^LL{res['img'].height}" in text and "^PQ2,0,1,N" in text
    assert res["img"].size == (round(56 * 300 / 25.4), round(83 * 300 / 25.4))
    svc.record_history(cfg, "Godex G530", sample_row, "Print Current", "Hang_Tag_56x83_Thermal.json")
    files = os.listdir(svc.session_dir)
    assert "history.jsonl" in files and "history.csv" in files and any(f.endswith(".zpl") for f in files) and any(f.endswith(".png") for f in files)


def test_print_service_virtual_printer_uses_vector_pdf(monkeypatch, templates, tmp_path):
    driver, raw = [], []
    monkeypatch.setattr(ps, "print_pdf_via_windows_driver", lambda path, printer: driver.append((path, printer)))
    monkeypatch.setattr(ps, "raw_print", lambda *a: raw.append(a))
    svc = ps.PrintService(session_dir=str(tmp_path))
    res = svc.print_cfg(normalize_cfg(templates["Hang_Tag_50x68.json"]), "Microsoft Print to PDF")
    assert res["mode"] == "virtual" and not raw and driver[0][1] == "Microsoft Print to PDF" and os.path.exists(driver[0][0])


def test_export_jobs_pdf_has_one_page_per_label(templates, sample_row, tmp_path):
    svc = ps.PrintService(session_dir=str(tmp_path))
    out = str(tmp_path / "all.pdf")
    svc.export_jobs_pdf(normalize_cfg(templates["Hang_Tag_50x68.json"]), [sample_row, dict(sample_row, Model="B")], [(0, 2), (1, 3)], out)
    import fitz
    with fitz.open(out) as d:
        assert len(d) == 5


def test_proof_round_trip_report(templates, tmp_path):
    svc = ps.PrintService(session_dir=str(tmp_path))
    path, report = svc.make_proof(normalize_cfg(templates["Hang_Tag_50x68.json"]))
    assert os.path.exists(path) and ("Difference vs direct RAW path" in report or "Warning" in report)
