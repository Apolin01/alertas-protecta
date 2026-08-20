

$ErrorActionPreference = "Continue"
$root = "c:\proyectos\alertas-rss-main\alertas-rss-main"
$logs = "$root\logs"

# NO seteamos WA_DATA_PATH: el bridge usa por defecto "/app" (resuelve a
# C:\app en Windows), que es donde vive la sesion de WhatsApp REAL y activa
# en esta maquina — no en $root\.wwebjs_auth. Cambiarlo rompe la sesion.

# ─────────────────────────────────────────────────────────────
# SINGLETON GUARD — evita 2 supervisores corriendo en paralelo
# ─────────────────────────────────────────────────────────────
# Mecanismo: mutex nombrado per-session (atomic, no requiere admin).
# Solo UN proceso puede tomar el mutex. Los demas abortan limpio con exit 0.
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Force -Path $logs | Out-Null }
$lockFile = "$logs\supervisor.lock"
$myPid = $PID
$supLog = "$logs\supervisor.log"

function Write-LogLine([string]$msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $supLog -Value "[$ts] $msg"
}

# Mutex atomico - el primero que llama gana, los demas abortan.
# AbandonedMutexException: el proceso anterior murio sin liberar (kill -Force).
# En ese caso tomamos ownership y continuamos.
$singletonMutex = New-Object System.Threading.Mutex($false, "AlertasProtectaSupervisor")
try {
    $gotLock = $singletonMutex.WaitOne(0)
} catch [System.Threading.AbandonedMutexException] {
    Write-LogLine "Mutex abandonado por proceso anterior - tomando ownership"
    $gotLock = $true
} catch {
    Write-LogLine "ERROR tomando mutex: $_"
    exit 1
}
if (-not $gotLock) {
    Write-LogLine "ABORTADO: mutex ocupado por otro supervisor (PID mio=$myPid)."
    exit 0
}

# Escribir lock file con mi PID (para inspeccion humana)
$myPid | Out-File -FilePath $lockFile -Encoding ascii -Force

# Limpieza al salir: borrar lock file (el mutex se libera solo al morir el proceso).
# Usamos $script: para que el callback de Exiting acceda a la variable.
$script:lockFileForCleanup = $lockFile
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    try { Remove-Item -Path $script:lockFileForCleanup -Force -ErrorAction SilentlyContinue } catch {}
} | Out-Null

Write-LogLine "Supervisor singleton OK (PID=$myPid)"

# Asegurar que existe la carpeta de logs
if (-not (Test-Path $logs)) {
    New-Item -ItemType Directory -Force -Path $logs | Out-Null
}

$supervisorLog = "$logs\supervisor.log"

function Write-SupervisorLog {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Message"
    Add-Content -Path $supervisorLog -Value $line
    Write-Host $line
}

