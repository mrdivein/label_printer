ECG Label Tool v18 - Free Canvas Designer

Run AUTO_SETUP_AND_RUN.bat on Windows for first setup, then RUN.bat.

New layout workflow:
JSON Editor -> Apply + Drag Edit -> drag elements -> Save JSON.

See README_V17.txt for details.

v20 NOTE
Templates and calibration profiles now use a persistent user library under %APPDATA%\ECG_Label_Tool so application updates do not remove them. See README_V20.txt.


V20.1 HOTFIX
- Fold line can be moved without shifting the visible back-face layout.
- Virtual print area has a live dashed drag/resize preview.

v20.2: Dynamic Excel/Google Sheet fields, searchable field picker, source reload, and persistent Google source restore. See README_V20_2.txt.


UPDATES (OTA)
The installer is published as a GitHub Release of this repository (it must be public: installed apps read
releases without a token). The installed app checks at start and every 4 hours, downloads a new version in
the background (size + SHA-256 checked) and shows "Restart to update x.y.z" in the top bar. If the app is
simply closed instead, the update is installed silently and the app starts new next time.
Updates and uninstall never touch %APPDATA%\ECG_Label_Tool (templates, profiles, workspace); bundled
templates are only copied there when missing, so edited templates are never overwritten.

Install on a new PC: download Label-Printer-Setup-x.y.z.exe from
https://github.com/mrdivein/label_printer/releases/latest and run it (no admin needed).

Release:
1. Raise __version__ in labelapp/version.py.
2. Merge to the default branch. GitHub Actions runs the tests, builds the exe (PyInstaller) and the installer
   (Inno Setup, installer/label_printer.iss) and publishes both plus latest.json as release v<version>.
   No secret is needed (it uses the workflow's own token). A version that is already released is skipped.
