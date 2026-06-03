' Double-click launcher: no CMD or PowerShell window.
Set shell = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
ps1 = Chr(34) & root & "\Run-AutoVideoCompiler-GUI.ps1" & Chr(34)
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & ps1, 0, False
