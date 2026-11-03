"""The Windows build is published in a public repository: what it bundles must hold no company data.

PyInstaller bundles the `labelapp` package and `sample_templates/` (see packaging_qt.spec). Company
templates (`templates/`) and example data stay in this private repository and are not bundled.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED = ["labelapp", "sample_templates", "installer"]
# Company name, address, real brands/suppliers and price formats that appear in the private templates and data.
DENY = [r"eyewear", r"consulting\s+group", r"c[ôo]ng\s+ty", r"long\s+tr[ưu][ờo]ng", r"đường\s+d\b",
        r"marcolin", r"tom\s+ford", r"\bVND\b", r"docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]{20,}"]


def _files():
    for top in BUNDLED:
        for dirpath, _dirs, names in os.walk(os.path.join(ROOT, top)):
            if "__pycache__" in dirpath:
                continue
            for n in names:
                if n.endswith((".py", ".qml", ".json", ".js", ".iss", ".svg", ".txt", ".md", "qmldir")):
                    yield os.path.join(dirpath, n)


def test_bundled_files_hold_no_company_data():
    hits = []
    for p in _files():
        text = open(p, encoding="utf-8", errors="replace").read()
        for pat in DENY:
            for m in re.finditer(pat, text, re.IGNORECASE):
                hits.append("%s: %r" % (os.path.relpath(p, ROOT), m.group(0)))
    assert not hits, "company data in the public build:\n" + "\n".join(hits)


def test_spec_bundles_only_the_sample_templates():
    spec = open(os.path.join(ROOT, "packaging_qt.spec"), encoding="utf-8").read()
    assert '("sample_templates", "templates")' in spec
    assert '("templates", "templates")' not in spec
