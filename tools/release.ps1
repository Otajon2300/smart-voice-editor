# Publishes the current version as a GitHub release; installed panels offer it as an update.
#   1. Raise the version everywhere (backend\server.py, extension\panel.js, extension\host.jsx,
#      extension\index.html, extension\CSXS\manifest.xml, README.md).
#   2. powershell -NoProfile -ExecutionPolicy Bypass -File tools\release.ps1 -Notes "What changed"
# Runs the tests, builds dist\SmartVoiceEditor-<version>.zip + .sha256, commits, tags and uploads them.
param([Parameter(Mandatory = $true)][string]$Notes, [string]$Repo = 'Otajon2300/smart-voice-editor')
# Native tools (git, gh) write notices to stderr; Windows PowerShell would stop on them, so every
# step checks its exit code instead.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$git = @('-c', ('safe.directory=' + $root.Replace('\', '/')))

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'build_dist.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
$server = Get-Content -LiteralPath 'backend\server.py' -Raw -Encoding UTF8
if ($server -notmatch "VERSION = '([\d.]+)'") { throw 'Version not found.' }
$version = $Matches[1]
$tag = "v$version"
$zip = "dist\SmartVoiceEditor-$version.zip"
$sum = "dist\SmartVoiceEditor-$version.sha256"

# The online installer goes with every release, so .../releases/latest/download/<name> always works.
$online = 'dist\SmartVoiceEditor-Online-Setup.exe'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $csc /nologo /codepage:65001 /optimize /target:winexe "/out:$online" "/win32icon:$(Join-Path $PSScriptRoot 'installer\logo.ico')" '/r:System.IO.Compression.dll' '/r:System.IO.Compression.FileSystem.dll' '/r:System.Windows.Forms.dll' '/r:System.Drawing.dll' (Join-Path $PSScriptRoot 'installer\OnlineSetup.cs')
if ($LASTEXITCODE -ne 0) { throw 'The online installer did not compile.' }

& gh release view $tag --repo $Repo 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { throw "Release $tag already exists. Raise the version first." }

& git @git add -A
& git @git commit -m "Release $tag" -m $Notes
if ($LASTEXITCODE -ne 0) { Write-Host 'Nothing new to commit.' }
& git @git tag -a $tag -m "Release $tag"
if ($LASTEXITCODE -ne 0) { throw "Could not tag $tag." }
& git @git push origin main --follow-tags
if ($LASTEXITCODE -ne 0) { throw 'git push failed.' }
& gh release create $tag $zip $sum $online --repo $Repo --title "Smart Voice Editor $version" --notes $Notes
if ($LASTEXITCODE -ne 0) { throw 'Could not create the GitHub release.' }
Write-Host "Released $tag. Panels with internet will offer the update."
