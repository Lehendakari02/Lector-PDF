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
; The program is offered for PDFs ("Abrir con", default programs): see [Registry].
ChangesAssociations=yes

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

[Registry]
; Offers the program to Windows for PDFs, for this user only. It does not make
; itself the default program: Windows asks the user. Keep these lines the same as
; app/core/file_association.py (a test compares them).
Root: HKA; Subkey: "Software\Classes\LectorPDF.Documento"; ValueType: string; ValueData: "Documento PDF"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\LectorPDF.Documento\DefaultIcon"; ValueType: string; ValueData: """{app}\Lector-PDF.exe"",0"
Root: HKA; Subkey: "Software\Classes\LectorPDF.Documento\shell\open\command"; ValueType: string; ValueData: """{app}\Lector-PDF.exe"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "LectorPDF.Documento"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\Lector-PDF.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Lector-PDF"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\Lector-PDF.exe\shell\open\command"; ValueType: string; ValueData: """{app}\Lector-PDF.exe"" ""%1"""
Root: HKA; Subkey: "Software\Classes\Applications\Lector-PDF.exe\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""
Root: HKA; Subkey: "Software\Lector-PDF\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Lector-PDF"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Lector-PDF\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Lee, estudia, rellena y firma tus PDF. Todo se queda en tu ordenador."; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Lector-PDF\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "LectorPDF.Documento"
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Lector-PDF"; ValueData: "Software\Lector-PDF\Capabilities"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Lector-PDF.exe"; Description: "{cm:LaunchProgram,Lector-PDF}"; Flags: nowait postinstall skipifsilent
