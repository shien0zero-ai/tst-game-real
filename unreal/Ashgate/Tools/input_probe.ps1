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
 if($handle -and $handle -ne [IntPtr]::Zero) { [AshgateInput]::Key($handle,0x57,$false); [AshgateInput]::PostMessage($handle,0x10,[IntPtr]::Zero,[IntPtr]::Zero) | Out-Null }
 [AshgateInput]::SetCursorPos($oldPoint.X,$oldPoint.Y) | Out-Null
 [AshgateInput]::SetForegroundWindow($oldHandle) | Out-Null
 throw $_
}
$start=Get-Date
$p=Start-Process -FilePath $Executable -ArgumentList @('-AshgateInputProbe','-windowed','-ResX=1600','-ResY=900',('-AbsLog="'+$LogPath+'"')) -WindowStyle Hidden -PassThru
while(-not (Select-String -LiteralPath $LogPath -Pattern 'LogAshgate: Display: READY' -Quiet -ErrorAction SilentlyContinue)) {
 if($p.HasExited){throw 'Game exited before ready'}
 if(((Get-Date)-$start).TotalSeconds -gt 120){throw 'Game startup timeout'}
 Start-Sleep -Milliseconds 500
}
$handle=[AshgateInput]::Find($p.Id)
if($handle -eq [IntPtr]::Zero){throw 'Game window not found'}
[AshgateInput]::ShowWindow($handle,9) | Out-Null
[AshgateInput]::SetForegroundWindow($handle) | Out-Null
Start-Sleep -Seconds 2
function Key([int]$Code,[int]$Hold=80) { [AshgateInput]::Key($handle,$Code,$true); Start-Sleep -Milliseconds $Hold; [AshgateInput]::Key($handle,$Code,$false); Start-Sleep -Milliseconds 150 }
function Capture([string]$Name) { Write-Output ('INPUT STEP '+$Name); Key 0x78; Start-Sleep -Milliseconds 350 }
function Click([int]$Row) {
 $rect=New-Object AshgateInput+Rect
 [AshgateInput]::GetClientRect($handle,[ref]$rect) | Out-Null
 $scale=($rect.Bottom-$rect.Top)/900.0
 $point=New-Object AshgateInput+Point
 $point.X=[int](300*$scale); $point.Y=[int]((273+$Row*57)*$scale)
 [AshgateInput]::ClientToScreen($handle,[ref]$point) | Out-Null
 [AshgateInput]::SetCursorPos($point.X,$point.Y) | Out-Null
 Start-Sleep -Milliseconds 150
 [AshgateInput]::mouse_event(2,0,0,0,[UIntPtr]::Zero); Start-Sleep -Milliseconds 80
 [AshgateInput]::mouse_event(4,0,0,0,[UIntPtr]::Zero); Start-Sleep -Milliseconds 400
}
Capture 'base menu'
Click 1
Start-Sleep -Seconds 1
Capture 'practice deployed via mouse'
Key 0x57 1000
Capture 'W movement'
Key 0x4E
Capture 'N inspect'
[AshgateInput]::mouse_event(0x08,0,0,0,[UIntPtr]::Zero)
Start-Sleep -Milliseconds 250
Capture 'RMB ADS cancels inspect'
[AshgateInput]::mouse_event(0x10,0,0,0,[UIntPtr]::Zero)
[AshgateInput]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
Start-Sleep -Milliseconds 80
[AshgateInput]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
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
[AshgateInput]::PostMessage($handle,0x10,[IntPtr]::Zero,[IntPtr]::Zero) | Out-Null
if(-not $p.WaitForExit(30000)){throw 'Test game did not close normally'}
Write-Output ('Input test game exit code: '+$p.ExitCode)
[AshgateInput]::SetCursorPos($oldPoint.X,$oldPoint.Y) | Out-Null
[AshgateInput]::SetForegroundWindow($oldHandle) | Out-Null
Select-String -LiteralPath $LogPath -Pattern 'INPUT PROBE' | ForEach-Object {$_.Line}
