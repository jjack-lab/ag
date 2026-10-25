$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $PSScriptRoot 'launcher\Program.cs'
$output = Join-Path $root 'XingMuLauncher.exe'
if (Test-Path -LiteralPath $output) {
    Remove-Item -LiteralPath $output -Force
}
Add-Type -Path $source -OutputAssembly $output -OutputType ConsoleApplication
Write-Host "Built $output"
