param(
    [ValidateSet('runtime','fast','slow')][string]$Asset = 'runtime',
    [string]$RuntimeRoot = (Join-Path $env:LOCALAPPDATA 'Flexcell\inference')
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$taskAssets = Get-Content -Raw (Join-Path $PSScriptRoot 'local_inference_assets.json') | ConvertFrom-Json
$taskAsset = $taskAssets.$Asset
$taskRoot = [IO.Path]::GetFullPath($RuntimeRoot)
New-Item -ItemType Directory -Path $taskRoot -Force | Out-Null
$taskFile = Join-Path $taskRoot $taskAsset.file
if (!(Test-Path -LiteralPath $taskFile) -or (Get-FileHash -LiteralPath $taskFile -Algorithm SHA256).Hash.ToLower() -ne $taskAsset.sha256) {
    Write-Output "Downloading pinned $Asset asset"
    Invoke-WebRequest -Uri $taskAsset.url -OutFile "$taskFile.part" -TimeoutSec 300
    $taskHash = (Get-FileHash -LiteralPath "$taskFile.part" -Algorithm SHA256).Hash.ToLower()
    if ($taskHash -ne $taskAsset.sha256) { throw "SHA256 mismatch: $Asset" }
    Move-Item -LiteralPath "$taskFile.part" -Destination $taskFile -Force
}
if ($Asset -eq 'runtime') {
    Expand-Archive -LiteralPath $taskFile -DestinationPath (Join-Path $taskRoot 'llama') -Force
}
Write-Output "READY $Asset $taskFile"
