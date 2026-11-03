"""Print orchestration: the proven pipeline from the original App, without any UI.

Physical label printers:  VECTOR master PDF -> one rasterisation at printer DPI -> ZPL ^GFA -> RAW spooler job.
Virtual printers (PDF/XPS...): VECTOR PDF -> Windows driver (never ZPL to a PDF/XPS printer).
"""
import csv
import datetime
import json
import os
import shutil
import tempfile

from ..core.binding import bind_row_to_template
from ..core.pdf_export import (compare_print_rasters, rasterize_exact_print_pdf, render_print_hq, save_exact_print_pdf)
from ..core.preflight import preflight_checks
from ..core.units import DEFAULT_DPI
from .printer_service import (build_raw_gzpl, is_virtual_printer_name, print_pdf_via_windows_driver, raw_print)
from .settings_service import create_session_dir, safe_filename


def describe_route(printer):
    return ("VECTOR PDF -> Windows Driver" if is_virtual_printer_name(printer)
            else "VECTOR master -> 1 raster @ printer DPI -> RAW")


def _row_fields(row):
    row = row or {}
    return (row.get("Brand", row.get("Brand Name", "")), row.get("Model", row.get("SKU", "")),
            row.get("Barcode", row.get("UPC/EAN", row.get("UPC", row.get("EAN", "")))))


class PrintService:
    def __init__(self, session_dir=None, history_enabled=True):
        self._session_dir = session_dir
        self.history_enabled = history_enabled
        self.history_rows = []
        self._last_print = None

    @property
    def session_dir(self):
        """Per-launch output folder; created on first use (no empty folders for sessions that never print)."""
        if self._session_dir is None:
            self._session_dir = create_session_dir()
        return self._session_dir

    # ---- validation
    @staticmethod
    def preflight(cfg):
        """(errors, warnings) for the bound template about to be printed."""
        return preflight_checks(cfg)

    # ---- files
    def proof_pdf_path(self, prefix="proof", row=None):
        now = datetime.datetime.now()
        brand, model, code = _row_fields(row)
        name = (prefix + "_" + now.strftime("%H%M%S_%f")[:10] + "_" + safe_filename(brand) + "_" +
                safe_filename(model) + "_" + safe_filename(code) + ".pdf")
        return os.path.join(self.session_dir, name)

    # ---- printing
    def print_cfg(self, cfg, printer, row=None):
        if is_virtual_printer_name(printer):
            path = self.proof_pdf_path("VIRTUAL_PRINT", row)
            save_exact_print_pdf(cfg, path)
            print_pdf_via_windows_driver(path, printer)
            return {"mode": "virtual", "pdf": path, "img": None}
        img = render_print_hq(cfg, self.session_dir)
        raw = build_raw_gzpl(cfg, img)
        raw_print(printer, raw)
        self._last_print = (cfg, img, raw)
        return {"mode": "hq_raw", "pdf": None, "img": img}

    def print_via_driver(self, cfg, printer, row=None):
        path = self.proof_pdf_path("DRIVER_PRINT", row)
        save_exact_print_pdf(cfg, path)
        print_pdf_via_windows_driver(path, printer)
        return path

    def make_proof(self, cfg, row=None):
        """1:1 vector PDF proof + round-trip check against the direct raster. Nothing is printed.

        Returns (path, report_text)."""
        path = self.proof_pdf_path("PDF_PROOF", row)
        direct_img = save_exact_print_pdf(cfg, path, return_raster=True)
        pdf_img = rasterize_exact_print_pdf(path, int(cfg.get("dpi", DEFAULT_DPI)), int(cfg.get("threshold", 180)))
        same, diff, total = compare_print_rasters(direct_img, pdf_img)
        if same:
            pct = (diff / total * 100.0) if total else 0.0
            report = (f"Vector PDF rasterized at printer DPI: {pdf_img.width} x {pdf_img.height} dots\n"
                      f"Difference vs direct RAW path: {diff:,} / {total:,} ({pct:.4f}%)")
        else:
            report = f"Warning: PDF raster size {pdf_img.size} differs from RAW raster {direct_img.size}."
        return path, report

    def export_jobs_pdf(self, base_cfg, rows, jobs, path):
        """One multi-page vector PDF with every label (qty pages per row). `jobs` = [(row_index, qty)]."""
        import fitz
        out = fitz.open()
        tmpdir = tempfile.mkdtemp(prefix="label_export_")
        try:
            for n, (i, q) in enumerate(jobs):
                cfg = bind_row_to_template(base_cfg, rows[i])
                p = os.path.join(tmpdir, f"{n}.pdf")
                save_exact_print_pdf(cfg, p)
                with fitz.open(p) as one:
                    for _ in range(max(1, int(q))):
                        out.insert_pdf(one)
            out.save(path)
        finally:
            out.close()
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ---- history (same files/format as the original: history.jsonl + history.csv + png/zpl/pdf per label)
    def record_history(self, cfg, printer, row=None, action="Print Current", template_name=""):
        if not self.history_enabled:
            return
        row = row or {}
        now = datetime.datetime.now()
        brand, model, code = _row_fields(row)
        record = {
            "timestamp": now.isoformat(timespec="seconds"), "action": action,
            "template": os.path.basename(template_name or ""), "printer": printer,
            "brand": brand, "model": model, "barcode": code, "price": row.get("Price", ""),
            "copies": cfg.get("copies", 1), "paper_width_mm": cfg.get("width_mm"), "paper_height_mm": cfg.get("height_mm"),
            "offset_x_mm": cfg.get("offset_x_mm", 0), "offset_y_mm": cfg.get("offset_y_mm", 0),
            "rotation_deg": cfg.get("rotation_deg", 0),
        }
        stem = now.strftime("%H%M%S_%f")[:10] + "_" + safe_filename(brand) + "_" + safe_filename(model) + "_" + safe_filename(code)
        sd = self.session_dir
        try:
            last = self._last_print
            if last and last[0] is cfg:
                _, exact_img, raw_bytes = last          # reuse what was just sent to the printer
            else:
                exact_img = render_print_hq(cfg, sd)
                raw_bytes = build_raw_gzpl(cfg, exact_img)
            exact_img.convert("L").save(os.path.join(sd, stem + ".png"))
            record["preview_png"] = stem + ".png"
            with open(os.path.join(sd, stem + ".zpl"), "wb") as rf:
                rf.write(raw_bytes)
            record["raw_file"] = stem + ".zpl"
            save_exact_print_pdf(cfg, os.path.join(sd, stem + ".pdf"))
            record["vector_pdf"] = stem + ".pdf"
        except Exception:
            record["preview_png"] = record["raw_file"] = record["vector_pdf"] = ""
        with open(os.path.join(sd, "history.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        csv_path = os.path.join(sd, "history.csv")
        exists = os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(record.keys()))
            if not exists:
                writer.writeheader()
            writer.writerow(record)
        self.history_rows.append(record)
