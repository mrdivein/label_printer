; Inno Setup script: per-user installer for the PyInstaller build in dist\LabelPrinter.
;   iscc /DAppVersion=22.1.0 installer\label_printer.iss   ->  dist\Label-Printer-Setup-22.1.0.exe
; Installs to %LOCALAPPDATA%\Programs\Label Printer without admin rights. User data in
; %APPDATA%\LabelPrinter (templates, profiles, workspace) is never touched by install, update or uninstall.
; The app updates itself by running this installer with /VERYSILENT; it then restarts the app
; unless /NORELAUNCH=1 is passed (update installed while the app was being closed).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B1F0C52-8E3A-4D57-9A41-3C2D7F5E9A10}
AppName=Label Printer
AppVersion={#AppVersion}
AppVerName=Label Printer {#AppVersion}
DefaultDirName={localappdata}\Programs\Label Printer
DefaultGroupName=Label Printer
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Label-Printer-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
SetupIconFile=..\labelapp\ui\resources\app.ico
UninstallDisplayIcon={app}\LabelPrinter.exe
ArchitecturesInstallIn64BitMode=x64compatible

[InstallDelete]
; old program files from a previous version (not user data)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\LabelPrinter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Label Printer"; Filename: "{app}\LabelPrinter.exe"
Name: "{autodesktop}\Label Printer"; Filename: "{app}\LabelPrinter.exe"

[Run]
Filename: "{app}\LabelPrinter.exe"; Description: "Start Label Printer"; Flags: nowait postinstall; Check: ShouldRelaunch

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := ExpandConstant('{param:NORELAUNCH|0}') <> '1';
end;
