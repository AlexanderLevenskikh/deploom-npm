param([string] $Tarball, [switch] $InContainer)
$ErrorActionPreference = 'Stop'
if ($InContainer) {
    $system = Join-Path $env:windir 'System32'
    foreach ($file in 'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll') {
        if (Test-Path -LiteralPath (Join-Path $system $file)) { throw "Base image already contains $file" }
    }
    $env:PATH = 'C:\inputs;' + $env:PATH
    $env:npm_config_cache = 'C:\offline-test\empty-cache'
    $env:USERPROFILE = 'C:\offline-test\user'
    $env:LOCALAPPDATA = Join-Path $env:USERPROFILE 'local'
    $env:CLAUDE_CONFIG_DIR = Join-Path $env:USERPROFILE '.claude'
    $archive = (Get-ChildItem C:\inputs -Filter '*.tgz').FullName
    & C:\inputs\node.exe C:\inputs\npm\bin\npm-cli.js install --offline --prefix C:\offline-test\install --no-audit --no-fund --no-package-lock $archive
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    $pkg = 'C:\offline-test\install\node_modules\@levencode\deploom'
    & C:\inputs\node.exe (Join-Path $pkg 'bin/deploom.cjs') setup claude
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    $v = (Get-Content (Join-Path $pkg 'package.json') -Raw | ConvertFrom-Json).version
    $python = Join-Path $env:LOCALAPPDATA "DepLoom\public\versions\$v\python.exe"
    & $python -I -B -c "import win32job; from deploom_mcp import server; from z3 import Int,Solver,sat; s=Solver(); x=Int('x'); s.add(x==17); assert s.check()==sat and s.model()[x].as_long()==17"
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    Write-Output "Offline setup and Z3 passed on Windows $([Environment]::OSVersion.Version) with an empty npm cache and no system Visual C++ runtime."
    exit 0
}
$stage = Join-Path $env:RUNNER_TEMP 'deploom-offline-inputs'
New-Item -ItemType Directory $stage | Out-Null
$node = (Get-Command node.exe).Source
Copy-Item -LiteralPath $node, $Tarball, $PSCommandPath -Destination $stage
Copy-Item -LiteralPath (Join-Path (Split-Path $node) 'node_modules/npm') -Destination (Join-Path $stage 'npm') -Recurse
$base = 'mcr.microsoft.com/windows/servercore:ltsc2025'
docker pull $base
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$id = docker image inspect $base --format '{{.Id}}'
if ($LASTEXITCODE) { exit $LASTEXITCODE }
Write-Output "Windows base image $id"
docker run --rm --isolation process --network none --mount "type=bind,source=$stage,target=C:\inputs,readonly" $id powershell -NoProfile -ExecutionPolicy RemoteSigned -File C:\inputs\test-clean-windows.ps1 -InContainer
exit $LASTEXITCODE
