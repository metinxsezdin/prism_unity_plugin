# Sets this machine up for the Prism integration (run through Install.bat / Uninstall.bat).
#   1. Registers the Unity plugin (this repo's Unity folder) with Prism.
#   2. Adds the Prism MCP server to Claude Code, for this Windows user.
#   3. Checks that the Prism MCP can start Prism and read the user and projects.
# Safe to run again after a git pull; -Remove undoes steps 1 and 2.
# Usage: tools\install.ps1 [-Remove] [-PrismRoot <folder>] [-NoPause] [-SkipCheck]
param([switch]$Remove, [string]$PrismRoot = "", [switch]$NoPause, [switch]$SkipCheck)

# Native commands write to stderr; with "Stop", PowerShell 5.1 would turn that into an error. Exit codes are checked instead.
$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
$done = if ($Remove) { "Uninstall complete." } else { "Install complete." }

function Finish([int]$code, [string]$message) {
    Write-Host ""
    Write-Host $message
    if (-not $NoPause) { [void](Read-Host "Press Enter to close") }
    exit $code
}

function Test-PrismRoot([string]$root) {
    return $root -and (Test-Path (Join-Path $root "Python313\python.exe")) -and (Test-Path (Join-Path $root "Scripts\PrismCore.py"))
}

# --- Prism ---------------------------------------------------------------------------------
if (-not $PrismRoot) { $PrismRoot = if ($env:PRISM_ROOT) { $env:PRISM_ROOT } else { "C:\Program Files\Prism2" } }
if (-not (Test-PrismRoot $PrismRoot)) {
    if ($NoPause) { Finish 1 "Prism was not found at $PrismRoot. Run again with -PrismRoot <the Prism folder>." }
    $PrismRoot = Read-Host "Prism was not found at $PrismRoot. Enter the Prism folder (the one with Prism.exe)"
    if (-not (Test-PrismRoot $PrismRoot)) { Finish 1 "Prism was not found at $PrismRoot." }
}
$python = Join-Path $PrismRoot "Python313\python.exe"
$server = Join-Path $repo "PrismMcp\server.py"
Write-Host "Prism: $PrismRoot"

# --- 1. Unity plugin -> Prism -----------------------------------------------------------------
$cfg = Join-Path $env:USERPROFILE "Documents\Prism2\PluginPaths.json"
if (Test-Path $cfg) {
    if (-not (Test-Path "$cfg.bak")) { Copy-Item $cfg "$cfg.bak" }  # keep the first, pre-install copy
    $action = if ($Remove) { "remove" } else { "add" }
    & $python (Join-Path $PSScriptRoot "plugin_paths.py") $cfg (Join-Path $repo "Unity") $action
    if ($LASTEXITCODE -ne 0) { Finish 1 "Could not update $cfg." }
    if (-not $Remove) { Write-Host "Restart Prism (tray icon > Exit, then start it) so it loads the Unity plugin." }
} elseif (-not $Remove) {
    Finish 1 "Prism's settings ($cfg) were not found. Start Prism once, then run Install.bat again."
}

# --- 2. Prism MCP -> Claude Code -------------------------------------------------------------
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "Claude Code not found; install it and run Install.bat again."
} else {
    & claude mcp remove prism --scope user 2>&1 | Out-Null  # no entry yet is fine
    if (-not $Remove) {
        & claude mcp add prism --scope user -e "PRISM_ROOT=$PrismRoot" -- $python $server
        if ($LASTEXITCODE -ne 0) { Finish 1 "Could not add the Prism MCP to Claude Code." }
        Write-Host "Prism MCP added to Claude Code. Restart Claude Code sessions to see the Prism tools."
    } else {
        Write-Host "Prism MCP removed from Claude Code."
    }
}

# --- 3. Check -----------------------------------------------------------------------------
if (-not $Remove -and -not $SkipCheck) {
    Write-Host "Checking that the Prism MCP can start Prism (this can take a minute)..."
    $env:PRISM_ROOT = $PrismRoot
    $result = & $python $server --check 2>$null
    $code = $LASTEXITCODE
    Write-Host ($result -join "`n")
    if ($code -ne 0) { Finish 1 "The Prism MCP is installed but cannot use Prism yet; fix the problem above and run Install.bat again." }
}

Finish 0 $done
