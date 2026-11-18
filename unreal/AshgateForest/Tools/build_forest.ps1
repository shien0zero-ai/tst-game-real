param([string]$EngineRoot='D:\UE5\UE_5.8',[ValidateSet('Editor','Import','PIE','Windows','Verify')][string]$Action='Editor')
$ErrorActionPreference='Stop'
$forestProjectRoot=Split-Path $PSScriptRoot -Parent
$forestRepositoryRoot=Split-Path (Split-Path $forestProjectRoot -Parent) -Parent
$forestProject=Join-Path $forestProjectRoot 'AshgateForest.uproject'
$forestEngine=Join-Path $EngineRoot 'Engine'
$forestSaved=Join-Path $forestProjectRoot 'Saved'
$forestPython=Join-Path $forestEngine 'Binaries\ThirdParty\Python3\Win64\python.exe'
New-Item -ItemType Directory -Force -Path $forestSaved | Out-Null
if(Test-Path -LiteralPath (Join-Path $forestProjectRoot 'SourceArt\Packed\manifest.json')){& $forestPython (Join-Path $PSScriptRoot 'restore_assets.py');if($LASTEXITCODE){throw 'Packed asset restoration failed'}}
if($Action -in @('PIE','Windows','Verify')){& (Join-Path $PSScriptRoot 'ensure_p38.ps1') -EngineRoot $EngineRoot}
switch($Action){
'Editor' {& (Join-Path $forestEngine 'Binaries\ThirdParty\DotNet\10.0\win-x64\dotnet.exe') (Join-Path $forestEngine 'Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.dll') AshgateForestEditor Win64 Development "-Project=$forestProject" -NoEngineChanges -NoHotReloadFromIDE;if($LASTEXITCODE){throw 'Editor build failed'};& (Join-Path $PSScriptRoot 'ensure_p38.ps1') -EngineRoot $EngineRoot}
'Import' {$p=Start-Process -FilePath (Join-Path $forestEngine 'Binaries\Win64\UnrealEditor.exe') -ArgumentList @($forestProject,"-ExecutePythonScript=$PSScriptRoot/import_entry.py",'-unattended','-NoSplash','-RenderOffscreen',"-AbsLog=$forestSaved/ForestImport.log") -WindowStyle Hidden -PassThru;$forestProcessHandle=$p.Handle;$p.WaitForExit();if($p.ExitCode -or -not (Select-String -LiteralPath "$forestSaved/ForestImport.log" -Pattern 'FOREST IMPORT COMPLETE' -Quiet)){throw 'Asset import failed'}}
'PIE' {$p=Start-Process -FilePath (Join-Path $forestEngine 'Binaries\Win64\UnrealEditor.exe') -ArgumentList @($forestProject,'-ForestQA','-RenderOffscreen','-unattended','-NoSplash','-ExecCmds=Forest.PIEVerify',"-AbsLog=$forestSaved/PIE-QA.log") -WindowStyle Hidden -PassThru;$forestProcessHandle=$p.Handle;$p.WaitForExit();if($p.ExitCode -or -not (Select-String -LiteralPath "$forestSaved/PIE-QA.log" -Pattern 'QA COMPLETE failures=0' -Quiet)){throw 'PIE verification failed'}}
'Windows' {& (Join-Path $forestEngine 'Build\BatchFiles\RunUAT.bat') BuildCookRun "-project=$forestProject" -noP4 -platform=Win64 -clientconfig=Development -build -cook -stage -pak -iostore -compressed -archive "-archivedirectory=$forestRepositoryRoot/work/forest-package" -prereqs -unattended -utf8output -nocompileeditor -installed;if($LASTEXITCODE){throw 'Packaging failed'}}
'Verify' {$p=Start-Process -FilePath "$forestRepositoryRoot/work/forest-package/Windows/AshgateForest.exe" -ArgumentList @('-ForestQA','-RenderOffscreen','-ForceRes','-windowed','-ResX=1600','-ResY=900',"-AbsLog=$forestSaved/PackagedQA.log") -WindowStyle Hidden -PassThru;$forestProcessHandle=$p.Handle;$p.WaitForExit();if($p.ExitCode -or -not (Select-String -LiteralPath "$forestSaved/PackagedQA.log" -Pattern 'QA COMPLETE failures=0' -Quiet)){throw 'Windows verification failed'}}
}
