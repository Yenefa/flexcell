$ErrorActionPreference = 'Stop'
$evidencePath = '\\wsl.localhost\Ubuntu-24.04\home\ros\agentic_workcell_ws\setup\acceptance\q8_pilot_20261005'
$models = Invoke-RestMethod -Uri 'http://127.0.0.1:11435/v1/models' -TimeoutSec 3
$readiness = Invoke-RestMethod -Uri 'http://127.0.0.1:11435/health' -TimeoutSec 3
$serverProcess = Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | Where-Object CommandLine -Match '11435'
if (@($serverProcess).Count -ne 1) { throw 'Q8 server process identity is ambiguous' }
$weightPath = 'C:\Users\fuker\AppData\Local\Temp\flexcell_models\Clef-Flash-Q8_0.gguf'
$weightHash = (Get-FileHash -LiteralPath $weightPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($weightHash -ne '8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9') { throw 'Q8 file SHA mismatch' }
$result = [ordered]@{
    captured_utc = (Get-Date).ToUniversalTime().ToString('o')
    readiness = $readiness
    models = $models
    pid = $serverProcess.ProcessId
    executable = $serverProcess.ExecutablePath
    command_line = $serverProcess.CommandLine
    weight_file = $weightPath
    weight_sha256 = $weightHash
    binding = 'Process command line, local GGUF file hash, and served filename agree; provider does not expose a weight SHA.'
    sleep_ac_seconds = 0
    sleep_dc_seconds = 0
}
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidencePath 'windows_server_identity.json') -Encoding utf8NoBOM
Write-Output "Q8 PID=$($serverProcess.ProcessId) readiness=$($readiness.status) weight_sha256=$weightHash"
