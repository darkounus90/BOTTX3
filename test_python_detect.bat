@echo off
setlocal enabledelayedexpansion
set "PY_EXE="
for /d %%V in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
)
echo Step 1: %PY_EXE%

if not defined PY_EXE (
    for /f "delims=" %%I in ('where python 2^>nul') do (
        echo %%I | find /i "WindowsApps" >nul
        if errorlevel 1 (
            if not defined PY_EXE set "PY_EXE=%%I"
        )
    )
)
echo Step 2: %PY_EXE%
