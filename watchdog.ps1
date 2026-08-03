# watchdog.ps1 — Revisa que el Sistema de Alertas (Python) y el WhatsApp
# Bridge (Node) sigan vivos y respondiendo. Si alguno murio, o si
# alertas.log dejo de actualizarse (proceso colgado sin morir — ej. el
# incidente de DNS del 28-07-26), mata lo que quede y reinicia todo via
# iniciar_sistema.vbs.
#
# Pensado para correr cada 5 min desde el Programador de tareas de Windows
# (tarea "AlertasProtecta - Watchdog").

$ErrorActionPreference = "SilentlyContinue"

$raiz = $PSScriptRoot
$logPath = Join-Path $raiz "alertas.log"
$iniciar = Join-Path $raiz "iniciar_sistema.vbs"
$watchdogLog = Join-Path $raiz "logs\watchdog.log"

function Log($msg) {
    $linea = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $watchdogLog -Value $linea -Encoding utf8
}

# ── Chequeo 1: proceso Python de main.py vivo? ──
$pyVivo = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -match 'main\.py' }

# ── Chequeo 2: proceso Node del bridge vivo? ──
$nodeVivo = Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" |
    Where-Object { $_.CommandLine -match 'server\.js' }

# ── Chequeo 3: alertas.log se sigue actualizando? (detecta procesos colgados) ──
$logFresco = $true
if (Test-Path $logPath) {
    $ultimaEscritura = (Get-Item $logPath).LastWriteTime
    $minutosSinEscribir = ((Get-Date) - $ultimaEscritura).TotalMinutes
    if ($minutosSinEscribir -gt 15) {
        $logFresco = $false
        Log "alertas.log sin actualizarse hace $([math]::Round($minutosSinEscribir,1)) min"
    }
}

$necesitaReinicio = (-not $pyVivo) -or (-not $nodeVivo) -or (-not $logFresco)

if ($necesitaReinicio) {
    $razon = @()
    if (-not $pyVivo)    { $razon += "python.exe (main.py) no esta corriendo" }
    if (-not $nodeVivo)  { $razon += "node.exe (bridge) no esta corriendo" }
    if (-not $logFresco) { $razon += "alertas.log parece colgado" }
    Log "REINICIANDO — motivo: $($razon -join '; ')"

    # Matar lo que haya quedado a medias
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match 'main\.py' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
    Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" |
        Where-Object { $_.CommandLine -match 'server\.js' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }

    Start-Sleep -Seconds 3

    # Relanzar todo (el .vbs se encarga de bridge + main.py)
    Start-Process "wscript.exe" -ArgumentList "`"$iniciar`"" -WindowStyle Hidden
    Log "Relanzado via iniciar_sistema.vbs"
} else {
    Log "OK — python vivo, node vivo, log activo"
}

