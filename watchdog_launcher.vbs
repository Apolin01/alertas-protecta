' watchdog_launcher.vbs — Lanza watchdog.ps1 completamente oculto (sin
' ventana de PowerShell). La tarea programada "AlertasProtecta - Watchdog"
' llama a este .vbs en vez de a powershell.exe directamente.

Option Explicit
Dim oShell, oFSO, sDir

Set oShell = CreateObject("WScript.Shell")
Set oFSO   = CreateObject("Scripting.FileSystemObject")
sDir = oFSO.GetParentFolderName(WScript.ScriptFullName)

' 0 = ventana oculta, True = esperar a que termine
oShell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & sDir & "\watchdog.ps1""", 0, True
