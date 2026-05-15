@echo off
:: test_recovery.bat — simula un reboot sin reiniciar la PC.
:: Mata pm2 (como si Windows se hubiera apagado) y luego lo restaura
:: igual que lo hara start_alertas.bat al arrancar Windows.

setlocal
set PM2="C:\Users\Operador_02\AppData\Roaming\npm\pm2.cmd"

echo.
echo ============================================================
echo  TEST DE RECUPERACION — simula reboot sin reiniciar la PC
echo ============================================================
echo.

echo [1/4] Estado antes del test:
%PM2% list
echo.

echo [2/4] Matando daemon pm2 (equivale a apagar Windows)...
%PM2% kill
echo.

echo [3/4] Esperando 5s...
timeout /t 5 /nobreak > nul

echo [4/4] Restaurando procesos (lo mismo que hace start_alertas.bat al arrancar)...
%PM2% resurrect
echo.

echo ============================================================
echo  ESTADO FINAL — deberian estar online los 2 procesos:
echo ============================================================
%PM2% list
echo.
echo Si ves 'protecta-scraper' y 'wa-bridge' en estado 'online',
echo el flujo de auto-arranque post-reboot funciona OK.
echo.
echo Revisa healthchecks.io en 1-2 min: ambos checks deben volver a verde.
echo.

pause
endlocal
