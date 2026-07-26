"""
app.py — Primary Entry Point for MT5 Institutional Terminal.

Initialises PySide6 QApplication, applies dark QSS theme, loads fonts,
creates MainWindow, and launches Qt event loop.
"""
from __future__ import annotations
import sys
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from App.Services.LogService import log_service
from App.UI.MainWindow import MainWindow

# Ensure root directory is on sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> None:
    # Initialise rotating loggers
    log_service.initialise(level='INFO')
    log = log_service.get('app')
    log.info('Starting MT5 Institutional Terminal v2.0.0')

    # Enable High-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName('MT5 Institutional Terminal')
    app.setOrganizationName('Antigravity Trading')

    # Load QSS theme
    theme_path = ROOT_DIR / 'App' / 'Resources' / 'Themes' / 'dark.qss'
    if theme_path.exists():
        with open(theme_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
        log.info('Dark QSS theme loaded successfully')
    else:
        log.warning('Theme file not found at %s', theme_path)

    # Instantiate MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
