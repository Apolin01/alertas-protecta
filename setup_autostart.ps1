# setup_autostart.ps1
# Script de UN SOLO USO para registrar el sistema de alertas en Task Scheduler
# de modo que arranque automaticamente al iniciar sesion en Windows.
#
# Uso (UNA VEZ, abrir PowerShell como ADMINISTRADOR):
#   cd c:\proyectos\alertas-rss-main\alertas-rss-main
#   powershell -ExecutionPolicy Bypass -File setup_autostart.ps1
#
# Para deshabilitar el auto-arranque despues:
#   Unregister-ScheduledTask -TaskName "AlertasProtecta" -Confirm:$false

$ErrorActionPreference = "Stop"

$taskName = "AlertasProtecta"
$root = "c:\proyectos\alertas-rss-main\alertas-rss-main"
$scriptPath = "$root\start_autonomous.ps1"
$launcherPath = "$root\start_autonomous_launcher.vbs"

if (-not (Test-Path $scriptPath)) {
    Write-Host "ERROR: No se encuentra $scriptPath" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $launcherPath)) {
    Write-Host "ERROR: No se encuentra $launcherPath" -ForegroundColor Red
    exit 1
}

# Verificar permisos de admin
$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Este script requiere PowerShell ejecutado como Administrador." -ForegroundColor Red
    Write-Host "       Click derecho en PowerShell -> 'Ejecutar como administrador' y volver a intentar." -ForegroundColor Yellow
    exit 1
}

Write-Host "Registrando tarea programada '$taskName'..." -ForegroundColor Cyan

# Borrar tarea anterior si existe (para poder re-correr este script sin error)
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  Removiendo tarea existente..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Accion: ejecutar el supervisor via el launcher .vbs (no powershell.exe
# directo) — ver comentario en start_autonomous_launcher.vbs.
$action = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument "`"$launcherPath`""

# Trigger: al iniciar sesion del usuario actual, con 30s de retraso.
# Sin el retraso, el proceso a veces recibe una señal de cierre porque la
# sesion todavia se esta inicializando (visto en produccion: LastTaskResult
# 0xC000013A / STATUS_CONTROL_C_EXIT — el supervisor moria justo despues de
# lanzar el bridge, sin ningun error propio, y nunca llegaba a lanzar main.py).
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = "PT30S"

# Settings: reiniciar hasta 3 veces si falla, permitir correr con bateria
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

# Principal: correr como el usuario actual con sus privilegios normales
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Sistema Alertas Protecta - supervisor de Bridge + main.py + ngrok"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  Auto-arranque CONFIGURADO" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "El sistema se iniciara automaticamente la proxima vez que inicies sesion." -ForegroundColor Cyan
Write-Host ""
Write-Host "Comandos utiles:" -ForegroundColor Yellow
Write-Host "  Iniciar ahora:        Start-ScheduledTask -TaskName '$taskName'"
Write-Host "  Detener:              Stop-ScheduledTask  -TaskName '$taskName'"
Write-Host "  Ver estado:           Get-ScheduledTask   -TaskName '$taskName'"
Write-Host "  Deshabilitar:         Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
Write-Host ""
Write-Host "Logs del sistema: c:\proyectos\alertas-rss-main\alertas-rss-main\logs\" -ForegroundColor Yellow
Write-Host ""
