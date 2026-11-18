param([ValidateSet('Full','Lumen','Baked','Original')][string]$Variant='Baked')
$ErrorActionPreference='Stop';$p=Split-Path $PSScriptRoot -Parent;$r=Split-Path (Split-Path $p -Parent) -Parent;$s="$p\Saved";$exe="$r\work\forest-lighting-lab-package\Windows\AshgateForestLightingLab.exe";$name=$Variant+'-'+(Get-Date -Format HHmmss);$log="$s/Bench-$name.log"
$projectName='AshgateForestLightingLab'
if($Variant -eq 'Original'){$exe="$r/work/forest-lighting-original-reference/Windows/AshgateForest.exe";$projectName='AshgateForest'}
$probe=[IO.File]::ReadAllText("$p/Tools/input_probe.ps1");$start=$probe.IndexOf('using System;');$end=$probe.IndexOf("'@",$start);if(-not('LabBenchWindow' -as [type])){Add-Type -TypeDefinition $probe.Substring($start,$end-$start).Replace('AshgateInput','LabBenchWindow')}
[LabBenchWindow]::SetThreadDpiAwarenessContext([IntPtr](-4))|Out-Null
$old=[LabBenchWindow]::GetForegroundWindow();$point=New-Object LabBenchWindow+Point;[LabBenchWindow]::GetCursorPos([ref]$point)|Out-Null
$args=@('-ForestBenchmark','-ForceRes','-windowed','-ResX=1920','-ResY=1080','-ExecCmds="t.MaxFPS 0,r.VSync 0,scalability,r.ScreenPercentage,r.DynamicGlobalIlluminationMethod,r.ReflectionMethod,r.Shadow.Virtual.Enable"',"-AbsLog=$log");if($Variant -in @('Full','Lumen')){$args+="-Lab$Variant"}
Set-Content -LiteralPath $log -Value '' -Encoding UTF8
$q=Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory (Split-Path $exe -Parent) -WindowStyle Hidden -PassThru;$h=$q.Handle;$start=Get-Date
try{
 while(-not(Select-String -LiteralPath $log -Pattern 'LogForest: Display: READY' -Quiet -ErrorAction SilentlyContinue)){if($q.HasExited){throw 'Benchmark exited at startup'};if(((Get-Date)-$start).TotalSeconds -gt 180){throw 'Startup timeout'};Start-Sleep -Milliseconds 200}
 $focusReady=Get-Date;$window=[LabBenchWindow]::Find($q.Id)
 if($window -eq [IntPtr]::Zero){$child=Get-CimInstance Win32_Process -Filter "Name='$projectName.exe'"|Where-Object ParentProcessId -eq $q.Id|Select-Object -First 1;if($child){$window=[LabBenchWindow]::Find($child.ProcessId)}}
 if($window -eq [IntPtr]::Zero){throw 'Native window missing'}
 [LabBenchWindow]::ShowWindow($window,9)|Out-Null;[LabBenchWindow]::SetForegroundWindow($window)|Out-Null;Start-Sleep -Milliseconds 100
 # A real client click also activates borderless game windows; its shot is excluded by warmup.
 $rect=New-Object LabBenchWindow+Rect;[LabBenchWindow]::GetClientRect($window,[ref]$rect)|Out-Null
 $loc=New-Object LabBenchWindow+Point;$loc.X=[int]($rect.Right/2);$loc.Y=[int]($rect.Bottom/2);[LabBenchWindow]::ClientToScreen($window,[ref]$loc)|Out-Null
 for($attempt=0;$attempt -lt 3 -and [LabBenchWindow]::GetForegroundWindow() -ne $window;$attempt++){[LabBenchWindow]::ShowWindow($window,9)|Out-Null;[LabBenchWindow]::SetForegroundWindow($window)|Out-Null;[LabBenchWindow]::SetCursorPos($loc.X,$loc.Y)|Out-Null;Start-Sleep -Milliseconds 100;[LabBenchWindow]::mouse_event(2,0,0,0,[UIntPtr]::Zero);[LabBenchWindow]::mouse_event(4,0,0,0,[UIntPtr]::Zero);Start-Sleep -Milliseconds 300}
 if([LabBenchWindow]::GetForegroundWindow() -ne $window){throw 'Foreground activation failed'}
 $checks=0;$lost=0;$recovered=0;while(-not $q.HasExited){Start-Sleep -Milliseconds 250;if(-not $q.HasExited -and -not(Select-String $log -Pattern 'FOREST BENCHMARK COMPLETE' -Quiet)){
  $phase=((Get-Date)-$focusReady).TotalSeconds%35
  if($phase -ge 9){$checks++}
  if([LabBenchWindow]::GetForegroundWindow() -ne $window){
   if($phase -ge 9){$lost++}
   [LabBenchWindow]::ShowWindow($window,9)|Out-Null;[LabBenchWindow]::SetForegroundWindow($window)|Out-Null
   if($phase -lt 9 -and [LabBenchWindow]::GetForegroundWindow() -ne $window){[LabBenchWindow]::SetCursorPos($loc.X,$loc.Y)|Out-Null;[LabBenchWindow]::mouse_event(2,0,0,0,[UIntPtr]::Zero);[LabBenchWindow]::mouse_event(4,0,0,0,[UIntPtr]::Zero)}
   $recovered++
  }
 }}
 if($q.ExitCode -or -not(Select-String $log -Pattern 'FOREST BENCHMARK COMPLETE' -Quiet)){throw 'Benchmark failed'}
 @{checks=$checks;focus_lost=$lost;warmup_focus_recoveries=$recovered;variant=$Variant}|ConvertTo-Json|Set-Content "$s/Bench-$name-focus.json" -Encoding UTF8
 if($lost){throw "Benchmark lost foreground $lost times"}
 Copy-Item (Join-Path (Split-Path $exe -Parent) "$projectName/Saved/Performance/ForestBenchmark.csv") "$s/Bench-$name.csv"
 & 'D:/UE5/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe' "$r/unreal/AshgateForest/Tools/analyze_performance.py" "$s/Bench-$name.csv" --output "$s/Bench-$name.json"
 if($LASTEXITCODE){throw 'Analysis failed'}
}finally{[LabBenchWindow]::SetCursorPos($point.X,$point.Y)|Out-Null;[LabBenchWindow]::SetForegroundWindow($old)|Out-Null}
