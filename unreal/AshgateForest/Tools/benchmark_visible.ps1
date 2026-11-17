param([string]$Executable='',[string]$Name='current',[string]$ExtraCommands='')
$ErrorActionPreference='Stop';$r=Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent;$p="$r\unreal\AshgateForest";$s="$p\Saved";$log="$s\IntegrationBench-$Name.log"
if(-not $Executable){$Executable=Join-Path $r 'work/forest-package/Windows/AshgateForest.exe'}
$probe=[System.IO.File]::ReadAllText("$p\Tools\input_probe.ps1");$start=$probe.IndexOf("using System;");$end=$probe.IndexOf("'@",$start);$class=$probe.Substring($start,$end-$start).Replace('AshgateInput','ForestBenchmarkWindow');if(-not('ForestBenchmarkWindow' -as [type])){Add-Type -TypeDefinition $class}
$old=[ForestBenchmarkWindow]::GetForegroundWindow();$window=[IntPtr]::Zero
Set-Content -LiteralPath $log -Value '' -Encoding UTF8
$commands='t.MaxFPS 0,r.VSync 0,'+$ExtraCommands+',sg.GlobalIlluminationQuality,r.ScreenPercentage,r.Lumen.ThreadGroupSize32,r.Lumen.ScreenProbeGather.DownsampleFactor,r.Lumen.ScreenProbeGather.TracingOctahedronResolution,r.Lumen.ScreenProbeGather.RadianceCache.NumProbesToTraceBudget'
$proc=Start-Process -FilePath $Executable -ArgumentList @('-ForestBenchmark','-ForceRes','-windowed','-ResX=1920','-ResY=1080',('-ExecCmds="'+$commands+'"'),"-AbsLog=$log") -WorkingDirectory (Split-Path $Executable -Parent) -WindowStyle Hidden -PassThru;$handle=$proc.Handle;$started=Get-Date
try{
 while(-not(Select-String -LiteralPath $log -Pattern 'LogForest: Display: READY' -Quiet -ErrorAction SilentlyContinue)){if($proc.HasExited){throw 'Benchmark exited before startup'};if(((Get-Date)-$started).TotalSeconds -gt 120){throw 'Benchmark startup timeout'};Start-Sleep -Milliseconds 500}
 $window=[ForestBenchmarkWindow]::Find($proc.Id)
 if($window -eq [IntPtr]::Zero){$child=Get-CimInstance Win32_Process -Filter "Name='AshgateForest.exe'" | Where-Object ParentProcessId -eq $proc.Id | Select-Object -First 1;if($child){$window=[ForestBenchmarkWindow]::Find($child.ProcessId)}}
 if($window -eq [IntPtr]::Zero){throw 'Native benchmark window not found'}
 [ForestBenchmarkWindow]::ShowWindow($window,9) | Out-Null;[ForestBenchmarkWindow]::SetForegroundWindow($window) | Out-Null
 $proc.WaitForExit();if($proc.ExitCode -or -not(Select-String -LiteralPath $log -Pattern 'FOREST BENCHMARK COMPLETE' -Quiet)){throw 'Visible benchmark failed'}
 Copy-Item -LiteralPath (Join-Path (Split-Path $Executable -Parent) "AshgateForest/Saved/Performance/ForestBenchmark.csv") -Destination "$s\IntegrationBench-$Name.csv"
 & 'D:\UE5\UE_5.8\Engine\Binaries\ThirdParty\Python3\Win64\python.exe' "$p\Tools\analyze_performance.py" "$s\IntegrationBench-$Name.csv" --output "$s\IntegrationBench-$Name.json" *> "$s\IntegrationBench-$Name-summary.txt"
 if($LASTEXITCODE){throw 'Visible benchmark analysis failed'}
}finally{if($old -ne [IntPtr]::Zero){[ForestBenchmarkWindow]::SetForegroundWindow($old) | Out-Null}}
