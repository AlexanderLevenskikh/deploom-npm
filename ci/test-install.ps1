param(
    [Parameter(Mandatory)][string] $Tarball,
    [Parameter(Mandatory)][string] $Work,
    [string] $ClaudeCommand = "claude.cmd"
)
$ErrorActionPreference = 'Stop'
$Work = [IO.Path]::GetFullPath($Work)
if (Test-Path -LiteralPath $Work) { throw 'Smoke test requires a fresh directory' }
$testProfile = Join-Path $Work 'home'
New-Item -ItemType Directory -Path $testProfile | Out-Null
$env:USERPROFILE = $testProfile
$env:LOCALAPPDATA = Join-Path $testProfile 'local'
$env:APPDATA = Join-Path $testProfile 'roaming'
$env:CODEX_HOME = Join-Path $testProfile '.codex'
$env:CLAUDE_CONFIG_DIR = Join-Path $testProfile '.claude'
$env:OPENCODE_CONFIG_DIR = Join-Path $testProfile '.config/opencode'
$env:OPENCODE_CONFIG = Join-Path $env:OPENCODE_CONFIG_DIR 'opencode.jsonc'
$env:XDG_DATA_HOME = Join-Path $testProfile '.local/share'
$env:XDG_CACHE_HOME = Join-Path $testProfile '.cache'
$env:XDG_STATE_HOME = Join-Path $testProfile '.local/state'
$env:npm_config_cache = Join-Path $Work 'empty-npm-cache'
$env:npm_config_offline = 'true'
$env:DEPLOOM_MCP_STATE_DIR = Join-Path $testProfile 'state'
$install = Join-Path $Work 'install'
npm.cmd install --prefix $install --offline --no-fund --no-audit --no-package-lock $Tarball
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$package = Join-Path $install 'node_modules/@levencode/deploom'
node (Join-Path $package 'bin/verify-runtime.cjs')
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$cli = Join-Path $install 'node_modules/.bin/deploom.cmd'
foreach ($client in 'claude', 'codex', 'opencode') {
    foreach ($attempt in 1..2) {
        & $cli setup $client
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    }
}
$version = (Get-Content (Join-Path $package 'package.json') -Raw | ConvertFrom-Json).version
$active = Join-Path $env:LOCALAPPDATA "DepLoom/public/versions/$version/python.exe"
& $active -c "import sys, win32job; from deploom_mcp import server; assert sys.dont_write_bytecode"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $cli setup codex
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& (Join-Path $package 'runtime/python.exe') -I -B -u (Join-Path $PSScriptRoot 'smoke_clients.py') $testProfile
if ($LASTEXITCODE) { exit $LASTEXITCODE }
node (Join-Path $PSScriptRoot 'codex-skill.cjs') $testProfile
if ($LASTEXITCODE) { exit $LASTEXITCODE }
Push-Location -LiteralPath $testProfile
try {
    node (Join-Path $PSScriptRoot 'opencode-skill.cjs')
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    $env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1'
    $env:DISABLE_AUTOUPDATER = '1'
    $request = '{"type":"control_request","request_id":"check-skill","request":{"subtype":"initialize"}}'
    $packets = $request | & $ClaudeCommand -p --input-format stream-json --output-format stream-json --verbose --no-session-persistence
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    $reply = $packets | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object { $_.type -eq 'control_response' -and $_.response.request_id -eq 'check-skill' }
    if ($reply.response.subtype -ne 'success' -or 'deploom-upgrade' -notin $reply.response.response.commands.name) {
        throw 'Claude Code did not discover the installed Skill'
    }
    Write-Output 'Claude Code discovered the installed Skill'
} finally {
    Pop-Location
}
