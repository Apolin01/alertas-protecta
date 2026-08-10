' start_autonomous_launcher.vbs — Lanza start_autonomous.ps1 completamente
' oculto. La tarea programada "AlertasProtecta" llama a este .vbs en vez de
' a powershell.exe directamente: llamar powershell.exe -WindowStyle Hidden
' directo desde el Programador de Tareas (logon type Interactive) terminaba
' el proceso con STATUS_CONTROL_C_EXIT (0xC000013A) justo despues de lanzar
' el bridge, sin ningun error propio — nunca llegaba a lanzar main.py. Mismo
' workaround que ya usaba watchdog_launcher.vbs para watchdog.ps1.

Option Explicit
Dim oShell, oFSO, sDir

Set oShell = CreateObject("WScript.Shell")
Set oFSO   = CreateObject("Scripting.FileSystemObject")
sDir = oFSO.GetParentFolderName(WScript.ScriptFullName)

' 0 = ventana oculta, True = esperar a que termine (corre en loop infinito)
oShell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & sDir & "\start_autonomous.ps1""", 0, True
