@echo off
REM ===================================================================
REM  Setup.bat - prepares a PC to run QuickScan.exe.
REM
REM  Ships inside the built application folder. Unlike Install.bat in the
REM  source project, this does NOT install Python or any packages: the
REM  executable already carries its own Python, and the C++ runtime that
REM  Qt and NumPy need is bundled too. What it cannot carry is MetaTrader
REM  5 and the chart files that go inside it, so that is what this does.
REM
REM  Safe to run more than once.
REM ===================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo  ==================================================
echo   QuickScan setup
echo  ==================================================
echo.

set PROBLEMS=0

REM --- 1. Windows and the application itself -----------------------
echo  [1/4] Checking the application...

if not exist "QuickScan.exe" (
    echo.
    echo  ERROR: QuickScan.exe is not next to this script.
    echo  Keep Setup.bat inside the QuickScan folder and run it from there.
    echo.
    pause
    exit /b 1
)
if not exist "_internal" (
    echo.
    echo  ERROR: the _internal folder is missing.
    echo  QuickScan needs the whole folder, not just the .exe. Copy the
    echo  entire QuickScan folder across, not the single file.
    echo.
    pause
    exit /b 1
)
if "%PROCESSOR_ARCHITECTURE%"=="x86" (
    if not defined PROCESSOR_ARCHITEW6432 (
        echo.
        echo  ERROR: this is 32-bit Windows. QuickScan and the MetaTrader
        echo  connection both need 64-bit Windows.
        echo.
        pause
        exit /b 1
    )
)
echo        application files are complete

REM --- 2. MetaTrader 5 ---------------------------------------------
echo.
echo  [2/4] Checking MetaTrader 5...

set TERMROOT=%APPDATA%\MetaQuotes\Terminal
set MT5READY=0
if exist "%TERMROOT%" (
    for /d %%T in ("%TERMROOT%\*") do (
        if exist "%%T\MQL5\Indicators" set MT5READY=1
    )
)
if !MT5READY!==1 (
    echo        found, and it has been run before
    goto :charts
)

set "MT5EXE="
for /d %%D in ("%ProgramFiles%\*MetaTrader*" "%ProgramFiles%\*MT5*") do (
    if exist "%%D\terminal64.exe" set "MT5EXE=%%D\terminal64.exe"
)
if defined MT5EXE (
    echo        MetaTrader 5 is installed but has never been opened.
    echo        Opening it now. Log in to your account, then run this
    echo        setup again so the chart files can be copied in.
    start "" "!MT5EXE!"
    echo.
    pause
    exit /b 0
)

echo        MetaTrader 5 is not installed. QuickScan reads prices from it
echo        and cannot work without it.
echo.
echo          [1] Deriv MT5      - for Deriv accounts and the Volatility
echo                               indices this tool was built around
echo          [2] MetaQuotes MT5 - generic, works with any broker, but you
echo                               add your broker's server by hand
echo          [3] Skip for now
echo.
set /p MT5CHOICE="        Which would you like? [1/2/3] "

if "!MT5CHOICE!"=="3" set PROBLEMS=1& goto :charts
if "!MT5CHOICE!"=="1" set MT5URL=https://download.mql5.com/cdn/web/deriv.com.limited/mt5/deriv5setup.exe
if "!MT5CHOICE!"=="2" set MT5URL=https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe
if not defined MT5URL set PROBLEMS=1& goto :charts

set MT5SETUP=%TEMP%\mt5setup.exe
echo        downloading MetaTrader 5...
curl -L --fail --silent --show-error -o "!MT5SETUP!" "!MT5URL!"
if errorlevel 1 (
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '!MT5URL!' -OutFile '!MT5SETUP!' -UseBasicParsing } catch { exit 1 }"
    if errorlevel 1 (
        echo        Download failed. Install MetaTrader 5 yourself, then run
        echo        this setup again.
        set PROBLEMS=1
        goto :charts
    )
)
echo        starting the MetaTrader installer - follow it, then log in
start /wait "" "!MT5SETUP!"
del "!MT5SETUP!" >nul 2>&1
echo.
echo        When MetaTrader is installed and you have logged in, run this
echo        setup again so the chart files can be copied in.
echo.
pause
exit /b 0

REM --- 3. Chart files ----------------------------------------------
:charts
echo.
echo  [3/4] Copying chart files into MetaTrader...

if not exist "MQL5" (
    echo        No MQL5 folder here, so there is nothing to copy.
    echo        Scanning will still work; the on-chart drawing will not.
    goto :shortcut
)

set COPIED=0
for /d %%T in ("%TERMROOT%\*") do (
    if exist "%%T\MQL5\Indicators" (
        if exist "MQL5\Indicators\*.mq5" copy /y "MQL5\Indicators\*.mq5" "%%T\MQL5\Indicators\" >nul
        if not exist "%%T\MQL5\Experts" mkdir "%%T\MQL5\Experts"
        if exist "MQL5\Experts\*.mq5" copy /y "MQL5\Experts\*.mq5" "%%T\MQL5\Experts\" >nul
        set /a COPIED+=1
        echo        copied into %%~nxT
    )
)
if !COPIED!==0 (
    echo        No MetaTrader data folder found yet. Open MetaTrader, log in,
    echo        then run this setup again.
    set PROBLEMS=1
)

REM --- 4. Shortcut --------------------------------------------------
:shortcut
echo.
echo  [4/4] Desktop shortcut...
set /p WANTLNK="        Create a QuickScan shortcut on the desktop? [Y/n] "
if /i "!WANTLNK!"=="n" goto :done
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\QuickScan.lnk');" ^
  "$s.TargetPath='%CD%\QuickScan.exe'; $s.WorkingDirectory='%CD%'; $s.Save()" >nul 2>&1
if errorlevel 1 (echo        could not create the shortcut) else (echo        shortcut created)

:done
echo.
echo  ==================================================
if !PROBLEMS!==0 (
    echo   Setup complete.
) else (
    echo   Setup finished, but see the notes above.
)
echo  ==================================================
echo.
echo   One step is left, and only you can do it:
echo.
echo     1. Open MetaTrader 5 and press F4 to open MetaEditor
echo     2. On the left, find QuickScanChart, QuickScanEA and
echo        QuickScanLauncher
echo     3. Click each one and press F7 to compile it
echo.
echo   Then start QuickScan.exe, press "Load symbols from MetaTrader",
echo   tick what you want to watch, and press Start.
echo.
echo   QuickScan only reads prices. It does not place trades.
echo   The trading part is separate and is off unless you turn it on.
echo.
pause
endlocal
