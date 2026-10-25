$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root 'XingMuLauncher.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Launcher EXE does not exist: $exe"
}
$output = & $exe --check 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Launcher self-check failed: $output"
}
if (-not (Test-Path -LiteralPath ([string]$output) -PathType Leaf) -or [System.IO.Path]::GetExtension([string]$output) -ne '.bat') {
    throw "Launcher did not resolve the project start script: $output"
}
Write-Host 'Launcher self-check passed.'

$smokeDir = Join-Path $root '.test-tmp\launcher-smoke'
New-Item -ItemType Directory -Path $smokeDir -Force | Out-Null
$copiedExe = Join-Path $smokeDir 'XingMuLauncher.exe'
$marker = Join-Path $smokeDir 'launched.txt'
$scriptName = [System.IO.Path]::GetFileName([string]$output)
$fakeScript = Join-Path $smokeDir $scriptName
Copy-Item -LiteralPath $exe -Destination $copiedExe -Force
Set-Content -LiteralPath $fakeScript -Value '@echo off', 'echo launched>launched.txt' -Encoding ASCII
if (Test-Path -LiteralPath $marker) { Remove-Item -LiteralPath $marker -Force }
& $copiedExe
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $marker -PathType Leaf)) {
    throw 'Launcher did not execute the adjacent start script.'
}
Write-Host 'Launcher process smoke test passed.'
