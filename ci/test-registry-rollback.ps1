param(
    [Parameter(Mandatory)][string] $Previous,
    [Parameter(Mandatory)][string] $Current,
    [Parameter(Mandatory)][string] $Work
)
$ErrorActionPreference = 'Stop'
$exact = '^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$'
if ($Previous -notmatch $exact -or $Current -notmatch $exact -or $Previous -eq $Current) {
    throw 'Supply two different exact npm versions'
}
$profileRoot = [IO.Path]::GetFullPath($Work)
if (Test-Path -LiteralPath $profileRoot) { throw 'Rollback requires a fresh consumer profile' }
New-Item -ItemType Directory -Path $profileRoot | Out-Null
$env:USERPROFILE = $profileRoot
$env:CODEX_HOME = Join-Path $profileRoot '.codex'
$env:LOCALAPPDATA = Join-Path $profileRoot 'local'
$env:APPDATA = Join-Path $profileRoot 'roaming'
$env:npm_config_cache = Join-Path $profileRoot 'npm-cache'
$env:npm_config_registry = 'https://registry.npmjs.org/'
$base = Join-Path $env:LOCALAPPDATA 'DepLoom/public'
$active = Join-Path $base 'clients/codex/active.json'
function Invoke-Consumer([string]$Selector, [string]$Action, [string]$Expected) {
    npm.cmd exec --yes --prefer-online "--package=@levencode/deploom@$Selector" -- deploom $Action codex
    if ($LASTEXITCODE) { throw "npm exec failed at $Action $Selector" }
    $state = Get-Content -LiteralPath $active -Raw | ConvertFrom-Json
    if ($state.version -cne $Expected) { throw "Expected $Expected, activated $($state.version)" }
    $interpreter = Join-Path $base "versions/$Expected/python.exe"
    & $interpreter -I -B (Join-Path $PSScriptRoot 'smoke_clients.py') $profileRoot --client codex
    if ($LASTEXITCODE) { throw "Registered MCP failed after $Action $Selector" }
}
Push-Location -LiteralPath $profileRoot
try {
    Invoke-Consumer $Previous setup $Previous
    Invoke-Consumer next setup $Current
    Invoke-Consumer $Current rollback $Previous
    Write-Output "Registry rollback verified: $Previous -> next ($Current) -> $Previous"
} finally { Pop-Location }
