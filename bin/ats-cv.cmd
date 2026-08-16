@echo off
setlocal
if defined CLAUDE_PLUGIN_ROOT (
  set "PLUGIN_ROOT=%CLAUDE_PLUGIN_ROOT%"
) else (
  set "PLUGIN_ROOT=%~dp0.."
)
py "%PLUGIN_ROOT%\.agents\skills\tailor-cv\scripts\run_cli.py" -- %*
exit /b %ERRORLEVEL%
