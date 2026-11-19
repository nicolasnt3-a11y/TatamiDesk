#ifndef MyAppVersion
  #define MyAppVersion "1.0.1"
#endif

[Setup]
AppId={{8E4A9F21-6C3D-4B5E-9A12-7F8E3D4C5B6A}
AppName=Tatami Desk
AppVersion={#MyAppVersion}
AppPublisher=Vincent Chapeau
AppPublisherURL=https://github.com/nicolasnt3-a11y/TatamiDesk
AppSupportURL=https://github.com/nicolasnt3-a11y/TatamiDesk/issues
AppUpdatesURL=https://github.com/nicolasnt3-a11y/TatamiDesk/releases
DefaultDirName={localappdata}\TatamiDesk
DefaultGroupName=Tatami Desk
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=dist
OutputBaseFilename=TatamiDesk-Setup-{#MyAppVersion}
SetupIconFile=assets\tatamidesk.ico
UninstallDisplayIcon={app}\TatamiDesk.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Lancer Tatami Desk au démarrage de Windows"; GroupDescription: "Options :"

[Files]
Source: "dist\TatamiDesk.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Tatami Desk"; Filename: "{app}\TatamiDesk.exe"
Name: "{group}\{cm:UninstallProgram,Tatami Desk}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Tatami Desk"; Filename: "{app}\TatamiDesk.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "TatamiDesk"; ValueData: """{app}\TatamiDesk.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\TatamiDesk.exe"; Description: "{cm:LaunchProgram,Tatami Desk}"; Flags: nowait postinstall skipifsilent
