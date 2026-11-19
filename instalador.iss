; instalador.iss — receta de Inno Setup para el instalador de mibarra.
; Se compila con:  iscc /DVersion=2.0.0 instalador.iss
; (antes hay que correr "python construir.py" para tener dist\mibarra)

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{6B1E2C34-8D5A-4F0B-9C77-2A4E91D3F5A8}
AppName=mibarra
AppVersion={#Version}
AppVerName=mibarra {#Version}
AppPublisher=Vecx06
AppPublisherURL=https://github.com/Vecx06/mibarra
AppSupportURL=https://github.com/Vecx06/mibarra/issues
AppUpdatesURL=https://github.com/Vecx06/mibarra/releases
DefaultDirName={autopf}\mibarra
DisableProgramGroupPage=yes
; Se instala solo para tu usuario: no pide permisos de administrador
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=mibarra-{#Version}-instalador
SetupIconFile=recursos\mibarra.ico
UninstallDisplayIcon={app}\mibarra.exe
UninstallDisplayName=mibarra
LicenseFile=LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Si mibarra está abierta, el instalador la cierra (usa el "mutex" que crea la barra)
AppMutex=mibarra_instancia
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "inicio"; Description: "Abrir mibarra al iniciar Windows"
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "dist\mibarra\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\mibarra"; Filename: "{app}\mibarra.exe"
Name: "{autoprograms}\Restaurar barra de Windows"; Filename: "{app}\mibarra.exe"; Parameters: "--restaurar"; Comment: "Úsalo si la barra de Windows quedó escondida"
Name: "{autodesktop}\mibarra"; Filename: "{app}\mibarra.exe"; Tasks: escritorio

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "mibarra"; ValueData: """{app}\mibarra.exe"""; Tasks: inicio; Flags: uninsdeletevalue

[Run]
Filename: "{app}\mibarra.exe"; Description: "Abrir mibarra ahora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Al desinstalar: cerrar mibarra (y su guardián) y dejar la barra de Windows como estaba
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM mibarra.exe"; Flags: runhidden; RunOnceId: "CerrarMibarra"
Filename: "{app}\mibarra.exe"; Parameters: "--restaurar"; Flags: runhidden waituntilterminated; RunOnceId: "RestaurarBarra"
