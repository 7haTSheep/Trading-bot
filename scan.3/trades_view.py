"""The Trades tab: what was actually traded, and whether it was traded well.

Two halves of the same question. The left is the record -- every closed
position from the terminal, with the statistics that say whether repeating
this is worth doing. The right is the pre-trade checklist from the discipline
app, which is about the decision before the trade rather than the result
after it.

The checklist is kept because most of what goes wrong in these numbers is
decided before entry: oversizing, no stop, and trading to win a loss back
cannot be diagnosed from a P/L column afterwards.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QSizePolicy, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

import trades as trades_model
from theme import Palette

PERIODS = [('Last 7 days', 7), ('Last 30 days', 30),
           ('Last 90 days', 90), ('Last year', 365)]


def _section(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName('SectionLabel')
    return label


class StatCard(QFrame):
    """One number with its name. Tone colours it good, bad or neutral."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName('Panel')
        self._tone = 'neutral'
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 12)
        layout.setSpacing(3)
        self.name = _section(label)
        self.value = QLabel('--')
        self.value.setObjectName('StatValue')
        self.sub = QLabel('')
        self.sub.setObjectName('AppSubtitle')
        layout.addWidget(self.name)
        layout.addWidget(self.value)
        layout.addWidget(self.sub)

    def set_value(self, value: str, sub: str = '', tone: str = 'neutral'):
        self.value.setText(value)
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))
        self._tone = tone
        self._paint()

    def set_palette(self, palette: Palette):
        self._palette = palette
        self._paint()

    def _paint(self):
        p = getattr(self, '_palette', None)
        if p is None:
            return
        colour = {'good': p.buy, 'bad': p.sell, 'warn': p.warn}.get(self._tone, p.text)
        # Monospace so a column of these stays aligned as the digits change.
        self.value.setStyleSheet(
            f'color: {colour}; font-size: 25px; font-weight: 700;'
            f' letter-spacing: -0.5px;')


class EquityCurve(QWidget):
    """Running total of realised profit, trade by trade.

    Drawn rather than charted: a plotting library would add tens of megabytes
    to the bundle for one line.
    """

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._points: List[float] = []
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_palette(self, palette: Palette):
        self._palette = palette
        self.update()

    def set_points(self, points: List[float]):
        self._points = list(points)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        p = self._palette
        # A left gutter for the scale, so the labels never sit on the line.
        gutter = 62
        rect = self.rect().adjusted(gutter, 10, -10, -10)

        if len(self._points) < 2:
            painter.setPen(QPen(QColor(p.text_faint)))
            painter.drawText(self.rect(), Qt.AlignCenter,
                             'Not enough closed trades to plot yet')
            painter.end()
            return

        low = min(min(self._points), 0.0)
        high = max(max(self._points), 0.0)
        span = (high - low) or 1.0

        def x_at(i: int) -> float:
            return rect.left() + rect.width() * i / (len(self._points) - 1)

        def y_at(value: float) -> float:
            return rect.bottom() - rect.height() * (value - low) / span

        # Break-even matters more than any gridline: above it the account grew.
        zero = y_at(0.0)
        pen = QPen(QColor(p.border_strong))
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(rect.left()), int(zero), int(rect.right()), int(zero))

        final = self._points[-1]
        colour = QColor(p.buy if final >= 0 else p.sell)

        path = QPainterPath()
        path.moveTo(x_at(0), y_at(self._points[0]))
        for i, value in enumerate(self._points[1:], start=1):
            path.lineTo(x_at(i), y_at(value))

        under = QPainterPath(path)
        under.lineTo(x_at(len(self._points) - 1), zero)
        under.lineTo(x_at(0), zero)
        under.closeSubpath()
        fade = QLinearGradient(0, rect.top(), 0, rect.bottom())
        tinted = QColor(colour)
        tinted.setAlpha(70)
        fade.setColorAt(0.0, tinted)
        fade.setColorAt(1.0, QColor(colour.red(), colour.green(), colour.blue(), 0))
        painter.fillPath(under, QBrush(fade))

        line = QPen(colour)
        line.setWidthF(2.0)
        line.setJoinStyle(Qt.RoundJoin)
        painter.setPen(line)
        painter.drawPath(path)

        painter.setPen(QPen(QColor(p.text_dim)))
        labels = self.rect().adjusted(6, 10, -(self.rect().width() - gutter + 6), -10)
        painter.drawText(labels, Qt.AlignTop | Qt.AlignRight, f'{high:,.2f}')
        painter.drawText(labels, Qt.AlignBottom | Qt.AlignRight, f'{low:,.2f}')
        if low < 0 < high:
            zero_label = labels.adjusted(0, int(zero - labels.top()) - 8, 0, 0)
            painter.drawText(zero_label, Qt.AlignTop | Qt.AlignRight, '0.00')
        painter.end()


