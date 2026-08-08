"""Look and feel for the QuickScan window: palettes, stylesheet, textures.

Archetype: Retro-Futurism. The window is meant to read as instrumentation --
a warm near-black panel under grain and scanlines, phosphor amber as the only
interactive colour, and monospace everywhere a number appears so columns lock
instead of drifting.

Colour carries meaning and nothing else. Amber is "you can act on this",
toxic green and crimson are direction and outcome. There is no decorative
colour, which is what makes a red number mean something at a glance.

Three modes are offered -- System, Light and Dark. Light is the same
instrument printed on warm paper rather than a second design. System follows
Windows, read from the registry key Windows writes when the setting changes,
with Qt's own colour-scheme hint preferred when the installed Qt provides one.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

MODES = ('System', 'Light', 'Dark')

# Display face for headings, paired with a monospace for data. Both are
# bundled rather than borrowed from the system, so the window looks the same
# on a machine that has neither: Syne for its eccentric geometric capitals,
# JetBrains Mono because the reports are columns of figures and it was what
# the discipline app was designed against. Both are OFL licensed; the licence
# texts ship beside them.
#
# The system faces after them are fallbacks for a stripped-down build where
# the assets did not make it in.
DISPLAY_FAMILIES = ('Syne', 'Bahnschrift Condensed', 'Bahnschrift',
                    'Oswald', 'Arial Narrow')
MONO_FAMILIES = ('JetBrains Mono', 'Cascadia Mono', 'Cascadia Code',
                 'Consolas', 'DejaVu Sans Mono', 'Courier New')

_fonts_loaded = False


def load_fonts() -> list:
    """Register the bundled fonts. Must run before any stylesheet is applied.

    Returns the families that became available, which is empty when the assets
    are missing -- the family lists above then fall through to system faces
    rather than the window rendering in whatever Qt picks by default.
    """
    global _fonts_loaded
    if _fonts_loaded:
        return []
    _fonts_loaded = True

    import glob
    import os

    from PySide6.QtGui import QFontDatabase

    import paths

    loaded = []
    pattern = os.path.join(paths.resource_dir(), 'assets', 'fonts', '*.ttf')
    for path in sorted(glob.glob(pattern)):
        handle = QFontDatabase.addApplicationFont(path)
        if handle != -1:
            loaded.extend(QFontDatabase.applicationFontFamilies(handle))
    return sorted(set(loaded))


@dataclass(frozen=True)
class Palette:
    name: str
    dark: bool
    base_top: str
    base_bottom: str
    grain: int          # alpha of the noise overlay, 0-255
    scanline: int       # alpha of the horizontal rules
    card: str
    card_hover: str
    field: str
    border: str
    border_strong: str
    text: str
    text_dim: str
    text_faint: str
    accent: str
    accent_hover: str
    on_accent: str
    selection: str
    buy: str
    sell: str
    warn: str
    neutral: str


DARK = Palette(
    name='Dark',
    dark=True,
    base_top='#0B0B09',
    base_bottom='#15130F',
    grain=15,
    scanline=11,
    card='rgba(255, 255, 255, 0.030)',
    card_hover='rgba(255, 176, 0, 0.10)',
    field='rgba(0, 0, 0, 0.32)',
    border='rgba(232, 228, 217, 0.15)',
    border_strong='rgba(255, 176, 0, 0.55)',
    text='#E8E4D9',
    text_dim='#8F8879',
    text_faint='#5C5648',
    accent='#FFB000',
    accent_hover='#FFC742',
    on_accent='#0B0B09',
    selection='rgba(255, 176, 0, 0.30)',
    buy='#8FE388',
    sell='#E5484D',
    warn='#FFB000',
    neutral='#8F8879',
)

LIGHT = Palette(
    name='Light',
    dark=False,
    base_top='#F4EFE5',
    base_bottom='#E9E2D4',
    grain=11,
    scanline=7,
    card='rgba(255, 255, 255, 0.55)',
    card_hover='rgba(184, 116, 0, 0.10)',
    field='rgba(255, 255, 255, 0.72)',
    border='rgba(26, 23, 19, 0.18)',
    border_strong='rgba(184, 116, 0, 0.60)',
    text='#1A1713',
    text_dim='#5F5849',
    text_faint='#918978',
    accent='#B87400',
    accent_hover='#8F5A00',
    on_accent='#FFF8EA',
    selection='rgba(184, 116, 0, 0.22)',
    buy='#2F7D32',
    sell='#B3261E',
    warn='#B87400',
    neutral='#5F5849',
)


def windows_prefers_dark() -> Optional[bool]:
    """True/False from the Windows personalisation setting, None if unknown."""
    if sys.platform != 'win32':
        return None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize')
        try:
            value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
        finally:
            winreg.CloseKey(key)
        return not bool(value)
    except OSError:
        # The key is absent on builds predating the light/dark setting.
        return False


def resolve(mode: str) -> Palette:
    """Turn a mode name into the palette to actually paint with."""
    if mode == 'Dark':
        return DARK
    if mode == 'Light':
        return LIGHT

    # Qt's own hint is the better source when it exists: it reflects
    # per-application overrides and updates live.
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        app = QGuiApplication.instance()
        if app is not None:
            scheme = app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return DARK
            if scheme == Qt.ColorScheme.Light:
                return LIGHT
    except (AttributeError, ImportError):
        pass       # Qt older than 6.5, or no colour-scheme support built in.

    prefers_dark = windows_prefers_dark()
    if prefers_dark is None:
        return DARK
    return DARK if prefers_dark else LIGHT


def _first_installed(candidates, fallback: str) -> str:
    from PySide6.QtGui import QFontDatabase
    available = set(QFontDatabase.families())
    for family in candidates:
        if family in available:
            return family
    return fallback


def mono_family() -> str:
    """The best fixed-pitch family installed. Reports are space-aligned."""
    return _first_installed(MONO_FAMILIES, 'monospace')


def display_family() -> str:
    """The condensed display face used for headings and controls."""
    return _first_installed(DISPLAY_FAMILIES, 'sans-serif')


def qpalette(p: Palette):
    """A QPalette matching the stylesheet.

    The stylesheet cannot reach everything: dropdown arrows, the text cursor
    and focus rings are drawn by the style from the palette.
    """
    from PySide6.QtGui import QColor, QPalette

    qp = QPalette()
    text = QColor(p.text)
    base = QColor(p.base_top)
    accent = QColor(p.accent)

    for group in (QPalette.Active, QPalette.Inactive):
        qp.setColor(group, QPalette.Window, QColor(p.base_bottom))
        qp.setColor(group, QPalette.WindowText, text)
        qp.setColor(group, QPalette.Base, base)
        qp.setColor(group, QPalette.AlternateBase, QColor(p.base_bottom))
        qp.setColor(group, QPalette.Text, text)
        qp.setColor(group, QPalette.Button, base)
        qp.setColor(group, QPalette.ButtonText, text)
        qp.setColor(group, QPalette.ToolTipBase, base)
        qp.setColor(group, QPalette.ToolTipText, text)
        qp.setColor(group, QPalette.Highlight, accent)
        qp.setColor(group, QPalette.HighlightedText, QColor(p.on_accent))
        qp.setColor(group, QPalette.PlaceholderText, QColor(p.text_dim))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        qp.setColor(QPalette.Disabled, role, QColor(p.text_faint))
    return qp


def arrow_icons(p: Palette) -> dict:
    """Render the dropdown and spin chevrons to PNGs, return their paths.

    Styling any part of a widget makes Qt stop drawing that widget's
    subcontrols, so the arrows vanish unless the stylesheet supplies an image.
    Qt stylesheets cannot take a data: URI, so these have to be real files.
    """
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    cache = Path(tempfile.gettempdir()) / 'quickscan-ui'
    cache.mkdir(parents=True, exist_ok=True)

    size, paths = 14, {}
    for name, points in (
            ('down', ((3.5, 5.5), (7.0, 9.0), (10.5, 5.5))),
            ('up', ((3.5, 8.5), (7.0, 5.0), (10.5, 8.5)))):
        tag = p.accent.lstrip('#')
        path = cache / f'rf-arrow-{name}-{tag}.png'
        if not path.exists():
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(p.accent))
            pen.setWidthF(1.7)
            pen.setCapStyle(Qt.SquareCap)
            painter.setPen(pen)
            painter.drawPolyline([QPointF(x, y) for x, y in points])
            painter.end()
            pixmap.save(str(path))
        paths[name] = str(path).replace('\\', '/')   # QSS wants forward slashes
    return paths


def stylesheet(p: Palette, mono: str = 'Consolas',
               display: str = 'Bahnschrift Condensed') -> str:
    """The whole application stylesheet for one palette."""
    arrows = arrow_icons(p)
    down, up = arrows['down'], arrows['up']
    return f"""
