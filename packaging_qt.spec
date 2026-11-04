# PyInstaller spec for the Qt Quick / QML build.   Build on Windows:
#     pip install pyinstaller
#     pyinstaller packaging_qt.spec
# Output: dist/LabelPrinter/LabelPrinter.exe   (one-folder build; installer/label_printer.iss turns it into the setup)
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ("labelapp/ui/qml", "labelapp/ui/qml"),        # QML sources (components, panels, dialogs, theme)
    ("labelapp/ui/resources", "labelapp/ui/resources"),
    ("templates", "templates"),                    # seeded into %APPDATA%\LabelPrinter\templates when missing (never overwrites)
]
datas += collect_data_files("reportlab")           # reportlab fonts/resources
hidden = ["win32print", "win32api", "fitz", "barcode.codex", "barcode.ean", "barcode.isxn", "barcode.upc", "barcode.itf"]
# reportlab.graphics.barcode loads its symbologies through exec() on package import: PyInstaller cannot see them,
# and one missing module breaks every Code128/QR preview, print and PDF.
hidden += collect_submodules("reportlab.graphics.barcode")

a = Analysis(["labelapp/__main__.py"], pathex=["."], datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LabelPrinter", console=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="LabelPrinter")
