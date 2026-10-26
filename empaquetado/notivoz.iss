; Instalador de Notivoz (Inno Setup 6).
;
; Lo compila empaquetado\construir.py (no hace falta abrirlo a mano):
;   ISCC.exe /DVersion=0.1.0 empaquetado\notivoz.iss
;
; - Se instala para el usuario actual, sin pedir permisos de administrador.
; - Las actualizaciones usan este mismo instalador en modo silencioso: reemplaza
;   los archivos de la app y vuelve a abrir Notivoz. Los datos del usuario
;   (%APPDATA%\Notivoz: tareas, notas, ajustes, modelos de voz) nunca se tocan.

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
; Identificador fijo: así Windows sabe que cada versión actualiza a la anterior.
AppId={{C4EB275D-4346-42DD-9DBF-9D4154A6F7D2}
AppName=Notivoz
AppVersion={#Version}
AppVerName=Notivoz {#Version}
AppPublisher=Notivoz
AppPublisherURL=https://github.com/Jhere03/notivoz
AppSupportURL=https://github.com/Jhere03/notivoz
DefaultDirName={localappdata}\Programs\Notivoz
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist\instalador
OutputBaseFilename=Notivoz-Setup-{#Version}
SetupIconFile=..\assets\notivoz.ico
UninstallDisplayIcon={app}\Notivoz.exe
UninstallDisplayName=Notivoz
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
; Notivoz vive en la bandeja (al pedirle que se cierre, se oculta): lo cierra
; el propio instalador en PrepareToInstall, más abajo.
CloseApplications=no
RestartApplications=no
VersionInfoVersion={#Version}
VersionInfoProductName=Notivoz

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
spanish.WelcomeLabel2=Esto instalará [name/ver] en tu equipo.%n%nNotivoz organiza tus tareas, notas y recordatorios con la voz.%n%nTe recomendamos cerrar las demás aplicaciones antes de continuar.

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"
Name: "inicio"; Description: "Iniciar Notivoz al encender la PC (en la bandeja, junto al reloj)"; GroupDescription: "Inicio:"

[Files]
Source: "..\dist\Notivoz\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Una actualización limpia la versión anterior de la app (no los datos del usuario).
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{userprograms}\Notivoz"; Filename: "{app}\Notivoz.exe"; Comment: "Tus pendientes, con voz"
Name: "{userdesktop}\Notivoz"; Filename: "{app}\Notivoz.exe"; Tasks: escritorio; Comment: "Tus pendientes, con voz"

[Registry]
; Mismo registro que usa Notivoz en Configuración → Inicio con Windows.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Notivoz"; ValueData: """{app}\Notivoz.exe"" --inicio"; Tasks: inicio; Flags: uninsdeletevalue

[Run]
; Instalación normal: casilla «Abrir Notivoz» al terminar.
Filename: "{app}\Notivoz.exe"; Description: "Abrir Notivoz"; Flags: nowait postinstall skipifsilent
; Actualización (modo silencioso): volver a abrir Notivoz solo.
Filename: "{app}\Notivoz.exe"; Flags: nowait skipifnotsilent

[UninstallRun]
; Al desinstalar, cerrar Notivoz si sigue abierto en la bandeja.
Filename: "{cmd}"; Parameters: "/C taskkill /IM Notivoz.exe /F"; Flags: runhidden; RunOnceId: "CerrarNotivoz"

[Code]
// Antes de copiar archivos, cerrar Notivoz si está abierto (en la bandeja o
// recién cerrándose tras pulsar «Actualizar»). Sus datos ya están guardados:
// cada cambio se escribe en la base de datos al momento.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM Notivoz.exe /F', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Sleep(800);
  Result := '';
end;
