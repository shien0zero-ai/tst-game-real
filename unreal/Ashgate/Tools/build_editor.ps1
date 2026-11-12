param([string]$EngineRoot='D:\UE5\UE_5.8')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Path "$projectRoot\Saved" -Force | Out-Null
& "$EngineRoot\Engine\Binaries\ThirdParty\DotNet\10.0\win-x64\dotnet.exe" "$EngineRoot\Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.dll" AshgateEditor Win64 Development "-Project=$projectRoot\Ashgate.uproject" -NoEngineChanges -NoHotReloadFromIDE "-Log=$projectRoot\Saved\EditorBuild.log"
exit $LASTEXITCODE
