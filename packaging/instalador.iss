; Windows installer for Lector-PDF (Inno Setup 6).
; Built by GitHub Actions:  ISCC /DAppVersion=0.1.0 packaging\instalador.iss
; Installs for the current user only, so it never asks for administrator rights.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F6C2C0B-8B0E-4B6E-9C39-5D2A1C7E4F10}
AppName=Lector-PDF
AppVersion={#AppVersion}
AppPublisher=Lector-PDF
AppPublisherURL=https://github.com/Lehendakari02/Lector-PDF
DefaultDirName={localappdata}\Programs\Lector-PDF
DefaultGroupName=Lector-PDF
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=Lector-PDF-instalador
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=lector-pdf.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Lector-PDF.exe

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; portable.txt is excluded on purpose: the installed version keeps its data in
; the user's application data folder.
Source: "..\dist\Lector-PDF\*"; DestDir: "{app}"; Excludes: "portable.txt"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Lector-PDF"; Filename: "{app}\Lector-PDF.exe"
Name: "{autodesktop}\Lector-PDF"; Filename: "{app}\Lector-PDF.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Lector-PDF.exe"; Description: "{cm:LaunchProgram,Lector-PDF}"; Flags: nowait postinstall skipifsilent
