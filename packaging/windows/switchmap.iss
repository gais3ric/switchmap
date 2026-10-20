; Установщик SwitchMap для Windows (Inno Setup 6). Собирается из packaging/build.py --installer:
;   ISCC /DAppVersion=1.2.3 /DSourceDir=<dist\switchmap> /DOutputDir=<dist> switchmap.iss
; Тихая установка: SwitchMap-Setup-X.exe /VERYSILENT [/NETWORK=1] [/PORT=5000]
; (NETWORK и PORT учитываются только при первой установке — дальше настройки берутся из switchmap.conf)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\switchmap"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{6E2C1A0B-5D7F-4B8E-9C3A-2F1D8E7B4A60}
AppName=SwitchMap
AppVersion={#AppVersion}
AppVerName=SwitchMap {#AppVersion}
AppPublisher=SwitchMap
DefaultDirName={autopf}\SwitchMap
DefaultGroupName=SwitchMap
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=SwitchMap-Setup-{#AppVersion}
SetupIconFile=switchmap.ico
UninstallDisplayIcon={app}\switchmap.exe
UninstallDisplayName=SwitchMap {#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#AppVersion}
VersionInfoDescription=SwitchMap — карта и мониторинг коммутаторов
CloseApplications=no
RestartApplications=no

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; Данные (база, ключи, копии, журнал) при удалении программы остаются
Name: "{commonappdata}\SwitchMap"; Flags: uninsneveruninstall

[INI]
Filename: "{app}\SwitchMap.url"; Section: "InternetShortcut"; Key: "URL"; String: "{code:GetUrl}"
Filename: "{app}\SwitchMap.url"; Section: "InternetShortcut"; Key: "IconFile"; String: "{app}\switchmap.exe"
Filename: "{app}\SwitchMap.url"; Section: "InternetShortcut"; Key: "IconIndex"; String: "0"

[Icons]
Name: "{group}\Открыть SwitchMap"; Filename: "{app}\SwitchMap.url"; IconFilename: "{app}\switchmap.exe"
Name: "{group}\Папка данных и журнал"; Filename: "{commonappdata}\SwitchMap"
Name: "{group}\Удалить SwitchMap"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\SwitchMap.url"; Description: "Открыть SwitchMap в браузере"; Flags: postinstall shellexec nowait skipifsilent

[UninstallRun]
Filename: "{app}\switchmap-service.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopService"
Filename: "{app}\switchmap-service.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveService"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""SwitchMap"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveFirewall"

[UninstallDelete]
Type: files; Name: "{app}\SwitchMap.url"

[Code]
const
  ServiceName = 'SwitchMap';

var
  AccessPage: TInputOptionWizardPage;
  PortPage: TInputQueryWizardPage;

function DataDir(): String;
begin
  Result := ExpandConstant('{commonappdata}\SwitchMap');
end;

function ConfFile(): String;
begin
  Result := DataDir() + '\switchmap.conf';
end;

function IsFirstInstall(): Boolean;
begin
  Result := not FileExists(ConfFile());
end;

{ Значение из switchmap.conf (КЛЮЧ=значение) или Default }
function ReadConf(Key, Default: String): String;
var
  Lines: TArrayOfString;
  I, P: Integer;
  Line: String;
begin
  Result := Default;
  if not LoadStringsFromFile(ConfFile(), Lines) then
    Exit;
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Trim(Lines[I]);
    if (Length(Line) > 0) and (Line[1] <> '#') then
    begin
      P := Pos('=', Line);
      if (P > 0) and (CompareText(Trim(Copy(Line, 1, P - 1)), Key) = 0) then
        Result := Trim(Copy(Line, P + 1, Length(Line)));
    end;
  end;
end;

function ChosenNetwork(): Boolean;
begin
  if WizardSilent() then
    Result := ExpandConstant('{param:NETWORK|0}') = '1'
  else
    Result := AccessPage.Values[1];
end;

function ChosenPort(): String;
begin
  if WizardSilent() then
    Result := ExpandConstant('{param:PORT|5000}')
  else
    Result := Trim(PortPage.Values[0]);
end;

function GetUrl(Param: String): String;
begin
  if IsFirstInstall() then
    Result := 'http://localhost:' + ChosenPort() + '/'
  else
    Result := 'http://localhost:' + ReadConf('SWITCHMAP_PORT', '5000') + '/';
end;

procedure InitializeWizard();
begin
  AccessPage := CreateInputOptionPage(wpSelectDir, 'Доступ к SwitchMap',
    'Откуда можно будет открыть веб-интерфейс?',
    'Позже это можно изменить в файле ' + ConfFile() + '.', True, False);
  AccessPage.Add('Только с этого компьютера (например, если перед SwitchMap будет HTTPS-прокси)');
  AccessPage.Add('Из сети — с других компьютеров (будет открыт порт в брандмауэре Windows)');
  AccessPage.Values[1] := True;

  PortPage := CreateInputQueryPage(AccessPage.ID, 'Порт', 'На каком порту работает веб-интерфейс?',
    'Обычно 5000. Укажите другой, если этот уже занят.');
  PortPage.Add('Порт:', False);
  PortPage.Values[0] := '5000';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  { При обновлении настройки уже есть — не спрашиваем }
  Result := ((PageID = AccessPage.ID) or (PageID = PortPage.ID)) and not IsFirstInstall();
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  N: Integer;
begin
  Result := True;
  if CurPageID = PortPage.ID then
  begin
    N := StrToIntDef(Trim(PortPage.Values[0]), 0);
    if (N < 1) or (N > 65535) then
    begin
      MsgBox('Порт — число от 1 до 65535.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function RunHidden(FileName, Params: String): Integer;
var
  Code: Integer;
begin
  if not Exec(FileName, Params, '', SW_HIDE, ewWaitUntilTerminated, Code) then
    Code := -1;
  Log(FileName + ' ' + Params + ' -> ' + IntToStr(Code));
  Result := Code;
end;

function ServiceExists(): Boolean;
begin
  Result := RunHidden(ExpandConstant('{sys}\sc.exe'), 'query ' + ServiceName) = 0;
end;

function ServiceStopped(): Boolean;
var
  Output: TExecOutput;
  Code: Integer;
begin
  Result := True;
  if ExecAndCaptureOutput(ExpandConstant('{sys}\sc.exe'), 'query ' + ServiceName, '', SW_HIDE,
                          ewWaitUntilTerminated, Code, Output) and (Code = 0) then
    Result := Pos('STOPPED', Uppercase(StringJoin(' ', Output.StdOut))) > 0;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  I: Integer;
begin
  Result := '';
  { Обновление: служба держит файлы программы — останавливаем и ждём (до 40 с) }
  if ServiceExists() then
  begin
    RunHidden(ExpandConstant('{sys}\sc.exe'), 'stop ' + ServiceName);
    for I := 1 to 80 do
    begin
      if ServiceStopped() then
        Break;
      Sleep(500);
    end;
    if not ServiceStopped() then
      Result := 'Не удалось остановить службу SwitchMap. Остановите её вручную и запустите установку снова.';
    Sleep(1000);
  end;
end;

procedure WriteConfig();
var
  Lines: TArrayOfString;
  I: Integer;
begin
  if not LoadStringsFromFile(ExpandConstant('{app}\switchmap.conf.example'), Lines) then
    Exit;
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    if Pos('SWITCHMAP_HOST=', Lines[I]) = 1 then
      if ChosenNetwork() then Lines[I] := 'SWITCHMAP_HOST=0.0.0.0' else Lines[I] := 'SWITCHMAP_HOST=127.0.0.1';
    if Pos('SWITCHMAP_PORT=', Lines[I]) = 1 then
      Lines[I] := 'SWITCHMAP_PORT=' + ChosenPort();
  end;
  SaveStringsToUTF8File(ConfFile(), Lines, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Svc, Sys: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  Svc := ExpandConstant('{app}\switchmap-service.exe');
  Sys := ExpandConstant('{sys}\');
  ForceDirectories(DataDir());
  if IsFirstInstall() then
  begin
    WriteConfig();
    RunHidden(Sys + 'netsh.exe', 'advfirewall firewall delete rule name="SwitchMap"');
    if ChosenNetwork() then
      RunHidden(Sys + 'netsh.exe', 'advfirewall firewall add rule name="SwitchMap" dir=in action=allow protocol=TCP localport='
        + ChosenPort() + ' program="' + ExpandConstant('{app}\switchmap.exe') + '"');
  end;
  { Папка данных: только SYSTEM, администраторы и служба (LocalService) — в ней ключи шифрования }
  { Сначала права самой папки (без унаследованных «Пользователи: чтение»), потом всё внутри — наследует их }
  RunHidden(Sys + 'icacls.exe', '"' + DataDir() + '" /inheritance:r /grant:r *S-1-5-18:(OI)(CI)F *S-1-5-32-544:(OI)(CI)F *S-1-5-19:(OI)(CI)M /C /Q');
  RunHidden(Sys + 'icacls.exe', '"' + DataDir() + '\*" /reset /T /C /Q');
  if not ServiceExists() then
    RunHidden(Svc, 'install');
  { Служба — под ограниченной учётной записью LocalService, а не SYSTEM }
  RunHidden(Sys + 'sc.exe', 'config ' + ServiceName + ' obj= "NT AUTHORITY\LocalService" password= ""');
  RunHidden(Svc, 'start');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent() then
    MsgBox('SwitchMap удалён. База, ключи шифрования, резервные копии и журнал остались в папке' + #13#10
      + DataDir() + #13#10 + 'Удалите её вручную, если они больше не нужны.', mbInformation, MB_OK);
end;
