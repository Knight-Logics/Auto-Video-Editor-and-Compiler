# One clean GUI instance (kills stale UOVidCompiler_GUI.py first, then starts without a console).
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $root "Kill-AutoVideoCompiler-GUI.ps1")
Set-Location $root

function Resolve-PythonwPath {
    $pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($pythonw) {
        return $pythonw.Source
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        $candidate = Join-Path (Split-Path $python.Source -Parent) "pythonw.exe"
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

$launcher = Resolve-PythonwPath
if ($launcher) {
    Start-Process -FilePath $launcher -ArgumentList "UOVidCompiler_GUI.py" -WorkingDirectory $root -WindowStyle Hidden
    Write-Host "Started Auto Video Compiler GUI (no console) from $root"
} else {
    Start-Process -FilePath "python" -ArgumentList "UOVidCompiler_GUI.py" -WorkingDirectory $root -WindowStyle Hidden
    Write-Host "Started Auto Video Compiler GUI from $root (pythonw.exe not found; using python.exe hidden)"
}
