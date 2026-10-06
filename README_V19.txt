ECG LABEL TOOL v20 — ZOOM DESIGNER + PERSISTENT TEMPLATE LIBRARY

Main changes from v18

1. Designer zoom
- Default designer zoom: 200% of Fit.
- Zoom presets: 75% to 500%.
- +/- buttons.
- Fit button.
- Ctrl + mouse wheel: zoom.
- Mouse wheel: vertical scroll.
- Shift + mouse wheel: horizontal scroll.
- Scrollbars remain available while zoomed.
- Dragging works correctly while the canvas is scrolled.

2. Persistent template library
- Templates are no longer saved inside the version folder by default.
- User template library is stored at:
  %APPDATA%\ECG_Label_Tool\templates
- Updating or replacing the application folder does not remove this library.
- Bundled templates are copied into the persistent library only when missing.
- Existing user templates are never overwritten automatically.

3. Load Template
- Main window: Load Template...
- Designer: Load Template...
- Loading an external JSON imports a copy into the persistent template library.
- Library button opens the persistent template folder.

4. Calibration profiles also persist
- Printer/calibration profiles are stored at:
  %APPDATA%\ECG_Label_Tool\printer_profiles.json
- Profiles therefore remain available after app updates.

UPGRADING FROM v18 OR EARLIER
1. Start v20 once.
2. Click Load Template...
3. Select any custom JSON from the old version's templates folder.
4. v20 copies it into the persistent library.
5. Future v20+ updates can keep using the same library automatically.

The free-canvas rule from v18 is unchanged:
- Nominal paper and Virtual Print Area remain visual guides only.
- They do not clip printing or restrict dragging.
