ECG Label Tool v20.2 — Dynamic Data Fields

NEW
- Excel and Google Sheet columns are no longer treated as a fixed field list.
- Designer > + Field now opens a searchable field browser from the currently loaded source.
- The browser shows the current-row sample value for each source column.
- Select multiple columns and add them to the label in one action.
- Add any selected column as normal text or as a Code128 barcode.
- New Google Sheet columns become available after Reload Data / Reload Source, without editing app code.
- Main screen shows Fields (N) and can display every loaded source column.
- Templates bind directly with {{Exact Column Header}}. data_bindings remains supported for old templates.
- Blank and duplicate source headers are preserved as unique fields (Column_N / Name (2)).
- Field lookup has a trimmed, case-insensitive fallback for safer existing templates.
- Last Google Sheet source can be restored on startup, matching Excel persistence behavior.

WORKFLOW
1. Load Excel or Google Sheet.
2. If the source structure changes, click Reload Data.
3. Open Designer > + Field.
4. Search/select one or more columns.
5. Add as Text or Barcode.
6. Drag into position and Save Template.

PERSISTENCE
Existing template library, calibration profiles and workspace continue to use:
%APPDATA%\ECG_Label_Tool\
Updating the app folder does not remove them.
