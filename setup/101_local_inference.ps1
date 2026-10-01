param(
    [ValidateSet('start','status','stop')][string]$Action = 'status',
    [string]$RuntimeRoot = (Join-Path $env:LOCALAPPDATA 'Flexcell\inference')
)
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath($RuntimeRoot)
$taskAssets = Get-Content -Raw (Join-Path $PSScriptRoot 'local_inference_assets.json') | ConvertFrom-Json
$taskExe = Join-Path $taskRoot 'llama\llama-server.exe'
foreach ($taskArm in @('fast','slow')) {
    $taskPort = if ($taskArm -eq 'fast') { 18081 } else { 18082 }
    $taskPidFile = Join-Path $taskRoot "$taskArm.pid"
    $taskProcess = $null
    if (Test-Path -LiteralPath $taskPidFile) {
        $taskPid = [int](Get-Content -Raw -LiteralPath $taskPidFile)
        $taskProcess = Get-Process -Id $taskPid -ErrorAction SilentlyContinue
        if ($taskProcess -and $taskProcess.Path -ne $taskExe) { throw "PID ownership mismatch for $taskArm" }
    }
    if ($Action -eq 'stop') {
        if ($taskProcess) { Stop-Process -Id $taskProcess.Id; Write-Output "STOPPED $taskArm" }
        continue
    }
    if ($Action -eq 'start' -and !$taskProcess) {
        $taskModel = Join-Path $taskRoot $taskAssets.$taskArm.file
        if ((Get-FileHash -LiteralPath $taskModel -Algorithm SHA256).Hash.ToLower() -ne $taskAssets.$taskArm.sha256) { throw "Model hash mismatch for $taskArm" }
        $taskArgs = @('-m', ('"' + $taskModel + '"'), '-ngl', '99', '-c', '8192', '-np', '1', '-t', '4', '--host', '127.0.0.1', '--port', "$taskPort", '--alias', "flexcell-$taskArm")
        $taskStamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $taskProcess = Start-Process -FilePath $taskExe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRoot "$taskArm-$taskStamp.stdout.log") -RedirectStandardError (Join-Path $taskRoot "$taskArm-$taskStamp.stderr.log")
        [IO.File]::WriteAllText($taskPidFile, [string]$taskProcess.Id)
        @{arm=$taskArm; pid=$taskProcess.Id; arguments=$taskArgs; asset=$taskAssets.$taskArm; runtime=$taskAssets.runtime; started=(Get-Date).ToString('o')} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $taskRoot "$taskArm-server.json")
        Write-Output "STARTED $taskArm PID=$($taskProcess.Id) port=$taskPort"
    } elseif ($Action -eq 'status') {
        try {
            $taskHealth = Invoke-RestMethod "http://127.0.0.1:$taskPort/health" -TimeoutSec 3
            Write-Output "$taskArm PID=$($taskProcess.Id) health=$($taskHealth.status)"
        } catch { Write-Output "$taskArm unavailable: $($_.Exception.Message)" }
    }
}
