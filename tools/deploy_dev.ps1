# Registers this repo's Unity plugin folder with the local Prism install (development mode).
# Adds <repo>\Unity to %USERPROFILE%\Documents\Prism2\PluginPaths.json once, after backing the file up.
# Usage: tools/deploy_dev.ps1 [-Remove]
param([switch]$Remove)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$pluginDir = (Resolve-Path (Join-Path $repo "Unity")).Path
$cfg = Join-Path $env:USERPROFILE "Documents\Prism2\PluginPaths.json"
if (-not (Test-Path $cfg)) { throw "Prism plugin config not found: $cfg" }

if (-not (Test-Path "$cfg.bak")) { Copy-Item $cfg "$cfg.bak" }  # keep the first, pre-deploy backup
$python = "C:\Program Files\Prism2\Python313\python.exe"
$action = if ($Remove) { "remove" } else { "add" }
& $python (Join-Path $PSScriptRoot "plugin_paths.py") $cfg $pluginDir $action
exit $LASTEXITCODE
