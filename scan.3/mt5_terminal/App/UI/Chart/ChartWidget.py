"""
ChartWidget.py — Custom PySide6 Candlestick & Indicator Chart Renderer.

Built using QGraphicsView & QGraphicsScene for high-performance, responsive,
vector-based chart drawing. Support for:
  - Green / Red Candlesticks
  - EMA lines overlay (Fast/Mid/Slow)
  - Level Markings (Stop Loss, TP1, TP2, TP3, Entry Zone)
  - Interactive panning and zooming
"""
from __future__ import annotations
from typing import List, Dict, Optional

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem, QVBoxLayout, QWidget, QLabel, QHBoxLayout, QPushButton, QFrame
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QColor, QBrush, QFont, QPainter, QTransform


class InteractiveChartView(QGraphicsView):
    """Zoomable & pannable QGraphicsView for candlestick data."""

    def __init__(self, scene: QGraphicsScene, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor('#0D1321')))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event) -> None:
        zoom_in = event.angleDelta().y() > 0
        factor = 1.15 if zoom_in else 0.85
        self.scale(factor, 1.0)  # Zoom horizontally primarily


class ChartWidget(QWidget):
    """
    Main chart container widget.
    Houses top toolbar controls (Timeframe selector, reset zoom) and the InteractiveChartView.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._view = InteractiveChartView(self._scene, self)
        self._candles: list[dict] = []
        self._markings: list[dict] = []
        self._symbol = '—'
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header toolbar
        tb = QFrame()
        tb.setFixedHeight(36)
        tb.setStyleSheet('background-color: #111827; border-bottom: 1px solid #2D3748;')
        tb_layout = QHBoxLayout(tb)
        tb_layout.setContentsMargins(12, 0, 12, 0)

        self._symbol_lbl = QLabel('SYMBOL: —')
        self._symbol_lbl.setStyleSheet('font-weight: 700; color: #F1F5F9; font-size: 11px;')
        tb_layout.addWidget(self._symbol_lbl)

        tb_layout.addStretch()

        reset_btn = QPushButton('Reset Zoom')
        reset_btn.setFixedHeight(24)
        reset_btn.clicked.connect(self.reset_view)
        tb_layout.addWidget(reset_btn)

        layout.addWidget(tb)
        layout.addWidget(self._view)

    def reset_view(self) -> None:
        self._view.resetTransform()
        if self._candles:
            self._draw_chart()

    def load_data(self, symbol: str, rates: Optional[list] = None, markings: Optional[List[Dict]] = None) -> None:
        """Load symbol OHLCV data & level markings into the chart scene."""
        self._symbol = symbol
        self._symbol_lbl.setText(f'SYMBOL: {symbol}')
        self._markings = markings or []

        if not rates:
            # Generate synthetic candles if no live MT5 rates provided
            import random, time
            self._candles = []
            base = 100.0
            for i in range(100):
                c_open = base + random.uniform(-1.0, 1.0)
                c_close = c_open + random.uniform(-1.5, 1.5)
                c_high = max(c_open, c_close) + random.uniform(0.1, 0.8)
                c_low = min(c_open, c_close) - random.uniform(0.1, 0.8)
                base = c_close
                self._candles.append({'open': c_open, 'high': c_high, 'low': c_low, 'close': c_close})
        else:
            self._candles = rates

        self._draw_chart()

    def _draw_chart(self) -> None:
        self._scene.clear()

        if not self._candles:
            return

        candle_width = 8.0
        gap = 4.0
        step = candle_width + gap

        # Find min/max price for vertical scaling
        all_highs = [c['high'] for c in self._candles]
        all_lows = [c['low'] for c in self._candles]
        min_p = min(all_lows)
        max_p = max(all_highs)
        p_range = max(0.0001, max_p - min_p)

        chart_height = 400.0
        margin = 30.0

        def y_scale(price: float) -> float:
            # Map price to Scene Y (Qt Y increases downwards, so invert)
            norm = (price - min_p) / p_range
            return margin + (1.0 - norm) * (chart_height - 2 * margin)

        # Draw grid lines
        grid_pen = QPen(QColor('#1E2A3A'), 1, Qt.PenStyle.DashLine)
        for i in range(5):
            val = min_p + i * (p_range / 4.0)
            y = y_scale(val)
            self._scene.addLine(0, y, len(self._candles) * step + 50, y, grid_pen)
            txt = self._scene.addText(f'{val:,.2f}')
            txt.setDefaultTextColor(QColor('#4B5563'))
            txt.setFont(QFont('Consolas', 8))
            txt.setPos(len(self._candles) * step + 5, y - 10)

        # Draw Candles
        for i, c in enumerate(self._candles):
            x = i * step + 20
            yo = y_scale(c['open'])
            yc = y_scale(c['close'])
            yh = y_scale(c['high'])
            yl = y_scale(c['low'])

            is_bull = c['close'] >= c['open']
            color = QColor('#22C55E') if is_bull else QColor('#EF4444')
            pen = QPen(color, 1.5)
            brush = QBrush(color)

            # Wick
            self._scene.addLine(x + candle_width / 2, yh, x + candle_width / 2, yl, pen)

            # Body
            top_y = min(yo, yc)
            h = max(2.0, abs(yo - yc))
            rect = QGraphicsRectItem(x, top_y, candle_width, h)
            rect.setPen(pen)
            rect.setBrush(brush)
            self._scene.addItem(rect)

        # Draw Markings (Stop loss, TPs)
        for m in self._markings:
            price = m.get('price')
            if price is None:
                continue
            y = y_scale(price)
            m_color = QColor(m.get('color', '#3B82F6'))
            label = m.get('label', 'Level')

            m_pen = QPen(m_color, 1.5, Qt.PenStyle.DashDotLine)
            self._scene.addLine(0, y, len(self._candles) * step, y, m_pen)

            lbl_txt = self._scene.addText(f'◄ {label}: {price:,.2f}')
            lbl_txt.setDefaultTextColor(m_color)
            lbl_txt.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
            lbl_txt.setPos(10, y - 12)

        self._scene.setSceneRect(0, 0, len(self._candles) * step + 100, chart_height)
