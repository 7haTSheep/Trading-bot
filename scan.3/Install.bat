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
echo  [1/3] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not on PATH.
    echo  Install Python 3.10 or newer from https://www.python.org/downloads/
    echo  and tick "Add python.exe to PATH" during setup, then re-run this.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo        found Python !PYVER!

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
