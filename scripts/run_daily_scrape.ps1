
param(
  [string]$Mode = "python",   # "python" o "exe"
  [string]$ProjectRoot = ""
)

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $ProjectRoot = (Resolve-Path ".").Path
}

Set-Location $ProjectRoot

$logDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("daily_scrape_" + (Get-Date -Format "yyyyMMdd") + ".log")

"==== Valyro daily_scrape START $(Get-Date -Format o) ====" | Out-File -FilePath $logFile -Append -Encoding utf8

try {
  if ($Mode -eq "exe") {
    $exePath = Join-Path $ProjectRoot "valyro.exe"
    if (!(Test-Path $exePath)) { throw "No existe: $exePath" }

    & $exePath --daily-scrape --headless 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
    $exitCode = $LASTEXITCODE
  }
  else {
    $venvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
      $py = $venvPy
    } else {
      $pyCmd = Get-Command python -ErrorAction SilentlyContinue
      if (!$pyCmd) { throw "No encuentro python (ni .venv\Scripts\python.exe ni python en PATH)" }
      $py = $pyCmd.Source
    }

    & $py -m scripts.daily_scrape 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
    $exitCode = $LASTEXITCODE
  }

  "==== Valyro daily_scrape END $(Get-Date -Format o) exit=$exitCode ====" | Out-File -FilePath $logFile -Append -Encoding utf8
  exit $exitCode
}
catch {
  "==== Valyro daily_scrape CRASH $(Get-Date -Format o) ====" | Out-File -FilePath $logFile -Append -Encoding utf8
  $_ | Out-File -FilePath $logFile -Append -Encoding utf8
  exit 99
}
