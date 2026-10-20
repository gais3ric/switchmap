# Симулятор SNMP для проверок в GitHub Actions (Windows). Запускать в том же шаге, где идёт проверка:
# процессы, запущенные в фоне, GitHub завершает в конце каждого шага.
$ErrorActionPreference = 'Stop'
if (-not (Test-Path sim\Scripts\snmpsim-command-responder.exe)) {
    python -m venv sim
    sim\Scripts\pip install -q snmpsim pysmi cryptography
}
# полные пути: с относительным путём к данным snmpsim на Windows не создаёт индекс
$data = (Resolve-Path tests\snmpsim\data).Path
$simArgs = "--data-dir=$data", "--cache-dir=$env:RUNNER_TEMP\snmpcache", "--agent-udpv4-endpoint=127.0.0.1:161",
           "--v3-user=simuser", "--v3-auth-key=authpass123", "--v3-auth-proto=SHA", "--v3-priv-key=privpass123", "--v3-priv-proto=AES"
Start-Process sim\Scripts\snmpsim-command-responder.exe -ArgumentList $simArgs -WindowStyle Hidden `
    -RedirectStandardOutput "$env:RUNNER_TEMP\sim.log" -RedirectStandardError "$env:RUNNER_TEMP\sim.err"
for ($i = 0; $i -lt 90 -and -not (Get-NetUDPEndpoint -LocalPort 161 -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
Start-Sleep 3
if (-not (Get-NetUDPEndpoint -LocalPort 161 -ErrorAction SilentlyContinue)) {
    Get-Content "$env:RUNNER_TEMP\sim.log", "$env:RUNNER_TEMP\sim.err" -Tail 30
    throw "Симулятор SNMP не запустился"
}
