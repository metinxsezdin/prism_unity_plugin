# Registers this repo's Unity plugin folder with the local Prism install (development mode).
# Adds <repo>\Unity to %USERPROFILE%\Documents\Prism2\PluginPaths.json once, after backing the file up.
# Usage: tools/deploy_dev.ps1 [-Remove]
param([switch]$Remove)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$pluginDir = (Resolve-Path (Join-Path $repo "Unity")).Path
$cfg = Join-Path $env:USERPROFILE "Documents\Prism2\PluginPaths.json"
if (-not (Test-Path $cfg)) { throw "Prism plugin config not found: $cfg" }

Copy-Item $cfg "$cfg.bak" -Force
$python = "C:\Program Files\Prism2\Python313\python.exe"
$code = @'
import json, os, sys
cfg, plugin, remove = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
with open(cfg, encoding="utf-8") as f:
    data = json.load(f)
plugins = data.setdefault("plugins", [])
norm = lambda p: os.path.normcase(os.path.abspath(p))
others = [p for p in plugins if norm(p.get("path", "")) != norm(plugin)]
if not remove:
    others.append({"path": plugin})
data["plugins"] = others
with open(cfg, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)
print(("removed " if remove else "registered ") + plugin)
'@
& $python -c $code $cfg $pluginDir $(if ($Remove) { "1" } else { "0" })
exit $LASTEXITCODE
