ECG Label Tool v20.1 — Designer Hotfix

Fixes
- Fold boundary drag no longer makes the whole folded/back face jump.
  Existing elements already on the 180° back face are compensated automatically so their final visual/printed position stays fixed while only the fold boundary changes.
- Virtual Print Area now shows a live dashed ghost outline while moving or resizing, before the change is committed.
- Fold boundary also shows a dashed NEW FOLD preview while dragging.

Persistence
- Uses the same %APPDATA%\ECG_Label_Tool data location and workspace_v20.json as v20.
- Existing templates, printer profiles, calibration, recent source settings and working recovery remain available after replacing the application folder.

Notes
- Virtual Print Area remains a visual guide only and never clips print output.
- The fold boundary is still the actual 180° fold-region boundary; moving it updates the fold region but preserves the existing back-face layout visually.
