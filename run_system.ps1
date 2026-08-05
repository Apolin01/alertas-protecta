# run_system.ps1 - Ejecuta ambos procesos en paralelo (PowerShell)
# Uso: powershell -ExecutionPolicy Bypass -File run_system.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ALERTAS PROTECTA - Sistema Completo" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Este script inicia:" -ForegroundColor Yellow
Write-Host "  1. WhatsApp Bridge (Node.js en puerto 3000)" -ForegroundColor Yellow
Write-Host "  2. Sistema de Alertas (Python main.py)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Espera a que ambos procesos estén listos..." -ForegroundColor Yellow
Write-Host ""

# Cambiar al directorio del script
Set-Location (Split-Path $PSCommandPath -Parent)

# Función para iniciar proceso en ventana nueva
function Start-ProcessInNewWindow {
    param(
        [string]$Title,
        [string]$Command,
        [string]$WorkingDirectory = (Get-Location)
    )
    
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = "powershell.exe"
    $processInfo.Arguments = "-NoExit -Command `"Set-Location '$WorkingDirectory'; $Command`""
    $processInfo.UseShellExecute = $true
    $processInfo.CreateNoWindow = $false
    $processInfo.WindowStyle = 'Normal'
    
    $process = [System.Diagnostics.Process]::Start($processInfo)
    [System.Diagnostics.Process]::GetCurrentProcess().MainWindowTitle = $Title
    
    return $process
}

# Iniciar el bridge
Write-Host "[1/2] Iniciando WhatsApp Bridge..." -ForegroundColor Green
$bridgeDir = Join-Path (Get-Location) "whatsapp_bridge"
$bridgeProcess = Start-ProcessInNewWindow -Title "WhatsApp Bridge" -Command "node server.js" -WorkingDirectory $bridgeDir

# Esperar a que el bridge se inicie
Write-Host "[*] Esperando 5 segundos para que el bridge se inicie..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Iniciar main.py
# Se invoca el python del .venv por ruta explicita: la ventana nueva arranca
# sin el entorno activado, y el python del sistema no tiene psycopg2.
Write-Host "[2/2] Iniciando sistema de alertas..." -ForegroundColor Green
$mainProcess = Start-ProcessInNewWindow -Title "Sistema de Alertas" -Command "& '.\.venv\Scripts\python.exe' main.py" -WorkingDirectory (Get-Location)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✓ Ambos procesos iniciados" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Dos ventanas de PowerShell deberían haber aparecido:" -ForegroundColor Yellow
Write-Host "  - 'WhatsApp Bridge': servidor Node en puerto 3000" -ForegroundColor Yellow
Write-Host "  - 'Sistema de Alertas': procesamiento y envío" -ForegroundColor Yellow
Write-Host ""
Write-Host "Para DETENER TODO:" -ForegroundColor Yellow
Write-Host "  1. Cierra ambas ventanas (Ctrl+C)" -ForegroundColor Yellow
Write-Host "  2. O ejecuta: taskkill /F /IM node.exe" -ForegroundColor Yellow
Write-Host ""
Write-Host "Presiona Enter para salir de este script..." -ForegroundColor Gray
Read-Host
