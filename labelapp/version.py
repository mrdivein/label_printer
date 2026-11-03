"""Application version and the public place updates come from.

The release workflow reads ``__version__``: raising it on the default branch builds a new installer and publishes it.
"""
__version__ = "22.2.0"

# Public repository whose GitHub Releases hold the Windows installer (this repository).
UPDATE_REPO = "mrdivein/label_printer"
