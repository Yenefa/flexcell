param(
    [string]$Model = 'deepseek-v4.1-flash',
    [string]$Distro = 'Ubuntu-24.04',
    [string]$WslUser = 'ros'
)
$ErrorActionPreference = 'Stop'
$taskKey = $env:OC_API_KEY
if (-not $taskKey) { $taskKey = [Environment]::GetEnvironmentVariable('OC_API_KEY', 'User') }
if (-not $taskKey) { throw 'OC_API_KEY is not configured in the Windows environment' }
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskRepoWsl = '/mnt/' + $taskRepo.Substring(0,1).ToLowerInvariant() + $taskRepo.Substring(2).Replace('\','/')
$taskPayload = @{api_key=$taskKey; model=$Model; endpoint='https://opencode.ai/zen/v1/chat/completions'} | ConvertTo-Json -Compress
# Pass the credential only on stdin, never in argv, repository files or logs.
$taskPayload | wsl.exe -d $Distro -u $WslUser -- python3 "$taskRepoWsl/setup/110_configure_gateway.py"
if ($LASTEXITCODE -ne 0) { throw 'WSL gateway configuration failed' }
$taskPayload = $null
$taskKey = $null
