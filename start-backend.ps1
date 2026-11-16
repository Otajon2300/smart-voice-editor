param([switch]$InstallOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
# The offline installer brings its own Python (with every package) in `runtime`; otherwise a .venv is made.
$runtime = Join-Path $PSScriptRoot 'runtime\python.exe'
$python = if (Test-Path -LiteralPath $runtime) { $runtime } else { Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }

function Find-Python {
    # faster-whisper and the pinned wheels need Python 3.10-3.12 (Windows 8.1/10/11).
    foreach ($candidate in @(@('py', '-3.12'), @('py', '-3.11'), @('py', '-3.10'), @('python'))) {
        try {
            $exe = $candidate[0]; $extra = @($candidate | Select-Object -Skip 1)
            $version = & $exe @extra -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version -match '^3\.(10|11|12)$') { return ,$candidate }
        } catch {}
    }
    throw "Python 3.10, 3.11 yoki 3.12 topilmadi. python.org dan o'rnating (Windows 8.1 yoki yangisi kerak)."
}

if (-not (Test-Path -LiteralPath $python)) {
    $found = Find-Python
    $exe = $found[0]; $rest = @($found | Select-Object -Skip 1)
    & $exe @rest -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
$stamp = Join-Path $PSScriptRoot '.dependencies.sha256'
# The stamp covers the lock file too: a changed pin reinstalls just like a changed requirement.
$hash = (& $python -c "import hashlib;print(hashlib.sha256(open('requirements.txt','rb').read()+open('requirements-lock.txt','rb').read()).hexdigest().upper())").Trim()
$installed = if (Test-Path -LiteralPath $stamp) { (Get-Content -LiteralPath $stamp | Out-String).Trim() } else { '' }
if ($installed -ne $hash) {
    # requirements-lock.txt pins the tested versions of every package (Python 3.12).
    & $python -m pip install -r requirements.txt -c requirements-lock.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Pinned versions are not available for this Python; installing without the lock file.'
        & $python -m pip install -r requirements.txt
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not install Python dependencies (internet kerak).' }
    Set-Content -LiteralPath $stamp -Value $hash -Encoding Ascii
}
if ($InstallOnly) { Write-Host 'Python muhiti tayyor. Backend paneldan avtomatik ishga tushadi.'; exit 0 }
& $python backend/server.py
