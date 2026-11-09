param([string]$Out = "$PSScriptRoot\demo-output")
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\..\.."
$pilot = Join-Path $root "experiments\pilot-001"
$repo = $root.Path
if (-not $env:FLEXCELL_PILOT_API_KEY) {
  $key = [Environment]::GetEnvironmentVariable("FLEXCELL_PILOT_API_KEY", "User")
  if (-not $key) { throw "set FLEXCELL_PILOT_API_KEY first" }
  $env:FLEXCELL_PILOT_API_KEY = $key
}
if (-not $env:FLEXCELL_PILOT_BASE_URL) { $env:FLEXCELL_PILOT_BASE_URL = "https://api.deepseek.com" }
if (-not $env:FLEXCELL_PILOT_MODEL) { $env:FLEXCELL_PILOT_MODEL = "deepseek-chat" }
python "$pilot\run_pilot.py" --llm --task T-W5E2D --agent fc --repo-src $repo --out $Out --arms W5A
Write-Output "demo finished; see $Out"
