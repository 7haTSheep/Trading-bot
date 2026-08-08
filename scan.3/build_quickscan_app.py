"""Builds QuickScan.exe, a standalone Windows application.

The result runs on a PC with no Python installed: PyInstaller bundles the
interpreter and every library alongside the app.

    python build_quickscan_app.py

Output lands in dist/QuickScan/. Copy that whole folder to the target PC and
run QuickScan.exe inside it. MetaTrader 5 still has to be installed and
logged in there; the app talks to a running terminal and cannot replace it.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'quickscan_app.py'

# Imported dynamically inside the worker thread, so PyInstaller's static
# analysis does not see them and would otherwise leave them out.
HIDDEN = ['MetaTrader5', 'numpy', 'quickscan', 'candle_monitor', 'chart_export',
          'outcome_tracker', 'calibration']


def main() -> int:
    if sys.platform != 'win32':
        print('This builds a Windows executable and must be run on Windows.')
        return 1
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print('PyInstaller is missing. Install it with:\n    pip install pyinstaller')
        return 1
    if not APP.exists():
        print(f'Cannot find {APP.name}')
        return 1

    for stale in ('build', 'dist'):
        path = ROOT / stale
        if path.exists():
            print(f'removing old {stale}/')
            shutil.rmtree(path, ignore_errors=True)

    command = [
        sys.executable, '-m', 'PyInstaller',
        '--name=QuickScan',
        '--noconfirm',
        '--clean',
        # A folder build starts noticeably faster than one-file, which has to
        # unpack itself to a temp directory on every launch.
        '--onedir',
        # No console window behind the GUI. The app shows scanner output in
        # its own pane, so a second black window would only confuse.
        '--windowed',
        f'--paths={ROOT}',
    ]
    for module in HIDDEN:
        command.append(f'--hidden-import={module}')
    # The scanner modules are imported at runtime; ship the sources too so a
    # traceback in the bundle still points at real code.
    for source in ('quickscan.py', 'candle_monitor.py', 'chart_export.py',
                   'outcome_tracker.py', 'calibration.py'):
        if (ROOT / source).exists():
            command.append(f'--add-data={ROOT / source};.')
    command.append(str(APP))

    print('building, this takes a couple of minutes...\n')
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        print('\nBuild failed. The PyInstaller output above says why.')
        return result.returncode

    target = ROOT / 'dist' / 'QuickScan' / 'QuickScan.exe'
    if not target.exists():
        print('\nBuild reported success but QuickScan.exe is not where expected.')
        return 1

    size = sum(f.stat().st_size for f in (ROOT / 'dist' / 'QuickScan').rglob('*') if f.is_file())
    print(f'\nBuilt: {target}')
    print(f'Folder size: {size / 1024 / 1024:.0f} MB')
    print('\nCopy the whole dist/QuickScan folder to the other PC and run')
    print('QuickScan.exe inside it. MetaTrader 5 must be installed and logged')
    print('in on that PC as well.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
