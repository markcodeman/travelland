# Start the app, run the Playwright smoke test, and then stop the app
# Usage: .\scripts\run_smoke.ps1

$cwd = Get-Location
$python = Join-Path $cwd '.venv\Scripts\python.exe'
$app = Join-Path $cwd 'app.py'
$test = Join-Path $cwd 'tests\playwright_local_smoke.py'

if (-Not (Test-Path $python)) { Write-Error "Python executable not found at $python"; exit 2 }
if (-Not (Test-Path $app)) { Write-Error "App not found at $app"; exit 2 }
if (-Not (Test-Path $test)) { Write-Error "Smoke test not found at $test"; exit 2 }

Write-Host "Starting app using: $python $app"
$proc = Start-Process -FilePath $python -ArgumentList $app -WorkingDirectory $cwd -PassThru
Start-Sleep -Seconds 2

try {
    Write-Host "Running smoke test..."
    & $python $test 2>&1 | Tee-Object -Variable out
    Write-Host "Smoke test finished. Output:"; Write-Host $out
} catch {
    Write-Error "Smoke test failed: $_"
} finally {
    if ($proc -and $proc.Id) {
        Write-Host "Stopping app (PID $($proc.Id))"
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}
