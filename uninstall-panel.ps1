$ErrorActionPreference = 'Stop'
# Removes the panel link from the CEP extensions folder and stops a running backend.
# The project folder, the models and the PlayerDebugMode setting (other unsigned panels may need it) stay.
$target = Join-Path $env:APPDATA 'Adobe\CEP\extensions\uz.smartvoice.editor'
if (Test-Path -LiteralPath $target) {
    $item = Get-Item -LiteralPath $target -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) { throw "$target is a real folder, not the link made by setup.cmd. Remove it manually." }
    cmd /c rmdir "$target" | Out-Null
    Write-Host 'Panel link removed.'
} else { Write-Host 'Panel link was not installed.' }
$runtime = Join-Path $PSScriptRoot '.runtime.json'
if (Test-Path -LiteralPath $runtime) {
    try {
        $info = Get-Content -LiteralPath $runtime -Raw | ConvertFrom-Json
        $process = Get-Process -Id $info.pid -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -like 'python*') { Stop-Process -Id $info.pid -Force; Write-Host 'Backend stopped.' }
    } catch {}
}
Write-Host 'Done. Restart Premiere. To remove everything, delete this folder (the models in .models take about 5 GB).'
