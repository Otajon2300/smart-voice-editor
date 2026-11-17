# Draws the program logo (green sound wave on a dark rounded square) into tools\installer\logo.ico.
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\make_icon.ps1
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$out = Join-Path $PSScriptRoot 'installer\logo.ico'

function Draw([int]$size) {
    $bmp = New-Object System.Drawing.Bitmap $size, $size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $g.Clear([System.Drawing.Color]::Transparent)
    $r = [single]($size * 0.22)
    $s = [single]($size - 1)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc(0, 0, $r, $r, 180, 90)
    $path.AddArc($s - $r, 0, $r, $r, 270, 90)
    $path.AddArc($s - $r, $s - $r, $r, $r, 0, 90)
    $path.AddArc(0, $s - $r, $r, $r, 90, 90)
    $path.CloseFigure()
    $bg = New-Object System.Drawing.Drawing2D.LinearGradientBrush (New-Object System.Drawing.Point 0, 0), (New-Object System.Drawing.Point 0, $size), ([System.Drawing.Color]::FromArgb(255, 40, 44, 52)), ([System.Drawing.Color]::FromArgb(255, 18, 20, 24))
    $g.FillPath($bg, $path)

    # Sound-wave bars; the middle one is cut short, like a cleaned recording.
    $heights = @(0.30, 0.55, 0.80, 0.42, 0.66, 0.36)
    $green = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 61, 220, 132))
    $n = $heights.Count
    $area = $size * 0.70
    $step = $area / $n
    $w = [math]::Max(1.0, $step * 0.58)
    $x0 = ($size - $area) / 2 + ($step - $w) / 2
    for ($i = 0; $i -lt $n; $i++) {
        $h = [math]::Max($w, $size * $heights[$i])
        $x = [single]($x0 + $i * $step)
        $y = [single](($size - $h) / 2)
        $bar = New-Object System.Drawing.Drawing2D.GraphicsPath
        $d = [single][math]::Min($w, $h)
        $bar.AddArc($x, $y, $d, $d, 180, 180)
        $bar.AddArc($x, [single]($y + $h - $d), $d, $d, 0, 180)
        $bar.CloseFigure()
        $g.FillPath($green, $bar)
    }
    $g.Dispose()
    # Classic 32-bit DIB entry: header, bottom-up BGRA rows, then an empty AND mask.
    $ms = New-Object System.IO.MemoryStream
    $bw = New-Object System.IO.BinaryWriter $ms
    $bw.Write([uint32]40); $bw.Write([int32]$size); $bw.Write([int32]($size * 2))
    $bw.Write([uint16]1); $bw.Write([uint16]32); $bw.Write([uint32]0)
    $bw.Write([uint32]($size * $size * 4)); $bw.Write([int32]0); $bw.Write([int32]0)
    $bw.Write([uint32]0); $bw.Write([uint32]0)
    for ($y = $size - 1; $y -ge 0; $y--) {
        for ($x = 0; $x -lt $size; $x++) {
            $c = $bmp.GetPixel($x, $y)
            $bw.Write([byte]$c.B); $bw.Write([byte]$c.G); $bw.Write([byte]$c.R); $bw.Write([byte]$c.A)
        }
    }
    $bw.Write((New-Object byte[] ([int]([math]::Ceiling($size / 32.0) * 4 * $size))))
    $bw.Flush()
    $bmp.Dispose()
    return ,$ms.ToArray()
}

# ICO file with DIB images, which Windows and .NET both read.
$sizes = @(16, 24, 32, 48, 64, 128, 256)
$images = @($sizes | ForEach-Object { ,(Draw $_) })
$fs = [System.IO.File]::Create($out)
$bw = New-Object System.IO.BinaryWriter $fs
$bw.Write([uint16]0); $bw.Write([uint16]1); $bw.Write([uint16]$sizes.Count)
$offset = 6 + 16 * $sizes.Count
for ($i = 0; $i -lt $sizes.Count; $i++) {
    $d = if ($sizes[$i] -ge 256) { 0 } else { $sizes[$i] }
    $bw.Write([byte]$d); $bw.Write([byte]$d); $bw.Write([byte]0); $bw.Write([byte]0)
    $bw.Write([uint16]1); $bw.Write([uint16]32)
    $bw.Write([uint32]$images[$i].Length); $bw.Write([uint32]$offset)
    $offset += $images[$i].Length
}
foreach ($img in $images) { $bw.Write($img) }
$bw.Close()
Write-Host "Wrote $out"
