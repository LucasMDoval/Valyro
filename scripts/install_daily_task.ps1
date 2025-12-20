param(
  [Parameter(Mandatory=$true)]
  [string]$Time,              # "09:30"
  [string]$Mode = "python",   # "python" ahora, "exe" luego
  [string]$TaskBase = "Valyro - Daily Scrape",
  [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $ProjectRoot = (Resolve-Path ".").Path
}

$runner = Join-Path $ProjectRoot "scripts\run_daily_scrape.ps1"
if (!(Test-Path $runner)) { throw "No existe: $runner" }

# comando que ejecutará la tarea
$taskCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Mode $Mode -ProjectRoot `"$ProjectRoot`""

$taskDaily  = "$TaskBase (Daily)"
$taskLogon  = "$TaskBase (OnLogon)"

# 1) Tarea diaria
schtasks /Create /F /TN "$taskDaily" /SC DAILY /ST $Time /TR "$taskCmd" /RL LIMITED | Out-Null

# 2) Tarea al iniciar sesión (catch-up si el PC estaba apagado)
schtasks /Create /F /TN "$taskLogon" /SC ONLOGON /TR "$taskCmd" /RL LIMITED | Out-Null

# Verifica que existen
schtasks /Query /TN "$taskDaily" | Out-Null
schtasks /Query /TN "$taskLogon" | Out-Null

Write-Host "OK. Tareas instaladas/actualizadas:"
Write-Host " - $taskDaily a las $Time"
Write-Host " - $taskLogon al iniciar sesión"
Write-Host "Runner: $runner"
Write-Host "Logs: $ProjectRoot\logs\daily_scrape_YYYYMMDD.log"
