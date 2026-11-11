# Runs Unity EditMode tests for TestProject in batch mode and prints a summary.
# Usage: tools/run_unity_tests.ps1 [-Filter Name] [-Category Cat]
param([string]$Filter = "", [string]$Category = "")
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$unity = if ($env:PRISM_UNITY_EDITOR) { $env:PRISM_UNITY_EDITOR } else { "C:\Program Files\Unity\Hub\Editor\6000.5.6f1\Editor\Unity.exe" }
$results = Join-Path $repo "TestResults"
New-Item -ItemType Directory -Force $results | Out-Null
$xml = Join-Path $results "editmode.xml"
$log = Join-Path $results "editmode.log"
if (Test-Path $xml) { Remove-Item $xml -Force }
$uargs = @("-batchmode", "-projectPath", (Join-Path $repo "TestProject"), "-runTests", "-testPlatform", "EditMode",
          "-testResults", $xml, "-logFile", $log)
if ($Filter) { $uargs += @("-testFilter", $Filter) }
if ($Category) { $uargs += @("-testCategory", $Category) } else { $uargs += @("-testCategory", "!E2E") }
$p = Start-Process -FilePath $unity -ArgumentList $uargs -Wait -PassThru -NoNewWindow
if (-not (Test-Path $xml)) {
    Write-Host "No test results written (exit $($p.ExitCode)). Last log lines:"
    Get-Content $log -Tail 40
    exit 2
}
[xml]$doc = Get-Content $xml
$run = $doc.'test-run'
Write-Host ("total={0} passed={1} failed={2} skipped={3} result={4}" -f $run.total, $run.passed, $run.failed, $run.skipped, $run.result)
foreach ($tc in $doc.SelectNodes("//test-case[@result='Failed']")) {
    Write-Host ("FAILED: {0}" -f $tc.fullname)
    Write-Host ("  " + ($tc.failure.message.'#cdata-section' -replace "`n", "`n  "))
}
if ([int]$run.failed -gt 0 -or $run.result -notlike "Passed*") { exit 1 }
exit 0
