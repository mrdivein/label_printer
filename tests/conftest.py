import json
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def isolated_appdata(tmp_path, monkeypatch):
    """Never touch the real %APPDATA%\\LabelPrinter during tests."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    return tmp_path / "appdata"


@pytest.fixture
def templates():
    out = {}
    tdir = os.path.join(ROOT, "templates")
    for n in sorted(os.listdir(tdir)):
        if n.endswith(".json"):
            with open(os.path.join(tdir, n), encoding="utf-8") as f:
                out[n] = json.load(f)
    return out


@pytest.fixture
def sample_row():
    return {"Brand": "NORTHWIND", "Model": "NW-1040", "Price": "1,290,000 VND", "Barcode": "012345678905",
            "Manufacturer": "SAMPLE MANUFACTURING LTD.", "ManufacturerCountry": "JAPAN", "ProductType": "Sản phẩm mẫu", "Origin": "Nhật Bản", "Importer": "CÔNG TY TNHH MẪU ABC", "ImporterAddress": "123 Đường Mẫu, Quận 1, TP Hồ Chí Minh", "Material": "Nhựa / Kim loại", "Usage": "Bảo quản nơi khô ráo", "Copies": 2}


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication(["tests"])
    yield app