/* ---- base ------------------------------------------------------- */
/* Monospace is the default rather than the exception: nearly everything
   in this window is a number, a price or a column. */
QWidget {{
    color: {p.text};
    font-family: "{mono}", monospace;
    font-size: 12px;
}}
QMainWindow, QDialog {{
    background: {p.base_bottom};
}}
QToolTip {{
    background: {p.base_top};
    color: {p.accent};
    border: 1px solid {p.border_strong};
    border-radius: 0px;
    padding: 6px 9px;
}}

/* ---- ruled boxes, not floating cards ---------------------------- */
QFrame#Panel {{
    background: {p.card};
    border: 1px solid {p.border};
    border-radius: 2px;
}}
QFrame#HeaderBar {{
    background: {p.card};
    border: 1px solid {p.border};
    border-left: 3px solid {p.accent};
    border-radius: 2px;
}}

/* ---- type ------------------------------------------------------- */
QLabel#AppTitle {{
    font-family: "{display}", sans-serif;
    font-size: 27px;
    font-weight: 700;
    letter-spacing: 3px;
    color: {p.text};
}}
QLabel#AppMark {{
    font-family: "{display}", sans-serif;
    font-size: 27px;
    font-weight: 700;
    letter-spacing: 3px;
    color: {p.accent};
}}
QLabel#AppSubtitle {{
    color: {p.text_dim};
    font-size: 11px;
    letter-spacing: 0.6px;
}}
QLabel#FieldLabel {{
    color: {p.text_dim};
}}
/* Qt stylesheets have no text-transform, so these labels are given their
   text already in capitals by the code that creates them. */
