"""Locations of files shipped with the application (templates, QML, assets).

Works from a source checkout and from a PyInstaller bundle (``sys._MEIPASS``).
"""
import os
import re
import sys
from urllib.parse import unquote, urlparse

# str() of a PySide6 QUrl is its repr, e.g. "PySide6.QtCore.QUrl('file:///C:/logo.png')", not the URL itself.
_QURL_REPR = re.compile(r"""^\s*(?:PySide6\.QtCore\.)?QUrl\((['"])(.*)\1\)\s*$""")


def to_local_path(value):
    """Native file path from what QML file dialogs hand out: a QUrl object, a "file:///" URL string, a plain path,
    or the "PySide6.QtCore.QUrl('file:///...')" text that older versions saved into templates by mistake."""
    if value is None:
        return ""
    if hasattr(value, "toLocalFile"):                     # QUrl passed through as an object
        local = value.toLocalFile()
        return local if local else value.toString()
    s = str(value).strip()
    m = _QURL_REPR.match(s)
    if m:
        s = m.group(2)
    if s.lower().startswith("file:"):
        u = urlparse(s)
        p = unquote(u.path)
        if u.netloc and u.netloc.lower() != "localhost":  # UNC share: file://server/share/x
            p = "//" + u.netloc + p
        if re.match(r"^/[A-Za-z]:[/\\]", p):              # /C:/x -> C:/x
            p = p[1:]
        s = p
    return s


def app_root():
    """Folder that holds the shipped ``templates/`` directory.

    Source checkout: the repository root (parent of the ``labelapp`` package).
    Frozen build: the PyInstaller data directory.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def package_dir():
    return os.path.dirname(os.path.abspath(__file__))


def qml_dir():
    return os.path.join(package_dir(), "ui", "qml")
