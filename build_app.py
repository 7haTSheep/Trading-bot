"""
build_app.py — PyInstaller build script for MT5 Institutional Terminal.

Bundles the application into a standalone Windows executable directory under dist/MT5_Terminal/
or single executable under dist/MT5_Terminal.exe.
"""
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def build():
    print("Building MT5 Terminal Windows Standalone Executable...")
    
    # Target entry point
    entry_point = ROOT / "mt5_terminal" / "app.py"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=MT5_Institutional_Terminal",
        "--noconfirm",
        "--onedir",  # Folder build for fast startup
        "--windowed", # Hide console window
        f"--add-data={ROOT / 'quickscan.py'};.",
        f"--add-data={ROOT / 'mt5_terminal' / 'App' / 'Resources' / 'Themes'};App/Resources/Themes",
        f"--add-data={ROOT / 'mt5_terminal' / 'Configs'};Configs",
        f"--paths={ROOT}",
        f"--paths={ROOT / 'mt5_terminal'}",
        str(entry_point)
    ]
    
    print("Running PyInstaller command:")
    print(" ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\nSUCCESS! Standalone Windows Application created at:")
        print(f"  {ROOT / 'dist' / 'MT5_Institutional_Terminal' / 'MT5_Institutional_Terminal.exe'}")
    else:
        print("\nBuild failed with exit code:", res.returncode)

if __name__ == "__main__":
    build()
