# One clean GUI instance (kills stale UOVidCompiler_GUI.py first, then starts).
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $root "Kill-AutoVideoCompiler-GUI.ps1")
Set-Location $root
Start-Process -FilePath "python" -ArgumentList "UOVidCompiler_GUI.py" -WorkingDirectory $root
Write-Host "Started Auto Video Compiler GUI from $root"
