<#
.SYNOPSIS
Runs one stage of the portable WAID4500 reproduction workflow.

.PARAMETER Mode
Select verify, rebuild, smoke, train, or resume.

.PARAMETER Python
Python executable used to run the reproduction scripts.

.PARAMETER ProjectRoot
Root of the Agrinebula project containing local WAID assets.

.PARAMETER Device
Optional Ultralytics device override such as 0 or cpu.

.PARAMETER Resume
Checkpoint used by resume mode.
#>
[CmdletBinding()]
param(
    [ValidateSet('verify', 'rebuild', 'smoke', 'train', 'resume')]
    [string]$Mode = 'verify',
    [string]$Python = $env:AGRINEBULA_PYTHON,
    [string]$ProjectRoot = (Join-Path $PSScriptRoot '..\..'),
    [string]$Device,
    [string]$Resume
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = 'python'
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    $pythonCommand = Get-Command $Python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "Python executable not found: $Python"
    }
    $Python = $pythonCommand.Source
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$rebuildScript = Join-Path $PSScriptRoot 'rebuild_waid4500.py'
$trainScript = Join-Path $PSScriptRoot 'train_waid_yolo11s.py'
$verifyScript = Join-Path $PSScriptRoot 'verify_waid_reproduction.py'

switch ($Mode) {
    'verify' {
        $arguments = @($verifyScript, '--project-root', $ProjectRoot)
    }
    'rebuild' {
        $arguments = @(
            $rebuildScript,
            '--raw-root', (Join-Path $ProjectRoot 'data\external\waid\raw'),
            '--manifest', (Join-Path $ProjectRoot 'reproducibility\waid4500\dataset_manifest.csv'),
            '--output', (Join-Path $ProjectRoot 'data\external\waid\derived\waid4500_rebuilt')
        )
    }
    'smoke' {
        $arguments = @($trainScript, '--project-root', $ProjectRoot, '--smoke')
        if (-not [string]::IsNullOrWhiteSpace($Device)) {
            $arguments += @('--device', $Device)
        }
    }
    'train' {
        $arguments = @($trainScript, '--project-root', $ProjectRoot)
        if (-not [string]::IsNullOrWhiteSpace($Device)) {
            $arguments += @('--device', $Device)
        }
    }
    'resume' {
        if ([string]::IsNullOrWhiteSpace($Resume)) {
            throw 'Resume mode requires -Resume <checkpoint>.'
        }
        $arguments = @($trainScript, '--project-root', $ProjectRoot, '--resume', $Resume)
        if (-not [string]::IsNullOrWhiteSpace($Device)) {
            $arguments += @('--device', $Device)
        }
    }
}

& $Python @arguments
exit $LASTEXITCODE
