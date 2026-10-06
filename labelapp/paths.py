"""Locations of files shipped with the application (templates, QML, assets).

Works from a source checkout and from a PyInstaller bundle (``sys._MEIPASS``).
"""
import os
import sys


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
