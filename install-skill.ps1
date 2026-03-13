param(
    [string]$SkillRoot = (Join-Path $HOME '.agents\skills'),
    [switch]$RegisterGhAlias
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceSkillDir = Join-Path $repoRoot 'skills\foundry-model-availability'
$targetSkillDir = Join-Path $SkillRoot 'foundry-model-availability'

if (-not (Test-Path $sourceSkillDir)) {
    throw "Skill source folder not found: $sourceSkillDir"
}

New-Item -ItemType Directory -Path $SkillRoot -Force | Out-Null

if (Test-Path $targetSkillDir) {
    Remove-Item -Path $targetSkillDir -Recurse -Force
}

Copy-Item -Path $sourceSkillDir -Destination $targetSkillDir -Recurse -Force
Write-Host "Installed skill to $targetSkillDir"

if ($RegisterGhAlias) {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if (-not $gh) {
        throw 'GitHub CLI (gh) is not installed or not on PATH.'
    }

    $nodeScriptPath = Join-Path $repoRoot 'bin\foundry-models.js'
    if (-not (Test-Path $nodeScriptPath)) {
        throw "GitHub CLI node entrypoint not found: $nodeScriptPath"
    }

    $shellSafeScriptPath = $nodeScriptPath -replace '\\', '/'
    $aliasExpansion = "node `"$shellSafeScriptPath`" `"`$@`""
    $aliasExpansion | & gh alias set --shell --clobber foundry-models -
    Write-Host 'Registered gh alias: gh foundry-models'
}

Write-Host 'Skill installation complete.'