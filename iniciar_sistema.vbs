Option Explicit
Dim oShell, oFSO, sDir

Set oShell = CreateObject("WScript.Shell")
Set oFSO   = CreateObject("Scripting.FileSystemObject")
sDir = oFSO.GetParentFolderName(WScript.ScriptFullName)

' Crear carpeta logs si no existe
If Not oFSO.FolderExists(sDir & "\logs") Then
    oFSO.CreateFolder(sDir & "\logs")
End If

' Matar instancia previa del bridge en puerto 3000
oShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -ano ^| findstr "":3000 "" ^| findstr LISTENING') do taskkill /F /PID %a >nul 2>&1", 0, True
WScript.Sleep 1500

' 1. Iniciar WhatsApp Bridge (ventana oculta)
'    Los logs del bridge van a logs\bridge.log
oShell.Run "cmd /c cd /d """ & sDir & "\whatsapp_bridge"" && node server.js >> """ & sDir & "\logs\bridge.log"" 2>&1", 0, False

WScript.Sleep 5000

' 2. Iniciar Sistema de Alertas Python (ventana oculta)
'    main.py escribe a alertas.log por su propio logger
oShell.Run "cmd /c cd /d """ & sDir & """ && .venv\Scripts\python.exe main.py", 0, False

' Confirmacion visual (aparece una sola vez y desaparece al cerrar)
MsgBox "Sistema Alertas Protecta iniciado en segundo plano." & vbCrLf & vbCrLf & _
       "WhatsApp QR:  http://localhost:3000/qr" & vbCrLf & vbCrLf & _
       "Logs bridge:  logs\bridge.log" & vbCrLf & _
       "Logs alertas: alertas.log" & vbCrLf & vbCrLf & _
       "Para detener: detener_sistema.bat", _
       vbInformation, "Alertas Protecta Peru"
