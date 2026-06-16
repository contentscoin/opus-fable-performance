param(
  [switch]$Global
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SkillSrc = Join-Path $RepoRoot ".agents\skills\opus-fable"

if ($Global) {
  $SkillDst = Join-Path $env:USERPROFILE ".codex\skills\opus-fable"
  New-Item -ItemType Directory -Force -Path (Split-Path $SkillDst) | Out-Null
  if (Test-Path $SkillDst) { Remove-Item -Recurse -Force $SkillDst }
  Copy-Item -Recurse -LiteralPath $SkillSrc -Destination $SkillDst
  Write-Output "Installed Codex skill globally: $SkillDst"
  Write-Output "Codex plugin hooks live in hooks\hooks.json. Install or trust the plugin separately if you want automatic evidence hooks."
  Write-Output "Restart Codex or open a new thread to pick it up."
} else {
  $SkillDst = Join-Path (Get-Location) ".agents\skills\opus-fable"
  New-Item -ItemType Directory -Force -Path (Split-Path $SkillDst) | Out-Null
  if (Test-Path $SkillDst) { Remove-Item -Recurse -Force $SkillDst }
  Copy-Item -Recurse -LiteralPath $SkillSrc -Destination $SkillDst
  Copy-Item -LiteralPath (Join-Path $RepoRoot "codex\AGENTS.opus-fable.md") -Destination (Join-Path (Get-Location) "AGENTS.md") -Force
  Write-Output "Installed Codex skill locally: $SkillDst"
  Write-Output "For automatic evidence hooks, install this repository as a Codex plugin and review hooks\hooks.json."
}
