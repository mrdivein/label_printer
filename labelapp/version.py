"""Application version and the public place updates come from.

The release workflow reads ``__version__``: raising it on ``main`` builds a new installer and publishes it.
"""
__version__ = "22.1.0"

# Public repository that holds only the Windows installers (no source, no company data).
UPDATE_REPO = "mrdivein/label-printer-releases"
