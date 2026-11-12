@echo off
rem Removes the Unity plugin from Prism and the Prism MCP from Claude Code.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install.ps1" -Remove %*
exit /b %errorlevel%
