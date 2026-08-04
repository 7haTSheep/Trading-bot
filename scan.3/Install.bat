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

echo  [1/4] Checking Python...
where python >nul 2>&1
if errorlevel 1 goto :nopython

REM Found a Python, but MetaTrader5 has no 32-bit wheel. An x86 Python here
REM would install fine and then fail at pip, so check the build before
REM accepting it and offer to fetch a 64-bit one if it is wrong.
python -c "import sys; sys.exit(0 if sys.maxsize > 2**32 else 1)" >nul 2>&1
if not errorlevel 1 goto :havepython

echo        the Python on PATH is 32-bit; MetaTrader5 needs 64-bit
if exist "%PYDIR%\python.exe" (
    "%PYDIR%\python.exe" -c "import sys; sys.exit(0 if sys.maxsize > 2**32 else 1)" >nul 2>&1
    if not errorlevel 1 (
        echo        using the 64-bit Python already at %PYDIR%
        set "PATH=%PYDIR%;%PYDIR%\Scripts;%PATH%"
        goto :havepython
    )
)
echo        a 64-bit Python will be installed alongside it
echo        ^(the 32-bit one is left untouched^)
goto :getpython

:nopython
REM Python may be installed but absent from PATH; use it before downloading.
if exist "%PYDIR%\python.exe" (
    echo        found Python at %PYDIR% but not on PATH, using it
    set "PATH=%PYDIR%;%PYDIR%\Scripts;%PATH%"
    goto :havepython
)

echo.
echo        Python was not found on this PC.

:getpython
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
echo  [2/4] Installing Python packages...
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

REM --- 3. MetaTrader 5 ---------------------------------------------
REM  A terminal data folder only appears once MT5 has been run and logged
REM  in, so its presence is the real test of "ready", not the .exe.
echo.
echo  [3/4] Checking MetaTrader 5...
set TERMROOT=%APPDATA%\MetaQuotes\Terminal
set MT5READY=0
if exist "%TERMROOT%" (
    for /d %%T in ("%TERMROOT%\*") do (
        if exist "%%T\MQL5\Indicators" set MT5READY=1
    )
)
if !MT5READY!==1 (
    echo        found and already initialised
    goto :mql5files
)

REM Installed but never launched: the data folder does not exist yet.
set "MT5EXE="
for /d %%D in ("%ProgramFiles%\*MetaTrader*" "%ProgramFiles%\*MT5*") do (
    if exist "%%D\terminal64.exe" set "MT5EXE=%%D\terminal64.exe"
)
if defined MT5EXE (
    echo        MetaTrader 5 is installed but has not been run yet.
    echo        Starting it now - log in to your account, then close this
    echo        window and run Install.bat again to copy the MQL5 files.
    start "" "!MT5EXE!"
    echo.
    pause
    exit /b 0
)

echo        MetaTrader 5 was not found on this PC.
echo.
echo          [1] Deriv MT5      - pre-configured with Deriv's servers,
echo                               needed for the Volatility indices
echo          [2] MetaQuotes MT5 - generic build, any broker, but you must
echo                               add the server manually
echo          [3] Skip
echo.
set /p MT5CHOICE="        Which build? [1/2/3] "

if "!MT5CHOICE!"=="3" goto :mql5files
if "!MT5CHOICE!"=="1" set MT5URL=https://download.mql5.com/cdn/web/deriv.com.limited/mt5/deriv5setup.exe
if "!MT5CHOICE!"=="2" set MT5URL=https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe
if not defined MT5URL (
    echo        No choice made, skipping MetaTrader 5.
    goto :mql5files
)

set MT5SETUP=%TEMP%\mt5setup.exe
echo        downloading installer...
curl -L --fail --silent --show-error -o "!MT5SETUP!" "!MT5URL!"
if errorlevel 1 (
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '!MT5URL!' -OutFile '!MT5SETUP!' -UseBasicParsing } catch { exit 1 }"
    if errorlevel 1 (
        echo        ERROR: download failed. Install MetaTrader 5 manually.
        goto :mql5files
    )
)
echo        launching the MetaTrader 5 installer...
echo        Complete the wizard, then log in to your account.
start /wait "" "!MT5SETUP!"
del "!MT5SETUP!" >nul 2>&1
echo.
echo        Once MetaTrader 5 has been run and logged in, run Install.bat
echo        again so the MQL5 files can be copied into its data folder.
echo.
pause
exit /b 0

REM --- 4. MQL5 files -----------------------------------------------
:mql5files
echo.
echo  [4/4] Copying MQL5 files into MetaTrader terminals...
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
