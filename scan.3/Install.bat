@echo off
REM ===================================================================
REM  Install.bat - sets up QuickScan on a Windows machine.
REM
REM  Installs the Python packages the scanner needs and copies the MQL5
REM  indicator and EA into every MetaTrader 5 terminal found on this
REM  machine. It cannot compile them: MetaEditor has to do that, so the
REM  final step is manual and is printed at the end.
REM
REM  Safe to re-run; it overwrites the .mq5 sources and reinstalls.
REM ===================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo  ================================================
echo   QuickScan installer
echo  ================================================
echo.

REM --- 1. Python ---------------------------------------------------
REM  MetaTrader5 is a Windows-only wheel and needs 64-bit Python, so the
REM  amd64 build is fetched deliberately rather than whatever is default.
set PYVERSION=3.12.10
set PYURL=https://www.python.org/ftp/python/%PYVERSION%/python-%PYVERSION%-amd64.exe
set PYDIR=%LOCALAPPDATA%\Programs\Python\Python312

echo  [1/3] Checking Python...
where python >nul 2>&1
if not errorlevel 1 goto :havepython

REM Python may be installed but absent from PATH; use it before downloading.
if exist "%PYDIR%\python.exe" (
    echo        found Python at %PYDIR% but not on PATH, using it
    set "PATH=%PYDIR%;%PYDIR%\Scripts;%PATH%"
    goto :havepython
)

echo.
echo        Python was not found on this PC.
echo        This will download Python %PYVERSION% (about 25 MB) from
echo        https://www.python.org and install it for the current user.
echo        No administrator rights are needed and nothing else is changed.
echo.
set /p GETPY="        Download and install Python now? [y/N] "
if /i not "!GETPY!"=="y" (
    echo.
    echo        Skipped. Install Python 3.10 or newer yourself from
    echo        https://www.python.org/downloads/ , tick "Add python.exe to
    echo        PATH" during setup, then re-run this script.
    echo.
    pause
    exit /b 1
)

set PYEXE=%TEMP%\python-%PYVERSION%-amd64.exe
echo        downloading...
curl -L --fail --silent --show-error -o "%PYEXE%" "%PYURL%"
if errorlevel 1 (
    REM curl ships with Windows 10 1803 and later; fall back for older builds.
    echo        curl failed, trying PowerShell...
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%PYURL%' -OutFile '%PYEXE%' -UseBasicParsing } catch { exit 1 }"
    if errorlevel 1 (
        echo.
        echo  ERROR: could not download Python. Check the internet connection,
        echo  or install it manually from https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
)
if not exist "%PYEXE%" (
    echo  ERROR: download did not produce a file.
    pause
    exit /b 1
)

echo        installing (this takes a minute, a progress window may appear)...
REM PrependPath only affects new shells, so PATH is also set below for this one.
"%PYEXE%" /passive InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
set "PATH=%PYDIR%;%PYDIR%\Scripts;%PATH%"
del "%PYEXE%" >nul 2>&1

where python >nul 2>&1
if errorlevel 1 (
    if not exist "%PYDIR%\python.exe" (
        echo.
        echo  ERROR: Python still not found after install. Close this window,
        echo  open a new one and re-run, or install manually from python.org
        echo.
        pause
        exit /b 1
    )
)

:havepython
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo        using Python !PYVER!

REM MetaTrader5 has no 32-bit wheel; catch that here rather than at pip.
python -c "import sys; sys.exit(0 if sys.maxsize > 2**32 else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: this is 32-bit Python. The MetaTrader5 package requires
    echo  64-bit. Install the amd64 build from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM --- 2. Packages -------------------------------------------------
echo.
echo  [2/3] Installing Python packages...
python -m pip install --upgrade pip --quiet
if errorlevel 1 echo        WARNING: could not upgrade pip, continuing anyway
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  ERROR: package install failed. Check the messages above.
    echo  MetaTrader5 is Windows-only and needs 64-bit Python.
    echo.
    pause
    exit /b 1
)
echo        core packages installed

echo.
set /p DESKTOP="        Also install the PySide6 desktop terminal? (large download) [y/N] "
if /i "!DESKTOP!"=="y" (
    python -m pip install -r mt5_terminal\requirements.txt
    if errorlevel 1 echo        WARNING: desktop terminal packages failed to install
)

REM --- 3. MQL5 files -----------------------------------------------
echo.
echo  [3/3] Copying MQL5 files into MetaTrader terminals...
set TERMROOT=%APPDATA%\MetaQuotes\Terminal
set FOUND=0

if not exist "%TERMROOT%" goto :noterminal

for /d %%T in ("%TERMROOT%\*") do (
    REM Only real terminal folders have an MQL5 tree; skip Common and others.
    if exist "%%T\MQL5\Indicators" (
        set /a FOUND+=1
        copy /y "MQL5\Indicators\QuickScanChart.mq5" "%%T\MQL5\Indicators\" >nul
        if not exist "%%T\MQL5\Experts" mkdir "%%T\MQL5\Experts"
        copy /y "MQL5\Experts\QuickScanEA.mq5" "%%T\MQL5\Experts\" >nul
        echo        copied to %%~nxT
    )
)

if !FOUND!==0 goto :noterminal
goto :done

:noterminal
echo.
echo        No MetaTrader 5 terminal found under:
echo          %TERMROOT%
echo        Install and run MT5 once, then re-run this script. You can also
echo        copy MQL5\Indicators\QuickScanChart.mq5 and
echo        MQL5\Experts\QuickScanEA.mq5 into the terminal by hand.

:done
echo.
echo  ================================================
echo   Installed. Remaining steps must be done by hand:
echo  ================================================
echo.
echo   1. Open MetaEditor (F4 in MT5) and compile both files:
echo        Indicators\QuickScanChart.mq5
echo        Experts\QuickScanEA.mq5
echo.
echo   2. Start the scanner, quoting any symbol containing spaces:
echo        set PYTHONIOENCODING=utf-8
echo        python quickscan.py "Volatility 10 (1s) Index" --risk 90 --stop-atr 2.0 5m
echo.
echo   3. Attach QuickScanChart to the chart of a symbol being scanned.
echo.
echo   The EA refuses to trade a live account until AllowLiveAccount is set
echo   to true in its Inputs. Leave it off and use a demo account first.
echo.
pause
endlocal
