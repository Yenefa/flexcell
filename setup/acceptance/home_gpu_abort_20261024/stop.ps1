$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$jobRoot = 'F:\flexcell-models\pr40-20261024-01a169ef-batch5'
$owner = Get-Content "$jobRoot\owner.json" -Raw | ConvertFrom-Json
$target = Get-Process -Id $owner.pid -ErrorAction SilentlyContinue
$action = 'already_exited'
if ($null -ne $target) {
  if ($target.StartTime.Ticks.ToString() -ne $owner.start_ticks -or $target.Path -ne $owner.executable) { throw 'GPU process identity mismatch; refusing to stop another process' }
  Stop-Process -Id $owner.pid -Force
  Wait-Process -Id $owner.pid -Timeout 15 -ErrorAction SilentlyContinue
  $action = 'stopped_owned_process'
}
for ($i=0; $i -lt 15 -and ($null -ne (Get-Process -Id $owner.watchdog_pid -ErrorAction SilentlyContinue)); $i++) { Start-Sleep -Milliseconds 200 }
$guard = Get-Process -Id $owner.watchdog_pid -ErrorAction SilentlyContinue
if ($null -ne $guard -and $guard.StartTime.Ticks.ToString() -eq $owner.watchdog_start_ticks) { Stop-Process -Id $owner.watchdog_pid -Force }
$remaining = @(Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | Select-Object ProcessId,ExecutablePath)
$listener = @(Get-NetTCPConnection -LocalPort 11435 -State Listen -ErrorAction SilentlyContinue)
$result = [ordered]@{action=$action;pid=$owner.pid;exited=($null -eq (Get-Process -Id $owner.pid -ErrorAction SilentlyContinue));watchdog_exited=($null -eq (Get-Process -Id $owner.watchdog_pid -ErrorAction SilentlyContinue));port_11435_listening=($listener.Count -gt 0);remaining_inference_processes=$remaining;utc=[DateTime]::UtcNow.ToString('o')}
$result | ConvertTo-Json -Depth 5 | Set-Content "$jobRoot\shutdown.json" -Encoding UTF8
$result | ConvertTo-Json -Depth 5 -Compress