QLabel#SectionLabel {{
    font-family: "{display}", sans-serif;
    color: {p.accent};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2.2px;
}}
QLabel#Pill {{
    border-radius: 2px;
    padding: 5px 11px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1.1px;
}}

/* ---- controls --------------------------------------------------- */
QPushButton {{
    font-family: "{display}", sans-serif;
    background: transparent;
    border: 1px solid {p.border_strong};
    border-radius: 2px;
    padding: 8px 15px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 1.3px;
    color: {p.text};
}}
QPushButton:hover {{
    background: {p.card_hover};
    color: {p.accent};
}}
QPushButton:pressed {{
    background: {p.selection};
}}
QPushButton:disabled {{
    color: {p.text_faint};
    border-color: {p.border};
}}
QPushButton#Primary {{
    background: {p.accent};
    border: 1px solid {p.accent};
    color: {p.on_accent};
    font-size: 15px;
    letter-spacing: 2px;
}}
QPushButton#Primary:hover {{
    background: {p.accent_hover};
    border-color: {p.accent_hover};
    color: {p.on_accent};
}}
QPushButton#Primary:disabled {{
    background: transparent;
    border-color: {p.border};
    color: {p.text_faint};
}}
QPushButton#Danger:enabled {{
    color: {p.sell};
    border-color: {p.sell};
}}
QPushButton#Danger:hover:enabled {{
    background: {p.card_hover};
    color: {p.sell};
}}
QPushButton#Ghost {{
    border-color: transparent;
    color: {p.text_dim};
    padding: 5px 9px;
}}
QPushButton#Ghost:hover {{
    border-color: {p.border};
    color: {p.accent};
}}

