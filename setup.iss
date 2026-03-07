; =============================================================================
; Wedding Face Forward — Inno Setup Installer Script
; =============================================================================
;
; Compile with:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup.iss
;
; Output: Output\WeddingFaceForward_Setup.exe
;
; This creates a professional Windows installer that:
;   - Installs to Program Files by default
;   - Creates Start Menu and Desktop shortcuts
;   - Registers with Windows Add/Remove Programs
;   - Includes uninstaller
;   - Uses LZMA2 compression (~60% reduction)
; =============================================================================

#define MyAppName "Wedding Face Forward"
#define MyAppVersion "1.0.8"
#define MyAppPublisher "Wedding FaceForward"
#define MyAppURL "https://github.com/your-repo/wedding-face-forward"
#define MyAppExeName "WeddingFaceForward.exe"
#define MyAppAssocName "Wedding Face Forward"
#define MyAppAssocKey "WeddingFaceForward"

#define MyAppId "A7E3F2B1-8C4D-4E5F-9A0B-1C2D3E4F5A6B"

[Setup]
; App identity
AppId={{{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation directory
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

; Installer behavior
AllowNoIcons=yes
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Compression — LZMA2/max gives excellent ratio without excessive RAM usage
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4

; Output
OutputDir=Output
OutputBaseFilename=WeddingFaceForward_Setup_{#MyAppVersion}

; Appearance
SetupIconFile=WeddingFFapp_pyside\assets\logo.ico
WizardStyle=modern
WizardResizable=yes
WizardSizePercent=120

; Uninstall
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; Misc
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
MinVersion=10.0

; Version info embedded in Setup.exe
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenu";    Description: "Create a Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Install the entire PyInstaller output folder
; The source is dist\WeddingFaceForward\ which contains:
;   WeddingFaceForward.exe   (main executable)
;   _internal\              (all bundled files)
Source: "dist\WeddingFaceForward\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"; Tasks: startmenu
Name: "{group}\Uninstall {#MyAppName}";    Filename: "{uninstallexe}";        Tasks: startmenu

; Desktop
Name: "{autodesktop}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Option to launch after install
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up user data directory on uninstall (optional — comment out to keep user data)
; Type: filesandordirs; Name: "{localappdata}\WeddingFaceForward"

; Clean up any runtime-generated files in install dir
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\_internal\__pycache__"

[Code]
// =============================================================================
// Custom Pascal Script — Pre-install checks and post-install setup
// =============================================================================

function InitializeSetup(): Boolean;
begin
  Result := True;
  
  // Check for minimum Windows version (Windows 10+)
  if not IsWin64 then
  begin
    MsgBox('Wedding Face Forward requires a 64-bit version of Windows 10 or later.', 
           mbCriticalError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  UserDataDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Create the user data directory in %LOCALAPPDATA%
    UserDataDir := ExpandConstant('{localappdata}\WeddingFaceForward');
    if not DirExists(UserDataDir) then
    begin
      CreateDir(UserDataDir);
      Log('Created user data directory: ' + UserDataDir);
    end;

    // Create subdirectories
    if not DirExists(UserDataDir + '\logs') then
      CreateDir(UserDataDir + '\logs');
    if not DirExists(UserDataDir + '\data') then
      CreateDir(UserDataDir + '\data');
      
    Log('Post-install setup complete.');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataDir: String;
  Res: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    UserDataDir := ExpandConstant('{localappdata}\WeddingFaceForward');
    if DirExists(UserDataDir) then
    begin
      // Ask user if they want to remove their data
      Res := MsgBox(
        'Do you want to remove your Wedding Face Forward user data?' + #13#10 +
        '(Database, settings, credentials, and logs)' + #13#10 + #13#10 +
        'Location: ' + UserDataDir,
        mbConfirmation, MB_YESNO);
      
      if Res = IDYES then
      begin
        DelTree(UserDataDir, True, True, True);
        Log('Removed user data directory: ' + UserDataDir);
      end
      else
      begin
        Log('User chose to keep user data directory.');
      end;
    end;
  end;
end;
