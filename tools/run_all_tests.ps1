# Runs the Python unit tests and the Unity EditMode tests (E2E excluded unless -E2E).
# Usage: tools/run_all_tests.ps1 [-E2E]
param([switch]$E2E)
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "run_py_tests.ps1") *> $null
$py = $LASTEXITCODE
Write-Host ("python: " + $(if ($py -eq 0) { "OK" } else { "FAILED (run tools/run_py_tests.ps1 for details)" }))
& (Join-Path $PSScriptRoot "run_unity_tests.ps1")
$unity = $LASTEXITCODE
$e2e = 0
if ($E2E) {
    & (Join-Path $PSScriptRoot "run_unity_tests.ps1") -Category E2E
    $e2e = $LASTEXITCODE
}
if ($py -ne 0 -or $unity -ne 0 -or $e2e -ne 0) { exit 1 }
exit 0
