$ErrorActionPreference = 'Stop'
# Links the panel folder into the per-user CEP extensions folder and allows
# unsigned panels for every CEP version from Premiere Pro 2017 (CSXS.7) onward.
$source = Join-Path $PSScriptRoot 'extension'
$extensions = Join-Path $env:APPDATA 'Adobe\CEP\extensions'
if (-not (Test-Path -LiteralPath $extensions)) { New-Item -ItemType Directory -Force -Path $extensions | Out-Null }
$target = Join-Path $extensions 'uz.smartvoice.editor'
if (Test-Path -LiteralPath $target) {
    $item = Get-Item -LiteralPath $target -Force
    $isLink = ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
    if (-not $isLink) { throw "Another installation exists at $target. Check it manually." }
    # Re-point an old junction (for example after the folder was moved).
    cmd /c rmdir "$target" | Out-Null
}
# mklink works on Windows 7+ and every PowerShell version, unlike New-Item -ItemType Junction.
cmd /c mklink /J "$target" "$source" | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $target 'CSXS\manifest.xml'))) { throw 'Could not link the panel folder.' }
foreach ($version in 7..16) {
    & reg.exe add "HKCU\Software\Adobe\CSXS.$version" /v PlayerDebugMode /t REG_SZ /d 1 /f | Out-Null
}
Write-Host 'Panel installed. Restart Premiere: Window > Extensions > Smart Voice Editor.'
