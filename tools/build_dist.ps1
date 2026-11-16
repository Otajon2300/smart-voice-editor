# Builds dist\SmartVoiceEditor-<version>.zip (+ .sha256) from the sources, after running the tests.
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_dist.ps1 [-SkipTests]
param([switch]$SkipTests)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

$server = Get-Content -LiteralPath 'backend\server.py' -Raw -Encoding UTF8
if ($server -notmatch "VERSION = '([\d.]+)'") { throw 'Version not found in backend\server.py.' }
$version = $Matches[1]
# Every place that states the version must agree, or the panel refuses the backend or the host script.
$v = [regex]::Escape($version)
$places = @{
    'extension\panel.js'          = "var VERSION = '$v'"
    'extension\host.jsx'          = "version: '$v'"
    'extension\index.html'        = "SMART VOICE . $v<"
    'extension\CSXS\manifest.xml' = "ExtensionBundleVersion=`"$v`".*\s.*panel`" Version=`"$v`""
    'README.md'                   = "# Smart Voice Editor $v\s"
}
foreach ($file in $places.Keys) {
    $text = Get-Content -LiteralPath $file -Raw -Encoding UTF8
    if ($text -notmatch $places[$file]) { throw "$file does not state version $version." }
}

if (-not $SkipTests) {
    & '.\.venv\Scripts\python.exe' -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
    foreach ($test in 'tests\test_host.cjs', 'tests\test_panel.cjs') {
        & node $test
        if ($LASTEXITCODE -ne 0) { throw "$test failed." }
    }
}

$files = @('README.md', 'setup.cmd', 'uninstall.cmd', 'install-panel.ps1', 'uninstall-panel.ps1', 'install-gpu.ps1',
           'start-backend.ps1', 'requirements.txt', 'requirements-lock.txt', 'requirements-gpu.txt')
foreach ($folder in 'backend', 'extension', 'tests', 'tools') {
    $files += Get-ChildItem -LiteralPath $folder -Recurse -File |
        Where-Object { $_.FullName -notmatch '\\__pycache__\\' -and $_.Extension -ne '.pyc' } |
        # One-line leftovers of 0.7.0 that could not be deleted automatically.
        Where-Object { $_.Length -gt 120 -or (Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8) -notmatch '0\.7\.0 dan qolgan' } |
        ForEach-Object { $_.FullName.Substring($root.Length + 1) }
}

New-Item -ItemType Directory -Force -Path 'dist' | Out-Null
$zip = Join-Path $root "dist\SmartVoiceEditor-$version.zip"
$draft = "$zip.tmp"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$stream = [IO.File]::Open($draft, [IO.FileMode]::Create)
try {
    $archive = New-Object IO.Compression.ZipArchive($stream, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in $files) {
            $name = 'SmartVoiceEditor/' + $file.Replace('\', '/')
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, (Join-Path $root $file), $name) | Out-Null
        }
    } finally { $archive.Dispose() }
} finally { $stream.Dispose() }
Move-Item -LiteralPath $draft -Destination $zip -Force
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
Set-Content -LiteralPath "$zip.sha256".Replace('.zip.sha256', '.sha256') -Value "$hash  SmartVoiceEditor-$version.zip" -Encoding Ascii
Write-Host ("{0} ({1} files, {2:N0} KB)" -f $zip, $files.Count, ((Get-Item -LiteralPath $zip).Length / 1KB))
Write-Host "SHA256 $hash"
