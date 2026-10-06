# PyInstaller spec for the Qt Quick / QML build.   Build on Windows:
#     pip install pyinstaller
#     pyinstaller packaging_qt.spec
# Output: dist/ECG_Label_Tool/ECG_Label_Tool.exe   (one-folder build; faster start, easier to debug than one-file)
from PyInstaller.utils.hooks import collect_data_files

datas = [
    ("labelapp/ui/qml", "labelapp/ui/qml"),        # QML sources (components, panels, dialogs, theme)
    ("labelapp/ui/resources", "labelapp/ui/resources"),
    ("templates", "templates"),                    # bundled templates seeded into %APPDATA%\ECG_Label_Tool\templates
]
datas += collect_data_files("reportlab")           # reportlab fonts/resources
hidden = ["win32print", "win32api", "fitz", "barcode.codex", "barcode.ean", "barcode.isxn", "barcode.upc", "barcode.itf"]

a = Analysis(["labelapp/__main__.py"], pathex=["."], datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ECG_Label_Tool", console=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="ECG_Label_Tool")