function Start-Component {
    param(
        [string]$Name,
        [string]$Exe,
        [string]$Arguments,
        [string]$WorkDir
    )
    $outLog = "$logs\$Name.out.log"
    $errLog = "$logs\$Name.err.log"

    Write-SupervisorLog "Lanzando $Name (cwd=$WorkDir): $Exe $Arguments"
    $proc = Start-Process -FilePath $Exe `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -PassThru
    return $proc
}

# ─────────────────────────────────────────────────────────────
# GUARD adicional: detectar mains o bridges huerfanos
# ─────────────────────────────────────────────────────────────
# Aunque el lock file evite 2 supervisores, puede haber un main.py o un
# bridge huerfano arrancado fuera del supervisor (ej. desde VS Code,
# desde otro python del sistema, etc.). Si los detectamos, los matamos
# antes de lanzar los nuestros para evitar procesamiento duplicado.
function Stop-OrphanProcesses {
    $orphanMains = Get-CimInstance Win32_Process -Filter "Name LIKE '%python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*main.py*" }
    foreach ($p in $orphanMains) {
        $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path "$logs\supervisor.log" -Value "[$ts] Matando main.py huerfano PID $($p.ProcessId): $($p.CommandLine.Substring(0, [Math]::Min($p.CommandLine.Length, 100)))"
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    # Start-Process lanza node con cwd=whatsapp_bridge pero el CommandLine solo
    # muestra "node server.js" (sin la carpeta) — filtrar tambien por carpeta
    # hace que nunca matcheara y el puerto 3000 quedaba atascado con un
    # bridge huerfano para siempre. Alcanza con "server.js" a secas.
    $orphanBridges = Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*server.js*" }
    foreach ($p in $orphanBridges) {
        $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path "$logs\supervisor.log" -Value "[$ts] Matando bridge huerfano PID $($p.ProcessId)"
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if ($orphanMains -or $orphanBridges) { Start-Sleep -Seconds 3 }
}
Stop-OrphanProcesses

# ngrok se maneja MANUALMENTE fuera de este supervisor (deliberado): la URL
# publica de ngrok esta registrada en los 6 webhooks de rss.app, y el plan
# gratis genera una URL nueva cada vez que se lanza un tunel. Si el supervisor
# lanzara su propio ngrok en cada reinicio (como hacia antes de este cambio),
# generaria una URL distinta a la registrada en rss.app en cada reinicio de
# main.py/bridge — y este sistema se reinicia muy seguido. Por eso queda
# forzado a false aqui: ngrok se lanza una sola vez a mano y sobrevive a los
# reinicios de main.py/bridge sin verse afectado.
$ngrokAvailable = $false

Write-SupervisorLog "===== Arrancando sistema autonomo ====="

# 1. WhatsApp Bridge
$bridge = Start-Component -Name "bridge" `
    -Exe "node" -Arguments "server.js" `
    -WorkDir "$root\whatsapp_bridge"

# Esperar a que el bridge se inicialice antes de lanzar main.py
Start-Sleep -Seconds 6

# 2. Sistema de Alertas (Python)
$main = Start-Component -Name "main" `
    -Exe "$root\.venv\Scripts\python.exe" -Arguments "main.py" `
    -WorkDir $root

# 3. ngrok (si esta disponible)
$ngrok = $null
if ($ngrokAvailable) {
    Start-Sleep -Seconds 3
    $ngrok = Start-Component -Name "ngrok" `
        -Exe "ngrok" -Arguments "http 5000 --log stdout" `
        -WorkDir $root
}

Write-SupervisorLog "Sistema arrancado. PIDs: bridge=$($bridge.Id) main=$($main.Id) ngrok=$(if($ngrok){$ngrok.Id}else{'N/A'})"
Write-SupervisorLog "Para ver la URL publica de ngrok: abrir http://localhost:4040 en el navegador"

# Loop supervisor: chequea cada 30s que los procesos sigan vivos, reinicia los muertos
while ($true) {
    Start-Sleep -Seconds 30

    if ($bridge.HasExited) {
        Write-SupervisorLog "bridge MURIO (exit=$($bridge.ExitCode)) - reiniciando..."
        $bridge = Start-Component -Name "bridge" `
            -Exe "node" -Arguments "server.js" `
            -WorkDir "$root\whatsapp_bridge"
    }

    if ($main.HasExited) {
        Write-SupervisorLog "main MURIO (exit=$($main.ExitCode)) - reiniciando..."
        $main = Start-Component -Name "main" `
            -Exe "$root\.venv\Scripts\python.exe" -Arguments "main.py" `
            -WorkDir $root
    }

    if ($ngrokAvailable -and $ngrok -and $ngrok.HasExited) {
        Write-SupervisorLog "ngrok MURIO (exit=$($ngrok.ExitCode)) - reiniciando..."
        $ngrok = Start-Component -Name "ngrok" `
            -Exe "ngrok" -Arguments "http 5000 --log stdout" `
            -WorkDir $root
    }
}
