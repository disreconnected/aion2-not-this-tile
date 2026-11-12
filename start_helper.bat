@echo off
rem Starts the Not This Tile? helper. A copy that is already running is closed first, so there is only ever one.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object CommandLine -like '*notthistile_helper*' | ForEach-Object { Stop-Process -Id $_.ProcessId }"
start "" pythonw "%~dp0notthistile_helper.py"
