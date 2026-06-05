@echo off
setlocal enabledelayedexpansion

set "PY_EXE="

echo --- STEP 1 ---
for /d %%V in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%V\python.exe" (
        set "PY_EXE=%%V\python.exe"
        echo MATCHED IN STEP 1A: !PY_EXE!
    )
)
if not defined PY_EXE (
    for /d %%U in ("C:\Users\*") do (
        for /d %%V in ("%%U\AppData\Local\Programs\Python\Python*") do (
            if exist "%%V\python.exe" (
                set "PY_EXE=%%V\python.exe"
                echo MATCHED IN STEP 1B: !PY_EXE!
            )
        )
    )
)
if not defined PY_EXE (
    for /d %%V in ("C:\Program Files\Python*") do (
        if exist "%%V\python.exe" (
            set "PY_EXE=%%V\python.exe"
            echo MATCHED IN STEP 1C: !PY_EXE!
        )
    )
)
if not defined PY_EXE (
    for /d %%V in ("C:\Program Files (x86)\Python*") do (
        if exist "%%V\python.exe" (
            set "PY_EXE=%%V\python.exe"
            echo MATCHED IN STEP 1D: !PY_EXE!
        )
    )
)

echo --- STEP 2 ---
if not defined PY_EXE (
    for /f "delims=" %%I in ('where python 2^>nul') do (
        set "tmp_py=%%I"
        if "!tmp_py:WindowsApps=!"=="!tmp_py!" (
            if not defined PY_EXE (
                set "PY_EXE=%%I"
                echo MATCHED IN STEP 2A: !PY_EXE!
            )
        )
    )
)
if not defined PY_EXE (
    for /f "delims=" %%I in ('where py 2^>nul') do (
        set "tmp_py=%%I"
        if "!tmp_py:WindowsApps=!"=="!tmp_py!" (
            if not defined PY_EXE (
                set "PY_EXE=%%I"
                echo MATCHED IN STEP 2B: !PY_EXE!
            )
        )
    )
)

echo --- FINAL ---
echo PY_EXE IS: !PY_EXE!