class ChecklistPanel(QFrame):
    """The pre-trade checklist. Nothing unlocks until every line is ticked."""

    logged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('Panel')
        self._palette: Optional[Palette] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(9)

        head = QHBoxLayout()
        head.addWidget(_section('Pre-trade checklist'))
        head.addStretch()
        self.verdict = QLabel('Incomplete')
        head.addWidget(self.verdict)
        layout.addLayout(head)

        # A QCheckBox cannot wrap its own label, and these lines are sentences
        # rather than words, so the text lives in a QLabel beside the box and
        # clicking it toggles the box, as a real label would.
        self.boxes = {}
        for key, text in trades_model.CHECKLIST_ITEMS:
            box = QCheckBox()
            box.stateChanged.connect(self._refresh)
            self.boxes[key] = box

            caption = QLabel(text)
            caption.setWordWrap(True)
            caption.setCursor(Qt.PointingHandCursor)
            caption.mousePressEvent = (
                lambda event, b=box: b.setChecked(not b.isChecked()))

            row = QHBoxLayout()
            row.setSpacing(9)
            row.addWidget(box, 0, Qt.AlignTop)
            row.addWidget(caption, 1)
            layout.addLayout(row)

        layout.addStretch()
        self.log_button = QPushButton('Log checklist and reset')
        self.log_button.setEnabled(False)
        self.log_button.setCursor(Qt.PointingHandCursor)
        self.log_button.clicked.connect(self._log)
        layout.addWidget(self.log_button)

        self.history = QLabel('')
        self.history.setObjectName('AppSubtitle')
        layout.addWidget(self.history)
        self._refresh()

    def set_palette(self, palette: Palette):
        self._palette = palette
        self._refresh()

    def _all_ticked(self) -> bool:
        return all(box.isChecked() for box in self.boxes.values())

    def _refresh(self):
        complete = self._all_ticked()
        self.log_button.setEnabled(complete)
        self.verdict.setText('Clear to trade' if complete else 'Incomplete')
        if self._palette is not None:
            colour = self._palette.buy if complete else self._palette.warn
            self.verdict.setStyleSheet(f'color: {colour}; font-weight: 600;')
        self._show_count()

    def _show_count(self):
        try:
            rows = trades_model.load_checklist_log()
        except OSError:
            return
        if rows:
            self.history.setText(
                f'{len(rows)} logged · last {rows[-1]["time"].replace("T", " ")}')

    def _log(self):
        ticked = {key: box.isChecked() for key, box in self.boxes.items()}
        try:
            trades_model.log_checklist(ticked)
        except OSError as exc:
            self.logged.emit(f'Could not save the checklist: {exc}')
            return
        for box in self.boxes.values():
            box.setChecked(False)
        self._refresh()
        self.logged.emit('Checklist logged')


