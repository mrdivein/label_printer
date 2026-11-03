# Label Printer

A desktop app for designing and printing labels and hang tags on thermal or office printers.
Design a template on a free canvas (text, barcodes, QR codes, images, lines, boxes, fold lines),
bind it to columns of an Excel file or a Google Sheet with `{{Column}}`, and print one label or a whole list.

- Templates are plain JSON files; sizes are in millimetres. Three example templates are in `templates/`
  and `Example_Label_Data.xlsx` holds matching sample rows (all data is fictitious).
- Printing: RAW ZPL to label printers, or the Windows driver; PDF proof and PDF export of a print queue.
- Calibration: test prints, measured scale/offset compensation and saved printer profiles.

## Install (Windows)
Download `Label-Printer-Setup-x.y.z.exe` from [Releases](https://github.com/mrdivein/label_printer/releases/latest)
and run it (no admin rights needed).

## Updates
The installed app checks for a new version at start and every 4 hours, downloads it in the background
(size and SHA-256 checked) and shows "Restart to update x.y.z" in the top bar. If the app is simply closed,
the update is installed silently and the app starts new next time.
User data in `%APPDATA%\LabelPrinter` (templates, printer profiles, workspace) is kept by updates and uninstall.

## Run from source
`RUN.bat` on Windows, or:
```
pip install -r requirements.txt
python -m labelapp
```
Tests: `pip install -r requirements-dev.txt && python -m pytest tests` (see `MIGRATION_QT.md` for the architecture).

## Release
1. Raise `__version__` in `labelapp/version.py`.
2. Merge to the default branch. GitHub Actions runs the tests, builds the exe (PyInstaller) and the installer
   (Inno Setup, `installer/label_printer.iss`) and publishes both plus `latest.json` as release `v<version>`.
