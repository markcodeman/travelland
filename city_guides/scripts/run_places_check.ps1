# Run the Google Places one-off check using the repo venv
# Usage: .\scripts\run_places_check.ps1

$env:PWD = (Get-Location)
$venv = Join-Path $env:PWD ".venv\Scripts\python.exe"
$script = Join-Path $env:PWD "scripts\check_places.py"

Write-Host "Using python: $venv"
Write-Host "Running places check: $script"

if (-Not (Test-Path $venv)) {
    Write-Error "Python executable not found at $venv. Activate your venv or adjust the script."
    exit 2
}
if (-Not (Test-Path $script)) {
    Write-Error "Script not found: $script"
    exit 2
}

# Run the check and capture output
& $venv $script 2>&1 | Tee-Object -Variable out
$exitCode = $LASTEXITCODE
Write-Host "Exit code: $exitCode"
if ($out) { Write-Host $out }
exit $exitCode
