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


UPDATES (OTA) — like Ops Desk
Source stays in this PRIVATE repo. Only the Windows installer is published to the PUBLIC repo
mrdivein/label-printer-releases. The installed app checks it at start and every 4 hours, downloads a new
version in the background (size + SHA-256 checked) and shows "Restart to update x.y.z" in the top bar.
If the app is simply closed instead, the update is installed silently and the app starts new next time.
Updates and uninstall never touch %APPDATA%\ECG_Label_Tool (templates, profiles, workspace).

Install on a new PC: download Label-Printer-Setup-x.y.z.exe from
https://github.com/mrdivein/label-printer-releases/releases/latest and run it (no admin needed).
The public installer contains only a neutral sample template; import your company templates with
Library -> Load template, or copy the %APPDATA%\ECG_Label_Tool folder from another PC.

Release:
1. Raise __version__ in labelapp/version.py.
2. Merge to main. GitHub Actions runs the tests, builds the exe (PyInstaller) and the installer
   (Inno Setup, installer/label_printer.iss) and publishes both plus latest.json to label-printer-releases.
One-time setup:
- Create the public repo mrdivein/label-printer-releases with a README (it needs one commit).
- Add the repository secret RELEASES_TOKEN here: a fine-grained token limited to label-printer-releases,
  Contents: read and write. Without it the release job is skipped.
No company data in the public build: tests/test_public_build.py fails if anything bundled
(labelapp/, sample_templates/, installer/) contains the company name, address, brands or a Sheet id.
templates/ and Example_Label_Data.xlsx are NOT bundled.
