# Record only the Gazebo window on a WSLg host.
#
# WSLg renders windows as Wayland surfaces, so ffmpeg's x11grab inside WSL sees a
# black frame. This script records from Windows instead: it starts the stack and a
# software-rendered Gazebo GUI in WSL, finds the window, maximizes it, and captures
# exactly the window's client rectangle with gdigrab.
#
# Usage (from a Windows shell):
#   powershell -ExecutionPolicy Bypass -File scripts/record_gazebo.ps1 `
#     -SourceRun /tmp/carry-window3/out/NORMAL_1/run-7c231a57a747 `
#     -Out D:\demo\gazebo.mp4 -Seconds 60 -Cycles 1
param(
  [Parameter(Mandatory = $true)][string]$SourceRun,
  [string]$Out = "$PWD\gazebo-demo.mp4",
  [int]$Seconds = 60,
  [int]$Cycles = 1,
  [string]$WslRepo = "/home/ros/flexcell-physical",
  [string]$Distro = "Ubuntu-24.04",
  [string]$User = "ros",
  [ValidateSet('gpu', 'soft')][string]$Gui = 'soft'
)

Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class FlexGazeboWin {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
}
"@

$ErrorActionPreference = 'Continue'

# 1. clean a previous session
wsl -d $Distro -u $User -- bash -c 'pkill -f "gz sim" 2>/dev/null; pkill -f "flexcell_skills/" 2>/dev/null; pkill -f "ros2 launch flexcell_skills" 2>/dev/null; rm -f /tmp/demo-ready; true' | Out-Null
Start-Sleep -Seconds 4

# 2. start stack + GUI in WSL, keep the handle so we can stop it later
$serve = Start-Process -FilePath 'wsl' -ArgumentList @(
  '-d', $Distro, '-u', $User, '--', 'env', "DEMO_GUI=$Gui", 'bash',
  "$WslRepo/scripts/demo_serve.sh", $SourceRun, '/tmp/demo-serve-video'
) -PassThru -WindowStyle Hidden

$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  $check = wsl -d $Distro -u $User -- bash -c 'test -f /tmp/demo-ready && echo yes || echo no'
  if ($check -match 'yes') { $ready = $true; break }
  Start-Sleep -Seconds 3
}
if (-not $ready) {
  Stop-Process -Id $serve.Id -Force -ErrorAction SilentlyContinue
  throw 'stack did not become ready'
}
Start-Sleep -Seconds 4

# 3. find and maximize the Gazebo window
$script:gaz = [IntPtr]::Zero
$cb = [FlexGazeboWin+EnumProc]{
  param($h, $l)
  if ([FlexGazeboWin]::IsWindowVisible($h)) {
    $sb = New-Object System.Text.StringBuilder 512
    [void][FlexGazeboWin]::GetWindowText($h, $sb, 512)
    if ($sb.ToString() -match 'Gazebo Sim') { $script:gaz = $h }
  }
  return $true
}
[void][FlexGazeboWin]::EnumWindows($cb, [IntPtr]::Zero)
if ($script:gaz -eq [IntPtr]::Zero) {
  Stop-Process -Id $serve.Id -Force -ErrorAction SilentlyContinue
  throw 'no Gazebo Sim window found'
}
[void][FlexGazeboWin]::ShowWindow($script:gaz, 3)   # SW_MAXIMIZE
[void][FlexGazeboWin]::SetForegroundWindow($script:gaz)
Start-Sleep -Seconds 3

$rect = New-Object FlexGazeboWin+RECT
[void][FlexGazeboWin]::GetClientRect($script:gaz, [ref]$rect)
$origin = New-Object FlexGazeboWin+POINT
$origin.X = 0; $origin.Y = 0
[void][FlexGazeboWin]::ClientToScreen($script:gaz, [ref]$origin)
$x = $origin.X -band -2
$y = $origin.Y -band -2
$w = ($rect.Right - $rect.Left) -band -2
$h = ($rect.Bottom - $rect.Top) -band -2

# 4. record exactly that rectangle
$dir = Split-Path -Parent $Out
if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
$ff = Start-Process -FilePath 'ffmpeg' -ArgumentList @(
  '-hide_banner', '-loglevel', 'warning', '-y',
  '-f', 'gdigrab', '-framerate', '30',
  '-offset_x', "$x", '-offset_y', "$y", '-video_size', "${w}x${h}",
  '-i', 'desktop', '-t', "$Seconds",
  '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', $Out
) -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2

# 5. run the demo inside the live stack
wsl -d $Distro -u $User -- bash -c ". /opt/ros/jazzy/setup.bash; . `$HOME/flexcell-physical/install/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=45; cd `$HOME/flexcell-physical && python3 scripts/run_demo_cycles.py --out /tmp/demo-video --cycles $Cycles"

# 6. let ffmpeg finish its fixed duration, then stop the stack
$deadline = (Get-Date).AddSeconds($Seconds + 20)
while (-not $ff.HasExited -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
if (-not $ff.HasExited) { Stop-Process -Id $ff.Id -Force -ErrorAction SilentlyContinue }

wsl -d $Distro -u $User -- bash -c 'pkill -f "gz sim" 2>/dev/null; pkill -f "flexcell_skills/" 2>/dev/null; pkill -f "ros2 launch flexcell_skills" 2>/dev/null; pkill -f "move_group" 2>/dev/null; rm -f /tmp/demo-ready; true' | Out-Null
Stop-Process -Id $serve.Id -Force -ErrorAction SilentlyContinue

ffprobe -v error -show_entries format=duration,size -show_entries stream=width,height -of default=nw=1 $Out
