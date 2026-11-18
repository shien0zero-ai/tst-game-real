param([string]$EngineRoot='D:\UE5\UE_5.8')
$ErrorActionPreference='Stop';$project=Split-Path $PSScriptRoot -Parent;$saved=Join-Path $project 'Saved'
$names=@('p38_shot_0','p38_shot_1','p38_shot_2','p38_tail_0','p38_tail_1','p38_mag_out');$missing=@($names|Where-Object {-not(Test-Path -LiteralPath "$project\Content\Forest\P38Field\$_.uasset")})
if(-not $missing.Count){Write-Output 'Licensed P38 assets present';return}
New-Item -ItemType Directory -Path $saved -Force|Out-Null
& "$EngineRoot\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" "$PSScriptRoot\prepare_p38_audio.py" --project $project --download
if($LASTEXITCODE){throw 'Free P38 source preparation failed'}
$proc=Start-Process -FilePath "$EngineRoot\Engine\Binaries\Win64\UnrealEditor.exe" -ArgumentList @("$project/AshgateForest.uproject","-ExecutePythonScript=$PSScriptRoot/import_p38_audio.py",'-RenderOffscreen','-unattended','-NoSplash',"-AbsLog=$saved/P38Import.log") -WindowStyle Hidden -PassThru;$h=$proc.Handle;$proc.WaitForExit()
if($proc.ExitCode -or -not(Select-String -LiteralPath "$saved/P38Import.log" -Pattern 'P38 AUDIO IMPORT COMPLETE' -Quiet)){throw 'P38 SoundWave import failed'}
