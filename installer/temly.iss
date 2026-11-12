; Inno Setup script: per-user installer for the PyInstaller build in dist\Temly.
;   iscc /DAppVersion=22.1.0 installer\temly.iss   ->  dist\Temly-Setup-22.1.0.exe
; Installs to %LOCALAPPDATA%\Programs\Temly without admin rights. User data in
; %APPDATA%\Temly (templates, profiles, workspace) is never touched by install, update or uninstall.
; The app updates itself by running this installer with /VERYSILENT; it then restarts the app
; unless /NORELAUNCH=1 is passed (update installed while the app was being closed).
;
; Formerly "Label Printer". The AppId is unchanged, so this installer upgrades an existing Label Printer
; install in place (same folder, same uninstall entry) instead of installing a second copy. The app copies
; %APPDATA%\LabelPrinter into %APPDATA%\Temly on first start and leaves the old folder as it was.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B1F0C52-8E3A-4D57-9A41-3C2D7F5E9A10}
AppName=Temly
AppVersion={#AppVersion}
AppVerName=Temly {#AppVersion}
AppPublisher=Temly
AppComments=Label, barcode and hang tag designer for thermal and office printers
DefaultDirName={localappdata}\Programs\Temly
DefaultGroupName=Temly
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Temly-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
SetupIconFile=..\labelapp\ui\resources\app.ico
UninstallDisplayIcon={app}\Temly.exe
UninstallDisplayName=Temly
ArchitecturesInstallIn64BitMode=x64compatible

[InstallDelete]
; old program files from a previous version (not user data)
Type: filesandordirs; Name: "{app}\_internal"
; leftovers of the "Label Printer" name: old executable, shortcuts and downloaded updates
Type: files; Name: "{app}\LabelPrinter.exe"
Type: files; Name: "{autoprograms}\Label Printer.lnk"
Type: files; Name: "{autodesktop}\Label Printer.lnk"
Type: filesandordirs; Name: "{localappdata}\LabelPrinter\updates"
Type: dirifempty; Name: "{localappdata}\LabelPrinter"

[Files]
Source: "..\dist\Temly\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Temly"; Filename: "{app}\Temly.exe"
Name: "{autodesktop}\Temly"; Filename: "{app}\Temly.exe"

[Run]
Filename: "{app}\Temly.exe"; Description: "Start Temly"; Flags: nowait postinstall; Check: ShouldRelaunch

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := ExpandConstant('{param:NORELAUNCH|0}') <> '1';
end;
