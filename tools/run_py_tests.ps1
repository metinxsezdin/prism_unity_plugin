# Runs the Python unit tests with Prism's bundled interpreter.
# Prism's embedded Python has a python313._pth file, so PYTHONPATH is ignored;
# the search paths are inserted explicitly before unittest discovery runs.
# Usage: tools/run_py_tests.ps1 [-Pattern "test_*.py"]
param([string]$Pattern = "test_*.py")
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = if ($env:PRISM_UNITY_PYTHON) { $env:PRISM_UNITY_PYTHON } else { "C:\Program Files\Prism2\Python313\python.exe" }
$env:PYTHONIOENCODING = "utf-8"
$env:PRISM_UNITY_REPO = $repo
$boot = "import os,sys,unittest; r=os.environ['PRISM_UNITY_REPO']; " +
        "sys.path[:0]=[os.path.join(r,'Unity','Scripts'), os.path.join(r,'tests','python')]; " +
        "suite=unittest.defaultTestLoader.discover(os.path.join(r,'tests','python'), pattern=sys.argv[1], top_level_dir=os.path.join(r,'tests','python')); " +
        "res=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(0 if res.wasSuccessful() else 1)"
# unittest reports on stderr; with "Stop" a redirected stderr line would abort this script.
$ErrorActionPreference = "Continue"
& $python -c $boot $Pattern
exit $LASTEXITCODE
