param([string]$EngineRoot='D:\UE5\UE_5.8')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$repoRoot=Split-Path (Split-Path $projectRoot -Parent) -Parent
$archiveRoot=Join-Path $repoRoot 'work\ue5-package'
New-Item -ItemType Directory -Path "$projectRoot\Saved" -Force | Out-Null
& "$EngineRoot\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun "-project=$projectRoot\Ashgate.uproject" -noP4 -platform=Win64 -clientconfig=Development -build -cook -stage -pak -iostore -compressed -archive "-archivedirectory=$archiveRoot" -prereqs -unattended -utf8output -nocompileeditor -installed *> "$projectRoot\Saved\PackageBuild-console.txt"
if ($LASTEXITCODE -ne 0) { throw "Packaging failed ($LASTEXITCODE). See Saved\PackageBuild-console.txt" }
Write-Output "Package created: $archiveRoot\Windows"
Write-Output 'Run the packaged executable and validate it before creating a release ZIP.'
