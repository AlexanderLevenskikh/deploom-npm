$ErrorActionPreference = 'Stop'
npm.cmd install --global @openai/codex@0.165.0 @anthropic-ai/claude-code@2.1.241
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$archive = Join-Path $env:RUNNER_TEMP 'opencode-windows-x64.zip'
Invoke-WebRequest 'https://github.com/anomalyco/opencode/releases/download/v2.2.5/opencode-windows-x64.zip' -OutFile $archive
if ((Get-FileHash $archive).Hash -ne '2f3bfd6b3527c60c2a882557b20ddc9ba6bdff4b5a8fe61c853da8fcfb3076e8') { throw 'OpenCode digest mismatch' }
$dir = Join-Path $env:RUNNER_TEMP 'opencode'
Expand-Archive $archive $dir
(Get-ChildItem $dir -Recurse -Filter opencode.exe -File).Directory.FullName >> $env:GITHUB_PATH
