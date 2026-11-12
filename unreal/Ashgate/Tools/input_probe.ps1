param([Parameter(Mandatory=$true)][string]$Executable,[Parameter(Mandatory=$true)][string]$LogPath,[switch]$ProductionProfile,[switch]$DefaultResolution,[switch]$DeployRaid,[switch]$ValidateExistingLog)
$ErrorActionPreference='Stop'
function ValidateInputLog {
$snapshots=@(Select-String -LiteralPath $LogPath -Pattern 'INPUT PROBE' | ForEach-Object {$_.Line})
if($snapshots.Count -ne 16){throw "Expected 16 input snapshots, got $($snapshots.Count)"}
$requirements=@(@(0,'phase=base'),@(1,'phase=raid'),@(3,'inspect=[1-9]'),@(4,'aiming=1 inspect=0.00'),@(7,'ammo=7 '),@(8,'bag=1 paused=0'),@(9,'bag=0 paused=0'),@(10,'paused=1'),@(12,'paused=0'),@(13,'phase=base'),@(14,'phase=base'),@(15,'phase=base'))
foreach($requirement in $requirements){if($snapshots[$requirement[0]] -notmatch $requirement[1]){throw ('Input state mismatch: '+$snapshots[$requirement[0]])}}
$beforeShot=[int]([regex]::Match($snapshots[4],'ammo=(\d+) ').Groups[1].Value)
$afterShot=[int]([regex]::Match($snapshots[5],'ammo=(\d+) ').Groups[1].Value)
if($afterShot -ne ($beforeShot-1)){throw 'Single shot did not consume exactly one round'}
$reloadValue=[double]([regex]::Match($snapshots[6],'reload=([-0-9.]+)').Groups[1].Value)
if($reloadValue -le 0){throw 'Reload did not start'}
$initialSensitivity=[double]([regex]::Match($snapshots[0],'sensitivity=([-0-9.]+)').Groups[1].Value)
$changedSensitivity=[double]([regex]::Match($snapshots[11],'sensitivity=([-0-9.]+)').Groups[1].Value)
if([Math]::Abs($changedSensitivity-[Math]::Min(3.0,$initialSensitivity+0.1)) -gt 0.011){throw 'Sensitivity click did not apply'}
if($snapshots[1] -match 'position=([^ ]+ [^ ]+ [^ ]+)'){ $initialPosition=$Matches[1] }
if($snapshots[2] -match 'position=([^ ]+ [^ ]+ [^ ]+)' -and $Matches[1] -eq $initialPosition){throw 'W input did not move player'}
$all=Get-Content -LiteralPath $LogPath -Raw
foreach($marker in @('MENU release button=Quit1','MENU confirmed quit by user','LogExit: Exiting.')){if(-not $all.Contains($marker)){throw ('Missing expected input result: '+$marker)}}
if($all -match 'Fatal error|Unhandled Exception'){throw 'Input run crashed'}
if($ProductionProfile -and -not $all.Contains('save slot AshgateUE5_Profile_v1')){throw 'Production profile path was not exercised'}
Write-Output 'INPUT VALIDATION PASS: 16 snapshots, movement, weapon, menus, quit cancellation and confirmed exit'
Select-String -LiteralPath $LogPath -Pattern 'INPUT PROBE' | ForEach-Object {$_.Line}

}
if($ValidateExistingLog){ValidateInputLog;exit 0}

Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class AshgateInput {
 public delegate bool Callback(IntPtr h,IntPtr l);
 [StructLayout(LayoutKind.Sequential)] public struct Rect {public int Left,Top,Right,Bottom;}
 [StructLayout(LayoutKind.Sequential)] public struct Point {public int X,Y;}
 [DllImport("user32.dll")] public static extern bool EnumWindows(Callback c,IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h,StringBuilder b,int n);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int c);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h,ref Point p);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern bool GetCursorPos(out Point p);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h,uint m,IntPtr w,IntPtr l);
 [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint k,uint t);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr i);
 public static IntPtr Find(int id) {
   IntPtr result=IntPtr.Zero;
   EnumWindows((h,l)=>{uint p;GetWindowThreadProcessId(h,out p);if(p==id){var b=new StringBuilder(1024);GetWindowText(h,b,1024);if(b.ToString().Contains("ASHGATE")){result=h;return false;}}return true;},IntPtr.Zero);
   return result;
 }
 public static void Key(IntPtr h,uint key,bool down) {
   long bits=1|((long)MapVirtualKey(key,0)<<16);if(!down) bits|=0xC0000000L;
   PostMessage(h,down?0x100u:0x101u,(IntPtr)key,(IntPtr)bits);
 }
}
'@
$oldHandle=[AshgateInput]::GetForegroundWindow()
$oldPoint=New-Object AshgateInput+Point
[AshgateInput]::GetCursorPos([ref]$oldPoint) | Out-Null
trap {
 if($p -and -not $p.HasExited -and $handle -and $handle -ne [IntPtr]::Zero) { [AshgateInput]::Key($handle,0x57,$false); [AshgateInput]::PostMessage($handle,0x10,[IntPtr]::Zero,[IntPtr]::Zero) | Out-Null }
 [AshgateInput]::SetCursorPos($oldPoint.X,$oldPoint.Y) | Out-Null
 [AshgateInput]::SetForegroundWindow($oldHandle) | Out-Null
 throw $_
}
$start=Get-Date
$gameArgs=@(('-AbsLog="'+$LogPath+'"'))
if($ProductionProfile) { $gameArgs+='-AshgateInputCapture' } else { $gameArgs+='-AshgateInputProbe' }
if(-not $DefaultResolution) { $gameArgs+=@('-windowed','-ResX=1600','-ResY=900') }
$p=Start-Process -FilePath $Executable -ArgumentList $gameArgs -WorkingDirectory (Split-Path $Executable -Parent) -WindowStyle Hidden -PassThru
$bootstrap=$p
while(-not (Select-String -LiteralPath $LogPath -Pattern 'LogAshgate: Display: READY' -Quiet -ErrorAction SilentlyContinue)) {
 if($p.HasExited){throw 'Game exited before ready'}
 if(((Get-Date)-$start).TotalSeconds -gt 120){throw 'Game startup timeout'}
 Start-Sleep -Milliseconds 500
}
$handle=[AshgateInput]::Find($p.Id)
if($handle -eq [IntPtr]::Zero) {
 $child=Get-CimInstance Win32_Process -Filter "Name='Ashgate.exe'" | Where-Object ParentProcessId -eq $p.Id | Select-Object -First 1
 if($child) { $p=Get-Process -Id $child.ProcessId; $handle=[AshgateInput]::Find($p.Id) }
}
if($handle -eq [IntPtr]::Zero){throw 'Game window not found'}
$nativeHandle=$p.Handle
[AshgateInput]::ShowWindow($handle,9) | Out-Null
[AshgateInput]::SetForegroundWindow($handle) | Out-Null
Start-Sleep -Seconds 2
function Key([int]$Code,[int]$Hold=80) { [AshgateInput]::Key($handle,$Code,$true); Start-Sleep -Milliseconds $Hold; [AshgateInput]::Key($handle,$Code,$false); Start-Sleep -Milliseconds 150 }
function Capture([string]$Name) { Write-Output ('INPUT STEP '+$Name); Key 0x78; Start-Sleep -Milliseconds 350 }
function Click([int]$Row) {
 $releaseBefore=@(Select-String -LiteralPath $LogPath -Pattern 'MENU release button=').Count
 $rect=New-Object AshgateInput+Rect
 [AshgateInput]::GetClientRect($handle,[ref]$rect) | Out-Null
 $scale=($rect.Bottom-$rect.Top)/900.0
 $point=New-Object AshgateInput+Point
 $point.X=[int](300*$scale); $point.Y=[int]((273+$Row*57)*$scale)
 $clientX=$point.X; $clientY=$point.Y
 [AshgateInput]::ClientToScreen($handle,[ref]$point) | Out-Null
 [AshgateInput]::SetCursorPos($point.X,$point.Y) | Out-Null
 Start-Sleep -Milliseconds 150
 $packed=[IntPtr](($clientY -shl 16) -bor ($clientX -band 65535))
 for($attempt=0;$attempt -lt 3;$attempt++) {
  [AshgateInput]::PostMessage($handle,0x200,[IntPtr]::Zero,$packed)|Out-Null
  Start-Sleep -Milliseconds 200
  [AshgateInput]::PostMessage($handle,0x201,[IntPtr]1,$packed)|Out-Null; Start-Sleep -Milliseconds 250
  [AshgateInput]::SetCursorPos($point.X,$point.Y)|Out-Null
  [AshgateInput]::PostMessage($handle,0x200,[IntPtr]1,$packed)|Out-Null
  Start-Sleep -Milliseconds 100
  [AshgateInput]::PostMessage($handle,0x202,[IntPtr]::Zero,$packed)|Out-Null
  Start-Sleep -Milliseconds 500
  if(@(Select-String -LiteralPath $LogPath -Pattern 'MENU release button=').Count -gt $releaseBefore){return}
 }
 throw ('Menu click was not acknowledged for row '+$Row)
}
Capture 'base menu'
Click $(if($DeployRaid){0}else{1})
Start-Sleep -Seconds 1
Capture 'deployed via mouse'
Key 0x57 1000
Capture 'W movement'
Key 0x4E
Capture 'N inspect'
[AshgateInput]::PostMessage($handle,0x204,[IntPtr]2,[IntPtr]::Zero)|Out-Null
Start-Sleep -Milliseconds 250
Capture 'RMB ADS cancels inspect'
[AshgateInput]::PostMessage($handle,0x205,[IntPtr]::Zero,[IntPtr]::Zero)|Out-Null
[AshgateInput]::PostMessage($handle,0x201,[IntPtr]1,[IntPtr]::Zero)|Out-Null
Start-Sleep -Milliseconds 80
[AshgateInput]::PostMessage($handle,0x202,[IntPtr]::Zero,[IntPtr]::Zero)|Out-Null
Capture 'LMB fire'
Key 0x52
Capture 'R reload starts'
Start-Sleep -Seconds 2
Capture 'reload complete'
Key 0x09
Capture 'Tab bag remains live'
Key 0x1B
Capture 'Esc closes bag only'
Key 0x1B
Capture 'Esc pause'
Click 2
Capture 'sensitivity plus'
Key 0x1B
Capture 'Esc resume'
Key 0x1B
Click 4
Capture 'return to base'
Click 6
Capture 'quit confirmation / still running'
Click 1
Capture 'cancel quit / still running'
Click 6
Click 0
if(-not $p.WaitForExit(30000)){throw 'Test game did not close normally'}
$bootstrap.WaitForExit(30000)|Out-Null
Write-Output ('Input test bootstrap exit code: '+$bootstrap.ExitCode)
[AshgateInput]::SetCursorPos($oldPoint.X,$oldPoint.Y) | Out-Null
[AshgateInput]::SetForegroundWindow($oldHandle) | Out-Null

ValidateInputLog
