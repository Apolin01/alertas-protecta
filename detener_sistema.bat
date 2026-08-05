@echo off
echo ========================================
echo   ALERTAS PROTECTA - Detener Sistema
echo ========================================
echo.

REM Detener bridge buscando el PID que escucha en puerto 3000
echo Deteniendo WhatsApp Bridge (puerto 3000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   Bridge detenido ^(PID %%a^).
)

REM Detener Python (main.py)
echo Deteniendo Sistema de Alertas (Python)...
taskkill /F /IM python.exe  >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
echo   Python detenido.

echo.
echo ========================================
echo   Sistema detenido completamente.
echo ========================================
echo.
pause
