@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys, tkinter; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
    if not errorlevel 1 (
        py -3 -m rr2dv.gui %*
        goto result
    )
)
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys, tkinter; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
    if not errorlevel 1 (
        python -m rr2dv.gui %*
        goto result
    )
)
echo Python 3.11 or newer with Tk is required for this source download.
echo Install Python from python.org with Tcl/Tk, or use the Windows .exe download.
pause
exit /b 1

:result
if errorlevel 1 (
    echo.
    echo Derailroader stopped with an error shown above.
    pause
    exit /b 1
)
exit /b 0
