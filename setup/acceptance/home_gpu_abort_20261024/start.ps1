$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$jobRoot='F:\flexcell-models\pr40-20261024-01a169ef-batch5'
if (Test-Path $jobRoot) { throw 'Refusing to overwrite an existing run' }
if (@(Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'").Count -ne 0) { throw 'Pre-existing model process' }
New-Item $jobRoot -ItemType Directory | Out-Null
$exe='F:\flexcell-models\llama-b11389-vulkan\llama-server.exe'
$arguments=@('-m','F:\flexcell-models\Clef-Flash-Q8_0.gguf','--host','0.0.0.0','--port','11435','-ngl','99','-ub','32768','-c','16384','-lv','5')
$ownedProcess=Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory 'F:\flexcell-models\llama-b11389-vulkan' -RedirectStandardOutput "$jobRoot\stdout.log" -RedirectStandardError "$jobRoot\stderr.log" -PassThru
$reason='process_exited'
try {
  $ownedProcess.Refresh()
  $guardian=Get-Process -Id $PID
  $owner=[ordered]@{pid=$ownedProcess.Id;start_ticks=$ownedProcess.StartTime.Ticks.ToString();created_utc=$ownedProcess.StartTime.ToUniversalTime().ToString('o');executable=$exe;arguments=$arguments;job_root=$jobRoot;watchdog_pid=$PID;watchdog_start_ticks=$guardian.StartTime.Ticks.ToString();lifecycle='foreground SSH session with heartbeat lease'}
  $owner | ConvertTo-Json -Depth 5 | Set-Content "$jobRoot\owner.json" -Encoding UTF8
  Set-Content "$jobRoot\heartbeat.txt" -Value 'PR40 owned session' -Encoding ASCII
  [Console]::Out.WriteLine(($owner | ConvertTo-Json -Depth 5 -Compress))
  [Console]::Out.Flush()
  $deadline=[DateTime]::UtcNow.AddMinutes(30)
  while (-not $ownedProcess.HasExited) {
    Start-Sleep -Seconds 2
    $age=([DateTime]::UtcNow-(Get-Item "$jobRoot\heartbeat.txt").LastWriteTimeUtc).TotalSeconds
    if ($age -gt 120 -or [DateTime]::UtcNow -gt $deadline) { $reason='lease_or_deadline_expired'; break }
    $ownedProcess.Refresh()
  }
} finally {
  $target=Get-Process -Id $ownedProcess.Id -ErrorAction SilentlyContinue
  if ($null -ne $target -and $target.StartTime.Ticks.ToString() -eq $owner.start_ticks) { Stop-Process -Id $ownedProcess.Id -Force }
  [pscustomobject]@{pid=$ownedProcess.Id;reason=$reason;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content "$jobRoot\session_end.json" -Encoding UTF8
}
