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
# PyInstaller writes here; the finished folder is then copied into dist/.
STAGE = ROOT / 'build' / '_stage'

# Imported dynamically inside the worker thread, so PyInstaller's static
# analysis does not see them and would otherwise leave them out.
HIDDEN = ['MetaTrader5', 'numpy', 'quickscan', 'candle_monitor', 'chart_export',
          'outcome_tracker', 'calibration', 'trades', 'theme', 'surface',
          'trades_view']


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

    # PyInstaller wipes its output directory before writing, and Windows
    # refuses to remove a directory that any process is sitting in -- an open
    # Explorer window or a shell left with it as its working directory is
    # enough, and the folder then cannot be deleted even when it is empty.
    # Building into a staging area under build/ sidesteps that: writing files
    # *into* a held directory is still allowed, so the results can be copied
    # over the top afterwards.
    if STAGE.exists():
        shutil.rmtree(STAGE, ignore_errors=True)

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
        f'--distpath={STAGE}',
    ]
    for module in HIDDEN:
        command.append(f'--hidden-import={module}')
    # The scanner modules are imported at runtime; ship the sources too so a
    # traceback in the bundle still points at real code.
    for source in ('quickscan.py', 'candle_monitor.py', 'chart_export.py',
                   'outcome_tracker.py', 'calibration.py', 'trades.py',
                   'theme.py', 'surface.py', 'trades_view.py'):
        if (ROOT / source).exists():
            command.append(f'--add-data={ROOT / source};.')
    # The bundled typefaces, and the OFL licence texts they must ship with.
    fonts = ROOT / 'assets' / 'fonts'
    if fonts.exists():
        command.append(f'--add-data={fonts};assets/fonts')
    command.append(str(APP))

    print('building, this takes a couple of minutes...\n')
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        print('\nBuild failed. The PyInstaller output above says why.')
        return result.returncode

    built = STAGE / 'QuickScan' / 'QuickScan.exe'
    if not built.exists():
        print('\nBuild reported success but QuickScan.exe is not where expected.')
        return 1

    dist_dir = ROOT / 'dist' / 'QuickScan'
    dist_dir.mkdir(parents=True, exist_ok=True)
    print(f'copying into {dist_dir}...')
    try:
        shutil.copytree(built.parent, dist_dir, dirs_exist_ok=True)
    except OSError as exc:
        print(f'\nCould not write into dist/QuickScan: {exc.strerror or exc}')
        print('Close anything using that folder (Explorer windows, a running')
        print(f'QuickScan.exe, a command prompt sitting in it). The build itself')
        print(f'succeeded and is intact at {built.parent}.')
        return 1
    shutil.rmtree(STAGE, ignore_errors=True)

    target = dist_dir / 'QuickScan.exe'

    # Ship the setup script and the chart sources inside the folder, so the
    # distributed copy can prepare a fresh PC on its own. PyInstaller bundles
    # Python and the C++ runtime, but not MetaTrader or the .mq5 files, and
    # those are what a new machine is actually missing.
    dist_dir = target.parent
    setup = ROOT / 'Setup.bat'
    if setup.exists():
        shutil.copy2(setup, dist_dir / 'Setup.bat')
        print('included Setup.bat')
    mql5 = ROOT / 'MQL5'
    if mql5.exists():
        for sub in ('Indicators', 'Experts'):
            source = mql5 / sub
            if not source.exists():
                continue
            destination = dist_dir / 'MQL5' / sub
            destination.mkdir(parents=True, exist_ok=True)
            for item in source.glob('*.mq5'):
                shutil.copy2(item, destination / item.name)
                print(f'included MQL5/{sub}/{item.name}')
    # APP_README is the one written for the packaged application. The
    # project's own README describes running from source -- Install.bat,
    # python quickscan.py -- none of which exists in this folder, so shipping
    # it would tell the user to do things they cannot do.
    readme = ROOT / 'APP_README.md'
    if not readme.exists():
        readme = ROOT / 'README.md'
    # Shipped as .txt rather than .md: Windows has no default handler for a
    # .md file, so double-clicking one on a fresh PC does nothing useful,
    # while .txt opens in Notepad. The Markdown originals stay in the
    # repository, where GitHub renders them.
    import md_to_text

    changelog = ROOT / 'CHANGELOG.md'
    for source, name in ((readme, 'README.txt'), (changelog, 'CHANGELOG.txt')):
        if source.exists():
            md_to_text.convert_file(source, dist_dir / name)
            print(f'included {source.name} as {name}')
    # A previous build shipped Markdown; leave no stale copy behind.
    for stale in ('README.md', 'CHANGELOG.md'):
        (dist_dir / stale).unlink(missing_ok=True)

    size = sum(f.stat().st_size for f in (ROOT / 'dist' / 'QuickScan').rglob('*') if f.is_file())
    print(f'\nBuilt: {target}')
    print(f'Folder size: {size / 1024 / 1024:.0f} MB')
    print('\nCopy the whole dist/QuickScan folder to the other PC, then run')
    print('Setup.bat inside it. That checks for MetaTrader, offers to install')
    print('it, and copies the chart files in. Python is already bundled.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
