param([string]$EngineRoot='D:\UE5\UE_5.8',[ValidateSet('Editor','Prepare','Bake','PIE','Windows','Verify')][string]$Action='Editor')
$ErrorActionPreference='Stop'
$p=Split-Path $PSScriptRoot -Parent;$r=Split-Path (Split-Path $p -Parent) -Parent;$e=Join-Path $EngineRoot 'Engine';$s=Join-Path $p 'Saved';$project=Join-Path $p 'AshgateForestLightingLab.uproject'
New-Item -ItemType Directory -Force -Path $s|Out-Null
& "$e/Binaries/ThirdParty/Python3/Win64/python.exe" "$PSScriptRoot/restore_shared_content.py";if($LASTEXITCODE){throw 'Shared content restoration failed'}
function Editor([string[]]$Extra,[string]$Name){$q=Start-Process -FilePath "$e/Binaries/Win64/UnrealEditor.exe" -ArgumentList (@($project,'-NoSplash','-unattended','-RenderOffscreen',"-AbsLog=$s/$Name.log")+$Extra) -WindowStyle Hidden -PassThru;$h=$q.Handle;$q.WaitForExit();if($q.ExitCode){throw "$Name failed"}}
& "$e/Binaries/ThirdParty/Python3/Win64/python.exe" "$PSScriptRoot/restore_baked_lighting.py";if($LASTEXITCODE){throw 'Baked lighting restoration failed'}
switch($Action){
 'Editor'{& "$e/Binaries/ThirdParty/DotNet/10.0/win-x64/dotnet.exe" "$e/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll" AshgateForestLightingLabEditor Win64 Development "-Project=$project" -NoEngineChanges -NoHotReloadFromIDE;if($LASTEXITCODE){throw 'Lab Editor build failed'}}
 # Prepare deliberately replaces this lab's patch/lightmap. Normal builds use the saved, versioned bake.
 'Prepare'{Editor @("-ExecutePythonScript=$PSScriptRoot/prepare_lab_assets.py") 'PrepareAssets';Editor @("-ExecutePythonScript=$PSScriptRoot/create_patch.py") 'CreatePatch'}
 'Bake'{Editor @('-ExecCmds=ForestLab.Bake') 'Bake';if(-not(Select-String "$s/Bake.log" -Pattern 'LAB BAKE COMPLETE' -Quiet)){throw 'Lighting build did not produce saved lightmaps'};& "$e/Binaries/ThirdParty/Python3/Win64/python.exe" "$PSScriptRoot/pack_baked_lighting.py";if($LASTEXITCODE){throw 'Lighting preservation failed'}}
 'PIE'{Editor @('-ForestQA','-ExecCmds=Forest.PIEVerify') 'PIE-QA';if(-not(Select-String "$s/PIE-QA.log" -Pattern 'QA COMPLETE failures=0' -Quiet)){throw 'PIE QA failed'}}
 'Windows'{& "$e/Build/BatchFiles/RunUAT.bat" BuildCookRun "-project=$project" -noP4 -platform=Win64 -clientconfig=Development -build -cook -stage -pak -iostore -compressed -archive "-archivedirectory=$r/work/forest-lighting-lab-package" -prereqs -unattended -utf8output -nocompileeditor -installed;if($LASTEXITCODE){throw 'Lab Windows packaging failed'}}
 'Verify'{$q=Start-Process -FilePath "$r/work/forest-lighting-lab-package/Windows/AshgateForestLightingLab.exe" -ArgumentList @('-ForestQA','-RenderOffscreen','-ForceRes','-windowed','-ResX=1920','-ResY=1080',"-AbsLog=$s/PackagedQA.log") -WindowStyle Hidden -PassThru;$h=$q.Handle;$q.WaitForExit();if($q.ExitCode -or -not(Select-String "$s/PackagedQA.log" -Pattern 'QA COMPLETE failures=0' -Quiet)){throw 'Native QA failed'}}
}
