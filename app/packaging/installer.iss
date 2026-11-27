; Inno Setup script: per-user install, no admin rights needed.
#define AppName "Générateur d'examens"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{7B1C1E52-4C1E-4E55-9C2B-3E8A0F6D2B41}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Cégep de Valleyfield
DefaultDirName={localappdata}\Programs\ExamGen
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=ExamGen-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "dist\ExamGen\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\ExamGen.exe"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\ExamGen.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ExamGen.exe"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent
