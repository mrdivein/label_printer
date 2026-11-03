# PyInstaller spec for the Qt Quick / QML build.   Build on Windows:
#     pip install pyinstaller
#     pyinstaller packaging_qt.spec
# Output: dist/LabelPrinter/LabelPrinter.exe   (one-folder build; installer/label_printer.iss turns it into the setup)
#
# The build is published publicly, so it must carry no company data: only the neutral sample template
# (sample_templates/) is bundled. Company templates stay in this private repo and in each PC's
# %APPDATA%\ECG_Label_Tool\templates, which updates never touch.
from PyInstaller.utils.hooks import collect_data_files

datas = [
    ("labelapp/ui/qml", "labelapp/ui/qml"),        # QML sources (components, panels, dialogs, theme)
    ("labelapp/ui/resources", "labelapp/ui/resources"),
    ("sample_templates", "templates"),             # seeded into %APPDATA%\ECG_Label_Tool\templates when missing
]
datas += collect_data_files("reportlab")           # reportlab fonts/resources
hidden = ["win32print", "win32api", "fitz", "barcode.codex", "barcode.ean", "barcode.isxn", "barcode.upc", "barcode.itf"]

a = Analysis(["labelapp/__main__.py"], pathex=["."], datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LabelPrinter", console=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="LabelPrinter")
