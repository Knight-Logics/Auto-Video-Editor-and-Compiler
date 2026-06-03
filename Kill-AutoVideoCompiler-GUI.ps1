# Stops ONLY Auto Video Compiler GUI (UOVidCompiler_GUI.py), not other Python apps.
$targets = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -match 'UOVidCompiler_GUI' }

if (-not $targets) {
    Write-Host "No Auto Video Compiler GUI process found (UOVidCompiler_GUI.py)."
    foreach ($pidFile in @(
            (Join-Path $PSScriptRoot "gui.pid"),
            (Join-Path $env:PROGRAMDATA "KnightLogics\AutoVidCompiler\gui.pid"),
            (Join-Path $env:APPDATA "KnightLogics\AutoVidCompiler\gui.pid")
        )) {
        if (Test-Path $pidFile) { Remove-Item $pidFile -Force }
    }
    exit 0
}

foreach ($proc in $targets) {
    Write-Host "Stopping PID $($proc.ProcessId): $($proc.CommandLine)"
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

foreach ($pidFile in @(
        (Join-Path $PSScriptRoot "gui.pid"),
        (Join-Path $env:PROGRAMDATA "KnightLogics\AutoVidCompiler\gui.pid"),
        (Join-Path $env:APPDATA "KnightLogics\AutoVidCompiler\gui.pid")
    )) {
    if (Test-Path $pidFile) { Remove-Item $pidFile -Force }
}
Write-Host "Done."
