@echo off
REM run_system.bat - Ejecuta ambos procesos (Bridge + Main) en paralelo
REM Uso: run_system.bat

echo ========================================
echo   ALERTAS PROTECTA - Sistema Completo
echo ========================================
echo.
echo Este script inicia:
echo   1. WhatsApp Bridge (Node.js en puerto 3000)
echo   2. Sistema de Alertas (Python main.py)
echo.
echo Espera a que ambos procesos estén listos...
echo.

REM Obtener la ubicación del script
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Cerrar instancias previas del bridge si existieran
echo Cerrando instancias previas en puerto 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Iniciar el bridge en una ventana nueva
echo [1/2] Iniciando WhatsApp Bridge...
start "WhatsApp Bridge" cmd /k "cd whatsapp_bridge && node server.js"

REM Esperar 5 segundos para que el bridge se inicie
timeout /t 5 /nobreak

REM Iniciar main.py en otra ventana
echo [2/2] Iniciando sistema de alertas...
start "Sistema de Alertas" cmd /k "python main.py"

echo.
echo ========================================
echo   ✓ Ambos procesos iniciados
echo ========================================
echo.
echo Dos ventanas deberían haber aparecido:
echo   - "WhatsApp Bridge": nodo servidor en puerto 3000
echo   - "Sistema de Alertas": procesamiento y envío
echo.
echo Para DETENER TODO:
echo   1. Cierra ambas ventanas (Alt+F4)
echo   O
echo   2. Ejecuta: taskkill /F /IM node.exe
echo              taskkill /F /IM python.exe
echo.
