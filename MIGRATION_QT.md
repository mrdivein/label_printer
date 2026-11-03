# Qt Quick (PySide6 / QML) migration — status

Run the new UI: `RUN.bat` (Windows) or `python -m labelapp`. The original Tkinter app still runs unchanged: `RUN_TK.bat` / `python app.py`.
Tests: `pip install -r requirements-dev.txt && python -m pytest tests`

## Architecture
```
QML (labelapp/ui/qml)  ->  bridge QObjects (labelapp/bridge)  ->  services / core (pure Python)
```
| Layer | Files | Role |
|---|---|---|
| core | `labelapp/core/` `label_engine` (raster/preview), `pdf_export` (vector master + HQ raster), `binding`, `preflight`, `test_patterns`, `compensation`, `profiles`, `editor` + `designer_geometry` (all designer editing rules, in mm) | No UI toolkit. `label_engine`, `pdf_export`, `binding`, … are the original code moved verbatim. |
| services | `labelapp/services/` `printer_service` (win32 spooler, ZPL), `print_service` (pipeline + history), `template_service`, `datasource_service` (Excel/Google/DataSet), `settings_service` (%APPDATA% storage), `workspace_service`, `profile_service`, `image_service` | I/O and storage; same files and keys as before. |
| bridge | `labelapp/bridge/` `DocumentController`, `DataController`, `PrintController`, `LibraryController`, `ProfileController`, `AppBridge` (composition root), models, image provider, `tasks` (thread pool) | Qt properties/signals/slots; no business rules. |
| UI | `labelapp/ui/qml/` `theme/Theme.qml` (tokens, light/dark), `components/`, `panels/`, `dialogs/`, `Main.qml` | Presentation only. |

Key design points
* Document coordinates are millimetres everywhere. QML sends pointer positions in mm (`screen = pan + mm * pxPerMm`); zoom/pan never touch the document (tested).
* The canvas shows the Python renderer's output (`image://preview`) with a QML overlay for selection/handles/guides; dragging shows a lightweight ghost and commits once on release (no re-render per mouse move).
* Blocking work off the UI thread only where it really blocks: Google Sheet / Excel loading, printer enumeration. Print jobs run one per event-loop tick (same as Tk) with progress, cancel and skip/retry/stop.
* The old `app.py` imports the same core (`labelapp`), so there is one source of truth; the Tk designer's own geometry code is still its own copy until it is retired.

## Backward compatibility
No storage schema changed (the data folder is now `%APPDATA%\LabelPrinter`; an earlier one is copied over on first start). Template JSON, `%APPDATA%\LabelPrinter` (templates, `printer_profiles.json`, `workspace_v20.json`, `data_sources.json`, `active_working_template.json`, backups, print history) are read/written identically. The Qt UI only *adds* keys prefixed `qt_` to the workspace file (`qt_window`, `qt_dark`).

## Migrated to Qt
Template library (list/preview/new/duplicate/rename/delete/import/export), save / save-as with backups, undo/redo, working-copy recovery, canvas (zoom, pan, rulers, select, marquee, drag, resize, rotate, fold line, print-area guide, nudge, copy/paste, align, lock, layer order), inspector for every element property, label/paper/compensation/quality settings, Excel + Google Sheet data (saved sources, search, row navigation), data-field picker, print current (preflight, confirmation), print selected/all queue with quantities, batch progress/cancel/skip/retry, PDF export of the queue, PDF proof, print via Windows driver, test prints (calibration, text/barcode quality, ruler overlay, compare sheets), measure & apply compensation, printer profiles, print history files, light/dark theme, quick scan with Instant print / Print last (Data tab, Ctrl+L), Batch Scan queue (F8: multi-code paste, glued-scan splitting, repeat mode, duplicate resolve, qty, remove-after-print).

## Still only in the Tkinter app (use `Data ▾ → Open legacy app`)
print-history viewer + reprint, guide (preview guides) editor, JSON editor, "print via PDF" route, threshold sweep test, printer sync/proof info dialogs beyond the basic summary.

## Verification status
| Item | Status |
|---|---|
| Core extraction is output-identical | 93 digests (render, preview, HQ raster, PDF raster, ZPL, test patterns, data helpers) identical before/after the move |
| Dimensions, ZPL header/copies, vector PDF page size, zoom-independence, editor, services, bridge, batch printing (printer mocked) | 57 automated tests pass (Linux, offscreen Qt) |
| Mouse/keyboard interaction (move, resize, rotate, marquee, fold, nudge, undo, Ctrl+wheel) | Driven with real synthetic Qt events against the running QML window (Linux, offscreen) |
| High-DPI (1.75x) and minimum window size (1060x640) layouts | Checked via screenshots (Linux, offscreen) |
| Real Windows printing, printed physical size, Windows DPI scaling, native file dialogs, PyInstaller `.exe` | **Not verified** — no Windows/printer in the dev sandbox. The print code is unchanged and called through `PrintService`; please print a compare sheet and a real label on the G530 before retiring Tk. `packaging_qt.spec` + `installer/label_printer.iss` are built by `.github/workflows/release.yml` (see README.txt, UPDATES). |

## Known issues / notes
* Previews use `render_label` (as the Tk app did); the HQ print route re-renders from the vector PDF, so tiny anti-aliasing differences between preview and print are possible, as before. Use "PDF proof" to inspect the exact print master.
* The legacy "print via PDF" rasteriser can come out 1 dot larger than the exact size (PyMuPDF rounding) — unchanged behaviour, not used by the main route.
* `fitz` import emits a PyMuPDF deprecation warning (unchanged).

## Next steps
1. Verify on Windows with the real printer; build and test the PyInstaller bundle.
2. Port the history viewer to QML (logic in `PrintService` already exists). Batch Scan has no live label preview pane yet (use "Show" to preview a queued row in the editor).
3. Retire the Tk designer (`VisualDesignerDialog`), then the rest of `app.py`.