/* ---- inputs ----------------------------------------------------- */
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
    background: {p.field};
    border: 1px solid {p.border};
    border-radius: 2px;
    padding: 7px 9px;
    selection-background-color: {p.selection};
    selection-color: {p.text};
}}
QLineEdit:hover, QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover {{
    border-color: {p.text_dim};
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
    border-color: {p.accent};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
    margin-right: 3px;
}}
QComboBox::down-arrow {{
    image: url({down});
    width: 14px;
    height: 14px;
}}
QComboBox QAbstractItemView {{
    background: {p.base_top};
    border: 1px solid {p.border_strong};
    border-radius: 0px;
    padding: 2px;
    selection-background-color: {p.selection};
    selection-color: {p.accent};
    outline: none;
}}
QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    background: transparent;
    border: none;
    width: 18px;
}}
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
    image: url({up});
    width: 14px;
    height: 14px;
}}
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
    image: url({down});
    width: 14px;
    height: 14px;
}}

/* ---- checkboxes ------------------------------------------------- */
QCheckBox {{
    spacing: 9px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 0px;
    border: 1px solid {p.border_strong};
    background: {p.field};
}}
QCheckBox::indicator:hover {{
    border-color: {p.accent};
}}
QCheckBox::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
}}

/* ---- symbol list ------------------------------------------------ */
QListWidget {{
    background: {p.field};
    border: 1px solid {p.border};
    border-radius: 2px;
    padding: 2px;
    outline: none;
}}
QListWidget::item {{
    border-radius: 0px;
    padding: 4px 5px;
}}
QListWidget::item:hover {{
    background: {p.card_hover};
    color: {p.accent};
}}
QListWidget::indicator {{
    width: 13px;
    height: 13px;
    border-radius: 0px;
    border: 1px solid {p.border_strong};
    background: transparent;
}}
QListWidget::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
}}

/* ---- report view ------------------------------------------------ */
/* The family must be set here rather than with setFont: a font-family in the
   stylesheet overrides the widget's own font, so the two would fight. */
QPlainTextEdit#Report {{
    background: {p.field};
    border: 1px solid {p.border};
    border-radius: 2px;
    padding: 11px;
    font-family: "{mono}", monospace;
    font-size: 12px;
    selection-background-color: {p.selection};
    selection-color: {p.text};
}}

/* ---- tables ----------------------------------------------------- */
QTableWidget, QTableView {{
    background: {p.field};
    border: 1px solid {p.border};
    border-radius: 2px;
    gridline-color: transparent;
    selection-background-color: {p.selection};
    selection-color: {p.text};
    outline: none;
}}
QTableWidget::item, QTableView::item {{
    padding: 4px 7px;
    border: none;
    border-bottom: 1px solid {p.border};
}}
QHeaderView::section {{
    font-family: "{display}", sans-serif;
    background: transparent;
    color: {p.accent};
    border: none;
    border-bottom: 1px solid {p.border_strong};
    padding: 7px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1.4px;
}}
QTableCornerButton::section {{
    background: transparent;
    border: none;
}}

/* ---- tabs ------------------------------------------------------- */
QTabWidget::pane {{
    border: none;
    top: 4px;
}}
QTabBar::tab {{
    font-family: "{display}", sans-serif;
    background: transparent;
    color: {p.text_dim};
    border: 1px solid transparent;
    border-bottom: 2px solid transparent;
    border-radius: 0px;
    padding: 7px 20px;
    margin-right: 2px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 2px;
}}
QTabBar::tab:hover {{
    color: {p.accent};
}}
QTabBar::tab:selected {{
    color: {p.accent};
    border-bottom: 2px solid {p.accent};
}}

/* ---- scrollbars ------------------------------------------------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px 1px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 1px 2px;
}}
QScrollBar::handle {{
    background: {p.text_faint};
    border-radius: 0px;
    min-height: 30px;
    min-width: 30px;
}}
QScrollBar::handle:hover {{
    background: {p.accent};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* ---- chrome ----------------------------------------------------- */
QSplitter::handle {{
    background: transparent;
    width: 10px;
}}
QStatusBar {{
    background: transparent;
    color: {p.text_dim};
    font-size: 11px;
}}
QStatusBar::item {{
    border: none;
}}
QMessageBox {{
    background: {p.base_bottom};
}}
QMessageBox QLabel {{
    color: {p.text};
}}
"""
