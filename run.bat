@echo off
rem Haft Almas launcher. No cd to the program folder, so it also works from a UNC share.
if not exist "%~dp0main.py" goto missing
where py >nul 2>nul
if errorlevel 1 goto trypython
py -3 "%~dp0main.py"
goto done
:trypython
where python >nul 2>nul
if errorlevel 1 goto nopython
python "%~dp0main.py"
goto done
:nopython
echo Python 3.5 or newer was not found. Install it from python.org and tick "tcl/tk and IDLE".
pause
exit /b 1
:missing
echo main.py was not found next to run.bat.
echo Expected: %~dp0main.py
echo Copy the whole HaftAlmas folder, do not copy run.bat alone.
pause
exit /b 1
:done
if errorlevel 1 pause
