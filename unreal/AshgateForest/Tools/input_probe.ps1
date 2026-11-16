param([Parameter(Mandatory=$true)][string]$Executable,[Parameter(Mandatory=$true)][string]$LogPath)
$ErrorActionPreference='Stop'
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
# Reset this probe's own log before launching; an old READY marker must not pass startup.
Set-Content -LiteralPath $LogPath -Value '' -Encoding UTF8
$start=Get-Date
$gameArgs=@(('-AbsLog="'+$LogPath+'"'))
$gameArgs+='-ForestInput'

$p=Start-Process -FilePath $Executable -ArgumentList $gameArgs -WorkingDirectory (Split-Path $Executable -Parent) -WindowStyle Hidden -PassThru
$bootstrap=$p
while(-not (Select-String -LiteralPath $LogPath -Pattern 'LogForest: Display: READY' -Quiet -ErrorAction SilentlyContinue)) {
 if($p.HasExited){throw 'Game exited before ready'}
 if(((Get-Date)-$start).TotalSeconds -gt 240){throw 'Game startup timeout'}
 Start-Sleep -Milliseconds 500
}
$handle=[AshgateInput]::Find($p.Id)
if($handle -eq [IntPtr]::Zero) {
 $child=Get-CimInstance Win32_Process -Filter "Name='AshgateForest.exe'" | Where-Object ParentProcessId -eq $p.Id | Select-Object -First 1
 if($child) { $p=Get-Process -Id $child.ProcessId; $handle=[AshgateInput]::Find($p.Id) }
}
if($handle -eq [IntPtr]::Zero){throw 'Game window not found'}
$nativeHandle=$p.Handle
[AshgateInput]::ShowWindow($handle,9) | Out-Null
[AshgateInput]::SetForegroundWindow($handle) | Out-Null
Start-Sleep -Seconds 8
function Key([int]$Code,[int]$Hold=80) { [AshgateInput]::Key($handle,$Code,$true); Start-Sleep -Milliseconds $Hold; [AshgateInput]::Key($handle,$Code,$false); Start-Sleep -Milliseconds 150 }
function Capture([string]$Name) { Write-Output ('INPUT STEP '+$Name); Key 0x78; Start-Sleep -Milliseconds 350 }
function Click([int]$Row) {
 $releaseBefore=@(Select-String -LiteralPath $LogPath -Pattern 'LogForest: Display: MENU row=').Count
 $rect=New-Object AshgateInput+Rect
 [AshgateInput]::GetClientRect($handle,[ref]$rect) | Out-Null
 $scale=($rect.Bottom-$rect.Top)/900.0
 $point=New-Object AshgateInput+Point
 $point.X=[int](300*$scale); $point.Y=[int]((273+$Row*60)*$scale)
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
  if(@(Select-String -LiteralPath $LogPath -Pattern 'LogForest: Display: MENU row=').Count -gt $releaseBefore){return}
 }
 throw ('Menu click was not acknowledged for row '+$Row)
}
Capture 'trail start'
Key 0x57 1000
Capture 'walking'
Key 0x4E
Capture 'inspect'
[AshgateInput]::PostMessage($handle,0x204,[IntPtr]2,[IntPtr]::Zero)|Out-Null
Start-Sleep -Milliseconds 250
Capture 'ADS'
[AshgateInput]::PostMessage($handle,0x201,[IntPtr]1,[IntPtr]::Zero)|Out-Null
Start-Sleep -Milliseconds 100
[AshgateInput]::PostMessage($handle,0x202,[IntPtr]::Zero,[IntPtr]::Zero)|Out-Null
Capture 'fire'
[AshgateInput]::PostMessage($handle,0x205,[IntPtr]::Zero,[IntPtr]::Zero)|Out-Null
Key 0x52
Capture 'reload starts'
Start-Sleep -Seconds 2
Capture 'reload complete'
Key 0x71
Capture 'scenery view'
Key 0x71
Capture 'M1911 equipped'
Key 0x1B
Capture 'pause menu'
Click 3
Capture 'sensitivity plus'
Click 0
Capture 'resume'
Key 0x1B
Click 4
Click 1
Capture 'cancel quit'
Click 4
Click 0
if(-not $p.WaitForExit(30000)){throw 'Forest game did not exit normally'}
$bootstrap.WaitForExit(30000)|Out-Null
[AshgateInput]::SetCursorPos($oldPoint.X,$oldPoint.Y)|Out-Null
[AshgateInput]::SetForegroundWindow($oldHandle)|Out-Null
$lines=@(Select-String -LiteralPath $LogPath -Pattern 'LogForest: Display: INPUT position=' | ForEach-Object {$_.Line})
if($lines.Count -ne 13){throw "Expected 13 forest input snapshots, got $($lines.Count)"}
foreach($r in @(@(2,'inspect=[1-9]'),@(3,'aim=1'),@(6,'ammo=7'),@(7,'visible=0'),@(8,'visible=1'),@(9,'paused=1'),@(11,'paused=0'),@(12,'paused=1'))){if($lines[$r[0]] -notmatch $r[1]){throw ('Forest input state mismatch: '+$lines[$r[0]])}}
$before=[int]([regex]::Match($lines[3],'ammo=(\d+)').Groups[1].Value)
$after=[int]([regex]::Match($lines[4],'ammo=(\d+)').Groups[1].Value)
if($after -ne $before-1){throw 'Shot ammo mismatch'}
if(([regex]::Match($lines[0],'position=(.*?) ammo').Groups[1].Value) -eq ([regex]::Match($lines[1],'position=(.*?) ammo').Groups[1].Value)){throw 'Walking did not move player'}
$log=Get-Content -LiteralPath $LogPath -Raw
if(-not $log.Contains('CONFIRMED USER QUIT') -or -not $log.Contains('LogExit: Exiting.') -or $log -match 'Fatal error|Unhandled Exception'){throw 'Game exit verification failed'}
Write-Output 'FOREST INPUT VALIDATION PASS: 13 snapshots, walking, M1911, ADS, reload, holster, pause, sensitivity button, resume and quit cancellation/confirmation'
