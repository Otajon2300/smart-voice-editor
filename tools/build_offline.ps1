# Builds the offline installer: dist\offline-<version>\SmartVoiceEditor-Setup.exe + SmartVoiceEditor.data.001, ...
# Everything the program needs is inside: Python, packages (with CUDA), the Uzbek models and Whisper Medium
# (Russian; English uses the same model). Copy the whole folder to the other computer and run Setup.exe.
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_offline.ps1 [-SkipTests]
param([switch]$SkipTests, [long]$PartSize = 1900MB)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

# 1. Program files: the same package as an update (tests run here unless skipped).
$arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'build_dist.ps1'))
if ($SkipTests) { $arguments += '-SkipTests' }
& powershell @arguments
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
$server = Get-Content -LiteralPath 'backend\server.py' -Raw -Encoding UTF8
if ($server -notmatch "VERSION = '([\d.]+)'") { throw 'Version not found.' }
$version = $Matches[1]

$work = Join-Path $root 'dist\offline-stage'
$stage = Join-Path $work 'SmartVoiceEditor'
if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
New-Item -ItemType Directory -Force -Path $work | Out-Null
Expand-Archive -LiteralPath "dist\SmartVoiceEditor-$version.zip" -DestinationPath $work

function Copy-Tree($from, $to, [string[]]$skipDirs = @()) {
    $options = @($from, $to, '/E', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
    if ($skipDirs.Count) { $options += '/XD'; $options += $skipDirs }
    & robocopy @options | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Copy failed: $from" }
}

# 2. Python: the interpreter the .venv was made from, with the .venv's packages in its own site-packages.
$config = Get-Content -LiteralPath '.venv\pyvenv.cfg'
$home_ = (($config | Where-Object { $_ -match '^home\s*=' }) -replace '^home\s*=\s*', '').Trim()
if (-not (Test-Path -LiteralPath (Join-Path $home_ 'python.exe'))) { throw "Base Python not found: $home_" }
$runtime = Join-Path $stage 'runtime'
Copy-Tree $home_ $runtime @((Join-Path $home_ 'Lib\site-packages'), (Join-Path $home_ 'Doc'), (Join-Path $home_ 'Lib\test'), (Join-Path $home_ 'Scripts'))
Copy-Tree (Join-Path $root '.venv\Lib\site-packages') (Join-Path $runtime 'Lib\site-packages') @('__pycache__')
# Visual C++ runtime next to python.exe: the other computer may not have it installed.
foreach ($dll in 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'concrt140.dll') {
    $file = Join-Path $env:WINDIR "System32\$dll"
    if ((Test-Path -LiteralPath $file) -and -not (Test-Path -LiteralPath (Join-Path $runtime $dll))) { Copy-Item -LiteralPath $file -Destination $runtime }
}
# The packages are already there: the first start must not run pip.
$hash = (& (Join-Path $runtime 'python.exe') -c "import hashlib;print(hashlib.sha256(open('requirements.txt','rb').read()+open('requirements-lock.txt','rb').read()).hexdigest().upper())").Trim()
Set-Content -LiteralPath (Join-Path $stage '.dependencies.sha256') -Value $hash -Encoding Ascii
& (Join-Path $runtime 'python.exe') -c "import faster_whisper, ctranslate2, av, numpy, rapidfuzz, filelock; print('runtime ok')"
if ($LASTEXITCODE -ne 0) { throw 'The copied Python does not start.' }

# 3. Models: Kotib (Uzbek) and the pinned Hugging Face snapshots (Uzbek Small, Whisper Medium).
$kotib = Join-Path $root '.models\kotib-medium'
if ((Get-Item -LiteralPath (Join-Path $kotib 'model.bin')).Length -ne 3055769749) { throw 'Kotib model is not complete.' }
Copy-Tree $kotib (Join-Path $stage '.models\kotib-medium')
$hub = Join-Path $env:USERPROFILE '.cache\huggingface\hub'
foreach ($model in @(@('maqsudxo1ja/uz-whisper-small-stt-v2', 'bf1e5a0866a83277b2f7de1affe82a954710c612'),
                     @('Systran/faster-whisper-medium', '08e178d48790749d25932bbc082711ddcfdfbc4f'))) {
    $name = 'models--' + $model[0].Replace('/', '--')
    $found = $null
    foreach ($place in (Join-Path $root ".models\hf\$name"), (Join-Path $hub $name)) {
        if (Test-Path -LiteralPath (Join-Path $place "snapshots\$($model[1])\model.bin")) { $found = $place; break }
    }
    if (-not $found) { throw "Model $($model[0]) is not on this computer: run one analysis in that language first." }
    Copy-Tree (Join-Path $found "snapshots\$($model[1])") (Join-Path $stage ".models\hf\$name\snapshots\$($model[1])")
}

# 4. The installer and the archive parts.
$out = Join-Path $root "dist\offline-$version"
if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$src = Join-Path $PSScriptRoot 'installer'
$refs = '/r:System.IO.Compression.dll', '/r:System.IO.Compression.FileSystem.dll', '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll'
& $csc /nologo /codepage:65001 /optimize /target:exe "/out:$work\pack.exe" @refs (Join-Path $src 'Pack.cs') (Join-Path $src 'Parts.cs')
if ($LASTEXITCODE -ne 0) { throw 'pack.exe did not compile.' }
& $csc /nologo /codepage:65001 /optimize /target:winexe "/out:$out\SmartVoiceEditor-Setup.exe" @refs (Join-Path $src 'Setup.cs') (Join-Path $src 'Parts.cs')
if ($LASTEXITCODE -ne 0) { throw 'Setup.exe did not compile.' }
& "$work\pack.exe" $stage (Join-Path $out 'SmartVoiceEditor.data') $PartSize
if ($LASTEXITCODE -ne 0) { throw 'Packing failed.' }
@"
Smart Voice Editor $version — internetsiz o'rnatish (otashDEV)

1. Shu papkani to'liq (Setup.exe va barcha SmartVoiceEditor.data.0xx fayllari) boshqa kompyuterga ko'chiring.
2. Premiere Pro'ni yoping va SmartVoiceEditor-Setup.exe ni ishga tushiring.
3. Premiere Pro: Window > Extensions > Smart Voice Editor.

Talablar: Windows 10/11 64-bit, Premiere Pro 2017 yoki yangisi. NVIDIA videokarta bo'lsa tezroq ishlaydi.
Internet faqat yangilanish uchun kerak (panel o'zi taklif qiladi).
"@ | Set-Content -LiteralPath (Join-Path $out "O'QING.txt") -Encoding UTF8
Remove-Item -LiteralPath $work -Recurse -Force
Get-ChildItem -LiteralPath $out | ForEach-Object { Write-Host ("{0,-36} {1,10:N0} MB" -f $_.Name, ($_.Length / 1MB)) }