class TradesTab(QWidget):
    """History, statistics and checklist."""

    refresh_requested = Signal(int)      # days

    COLUMNS = ['Closed', 'Symbol', 'Side', 'Volume', 'Entry', 'Exit',
               'Stop', 'R', 'Profit']

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._trades: List[trades_model.Trade] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        # ---- left: the record ----------------------------------------
        left = QVBoxLayout()
        left.setSpacing(12)

        controls = QHBoxLayout()
        controls.addWidget(_section('Trade history'))
        controls.addStretch()
        self.period = QComboBox()
        for label, days in PERIODS:
            self.period.addItem(label, days)
        self.period.setCurrentIndex(1)
        self.period.currentIndexChanged.connect(self._request)
        self.refresh_button = QPushButton('Refresh')
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.clicked.connect(self._request)
        controls.addWidget(self.period)
        controls.addWidget(self.refresh_button)
        left.addLayout(controls)

        # Deliberately not a uniform grid. Net profit is the number that
        # actually answers the question, so it gets double width and the rest
        # sit under it in a plain row.
        self.cards = {}
        grid = QGridLayout()
        grid.setSpacing(9)
        for key, label, row, column, span in (
                ('net', 'Net profit', 0, 0, 2),
                ('win_rate', 'Win rate', 0, 2, 1),
                ('expectancy', 'Expectancy', 1, 0, 1),
                ('avg_r', 'Average R', 1, 1, 1),
                ('streak', 'Worst losing run', 1, 2, 1)):
            card = StatCard(label)
            self.cards[key] = card
            grid.addWidget(card, row, column, 1, span)
        left.addLayout(grid)

        curve_panel = QFrame()
        curve_panel.setObjectName('Panel')
        curve_layout = QVBoxLayout(curve_panel)
        curve_layout.setContentsMargins(14, 12, 14, 12)
        curve_layout.setSpacing(6)
        curve_layout.addWidget(_section('Equity curve'))
        self.curve = EquityCurve(palette)
        curve_layout.addWidget(self.curve)
        left.addWidget(curve_panel)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        for column in (0, 1):        # timestamp and symbol need their width
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        left.addWidget(self.table, 1)

        left_holder = QWidget()
        left_holder.setLayout(left)
        root.addWidget(left_holder, 3)

        # ---- right: the discipline -----------------------------------
        self.checklist = ChecklistPanel()
        self.checklist.setMaximumWidth(330)
        root.addWidget(self.checklist, 1)

        self.set_palette(palette)

    def set_palette(self, palette: Palette):
        self._palette = palette
        self.curve.set_palette(palette)
        self.checklist.set_palette(palette)
        for card in self.cards.values():
            card.set_palette(palette)
        self._fill_table()

    def _request(self):
        self.refresh_requested.emit(self.period.currentData())

    def set_busy(self, busy: bool):
        self.refresh_button.setEnabled(not busy)
        self.refresh_button.setText('Loading...' if busy else 'Refresh')

    def show_trades(self, rows: List[trades_model.Trade]):
        self._trades = rows
        stats = trades_model.compute_stats(rows)
        p = self._palette

        def tone(value: float) -> str:
            return 'good' if value > 0 else 'bad' if value < 0 else 'neutral'

        self.cards['net'].set_value(
            f'{stats.net_profit:,.2f}',
            f'{stats.count} trades · {stats.wins} won · {stats.losses} lost'
            f'  |  best {stats.best:,.2f} · worst {stats.worst:,.2f}' if rows else '',
            tone(stats.net_profit))
        self.cards['win_rate'].set_value(
            f'{stats.win_rate:.0f}%' if rows else '--',
            f'avg win {stats.avg_win:,.2f} · avg loss {stats.avg_loss:,.2f}' if rows else '')
        self.cards['expectancy'].set_value(
            f'{stats.expectancy:,.2f}' if rows else '--',
            'per trade' if rows else '', tone(stats.expectancy))
        self.cards['avg_r'].set_value(
            f'{stats.avg_r:.2f}' if stats.avg_r is not None else '--',
            'needs a stop on the order' if rows and stats.avg_r is None else '',
            tone(stats.avg_r) if stats.avg_r is not None else 'neutral')
        self.cards['streak'].set_value(
            str(stats.max_loss_streak) if rows else '--',
            f'best run {stats.max_win_streak}' if rows else '',
            'bad' if stats.max_loss_streak >= 4 else 'neutral')

        self.curve.set_points(stats.equity_curve)
        self._fill_table()

    def _fill_table(self):
        p = self._palette
        self.table.setRowCount(len(self._trades))
        for row, trade in enumerate(self._trades):
            values = [
                trade.closed_at.strftime('%d %b %H:%M'),
                trade.symbol,
                trade.side,
                f'{trade.volume:g}',
                f'{trade.entry:.5g}',
                f'{trade.exit:.5g}',
                f'{trade.stop:.5g}' if trade.stop else '--',
                f'{trade.r_multiple:+.2f}' if trade.r_multiple is not None else '--',
                f'{trade.profit:+,.2f}',
            ]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column in (3, 4, 5, 6, 7, 8):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if column == 2:
                    item.setForeground(QColor(p.buy if trade.side == 'BUY' else p.sell))
                if column in (7, 8):
                    item.setForeground(QColor(p.buy if trade.profit > 0
                                              else p.sell if trade.profit < 0
                                              else p.text_dim))
                self.table.setItem(row, column, item)
