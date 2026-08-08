"""The textured backdrop, and colouring for scan reports.

TextureBackdrop paints the surface everything else sits on: a warm near-black
(or warm paper) base under film grain and faint horizontal scanlines. The
grain is a tiled noise pixmap rather than per-pixel drawing, so repainting on
resize costs nothing, and it is generated from a fixed seed so the texture
does not crawl between repaints.

ReportHighlighter colours the scanner's output. The reports run sixty-odd
lines per symbol, and the parts that decide whether you act on one -- the
decision, the grade, the checklist -- should be findable without reading the
rest. Amber marks anything requiring a judgement, green and crimson mark
direction and outcome, and nothing else is coloured at all.
"""
from __future__ import annotations

import random

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                           QPen, QPixmap, QSyntaxHighlighter, QTextCharFormat)
from PySide6.QtWidgets import QWidget

from theme import Palette

GRAIN_TILE = 128


def _grain_tile(palette: Palette) -> QPixmap:
    """A tileable noise square. Cached per palette on the palette's name."""
    cache = _grain_tile._cache
    key = (palette.name, palette.grain)
    if key in cache:
        return cache[key]

    pixmap = QPixmap(GRAIN_TILE, GRAIN_TILE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    # Fixed seed: the grain must be identical every repaint, or resizing the
    # window makes the texture visibly crawl.
    rng = random.Random(20260808)
    light = QColor(255, 255, 255, palette.grain)
    dark = QColor(0, 0, 0, palette.grain)
    for _ in range(GRAIN_TILE * 10):
        x = rng.randrange(GRAIN_TILE)
        y = rng.randrange(GRAIN_TILE)
        painter.setPen(QPen(light if rng.random() > 0.5 else dark))
        painter.drawPoint(x, y)
    painter.end()

    cache[key] = pixmap
    return pixmap


_grain_tile._cache = {}


class TextureBackdrop(QWidget):
    """Base gradient, film grain, and scanlines. Everything layers over it."""

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self.setAttribute(Qt.WA_StyledBackground, False)

    def set_palette(self, palette: Palette):
        self._palette = palette
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        p = self._palette

        base = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base.setColorAt(0.0, QColor(p.base_top))
        base.setColorAt(1.0, QColor(p.base_bottom))
        painter.fillRect(rect, QBrush(base))

        painter.fillRect(rect, QBrush(_grain_tile(p)))

        # Scanlines every third row. Subtle enough to read as texture rather
        # than stripes, but it stops the background looking like flat fill.
        painter.setPen(QPen(QColor(0, 0, 0, p.scanline)))
        for y in range(rect.top(), rect.bottom(), 3):
            painter.drawLine(rect.left(), y, rect.right(), y)

        painter.end()


def _format(colour: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(colour))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class ReportHighlighter(QSyntaxHighlighter):
    """Colours the scanner's plain-text reports as they stream in."""

    def __init__(self, document, palette: Palette):
        super().__init__(document)
        self._rules = []
        self.set_palette(palette)

    def set_palette(self, palette: Palette):
        p = palette
        heading = _format(p.accent, bold=True)
        rules = [
            # Rules run in order and later ones win on overlap, so the broad
            # "label:" rule comes before the specific values it would dim.
            (r'^={3,}.*$', _format(p.text_faint)),
            (r'^\s*\d{1,2}\.\s+[A-Z][A-Z0-9 &/\-]+$', heading),
            (r'^=== .+ ===.*$', heading),

            (r'^\s{2,}[A-Za-z][A-Za-z0-9 ()/:%\-\.]*?\s*:', _format(p.text_dim)),

            (r'\bBUY NOW\b|\bSTRONG BUY\b', _format(p.buy, bold=True)),
            (r'\bSELL NOW\b|\bSTRONG SELL\b', _format(p.sell, bold=True)),
            (r'\bWAIT FOR [A-Z]+\b|\bWAIT\b(?! *\])', _format(p.warn, bold=True)),
            (r'\bNO TRADE\b', _format(p.neutral, bold=True)),

            (r'\bBULL\b|\bBULLISH\b', _format(p.buy)),
            (r'\bBEAR\b|\bBEARISH\b', _format(p.sell)),

            (r'\[YES \]', _format(p.buy, bold=True)),
            (r'\[NO  \]', _format(p.sell, bold=True)),
            (r'\[WAIT\]', _format(p.warn, bold=True)),

            (r'\bA\+ Setup\b|\bA Setup\b', _format(p.buy, bold=True)),
            (r'\bB Setup\b', _format(p.accent, bold=True)),
            (r'\bC Setup\b', _format(p.warn, bold=True)),

            (r'\bStop Loss\b|\bInvalidation\b|Thesis fails if', _format(p.sell)),
            (r'\bTP[123]\b|\bRunner Target\b', _format(p.buy)),

            (r'Priority: High', _format(p.text_dim, bold=True)),
            (r'Priority: Medium', _format(p.text_faint)),

            (r'CALIBRATION WARNING.*$', _format(p.sell, bold=True)),
            (r'^\s*->.*$', _format(p.text_dim, italic=True)),
        ]
        self._rules = [(QRegularExpression(pattern), fmt) for pattern, fmt in rules]
        self.rehighlight()

    def highlightBlock(self, text: str):
        for expression, fmt in self._rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
