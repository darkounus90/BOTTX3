@echo off
setlocal enabledelayedexpansion

set "PY_EXE="
echo Mocking where python...

:: Simulate where python returning WindowsApps
for %%I in ("C:\Users\PC\AppData\Local\Microsoft\WindowsApps\python.exe") do (
    set "tmp_py=%%~I"
    echo TEMP: !tmp_py!
    echo REPLACED: !tmp_py:WindowsApps=!
    if "!tmp_py:WindowsApps=!"=="!tmp_py!" (
        echo IT EQUALS! Setting PY_EXE
        if not defined PY_EXE set "PY_EXE=%%~I"
    ) else (
        echo IT DOES NOT EQUAL! Ignoring...
    )
)

echo FINAL PY_EXE: "%PY_EXE%"
