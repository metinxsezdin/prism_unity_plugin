@echo off
rem Sets this machine up for Prism: the Unity plugin and the Prism MCP for Claude Code. Safe to run again.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install.ps1" %*
exit /b %errorlevel%
