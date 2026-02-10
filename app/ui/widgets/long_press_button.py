"""长按确认按钮。支持 set_tokens 或构造传入 tokens，关键操作用 btn_h_key。"""

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QPaintEvent, QPainter, QColor, QBrush

if TYPE_CHECKING:
    from app.ui.layout_profile import LayoutTokens


class LongPressButton(QPushButton):
    """长按达到 hold_ms 后发射 confirmed()，松开提前则取消。默认 minHeight=btn_h_key(52)。"""

    confirmed = pyqtSignal()

    def __init__(
        self,
        text: str = "",
        tokens: "LayoutTokens | None" = None,
        parent=None,
    ):
        super().__init__(text, parent)
        self._tokens = tokens
        h = tokens.btn_h_key if tokens else 52
        self.setMinimumHeight(h)
        self._hold_ms = 2000
        self._progress = 0.0
        self._elapsed_ms = 0
        self._original_text = text
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._update_interval_ms = 50

    def hold_ms(self) -> int:
        return self._hold_ms

    def set_hold_ms(self, ms: int) -> None:
        self._hold_ms = max(100, ms)

    def setHoldMs(self, ms: int) -> None:
        self.set_hold_ms(ms)

    def setDanger(self, danger: bool) -> None:
        self.setProperty("danger", str(danger).lower())
        self.style().unpolish(self)
        self.style().polish(self)

    def set_tokens(self, tokens: "LayoutTokens") -> None:
        self._tokens = tokens
        self.setMinimumHeight(tokens.btn_h_key)

    def _start_hold(self) -> None:
        self._original_text = self.text()
        self._progress = 0.0
        self._elapsed_ms = 0
        self._timer.timeout.disconnect()
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(self._update_interval_ms)

    def _on_tick(self) -> None:
        self._elapsed_ms += self._update_interval_ms
        self._progress = min(1.0, self._elapsed_ms / self._hold_ms)
        self._update_display()
        if self._progress >= 1.0:
            self._timer.stop()
            self.confirmed.emit()
            self.setText(self._original_text)

    def _cancel_hold(self) -> None:
        self._timer.stop()
        self.setText(self._original_text)
        self._progress = 0.0
        self.update()

    def _update_display(self) -> None:
        pct = int(self._progress * 100)
        self.setText(f"{self._original_text} ({pct}%)")
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if 0 < self._progress < 1.0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            h = self.height()
            m = self._bar_margin()
            bar_h = max(m, h // 8)
            y = h - bar_h - m
            w = self.width() - m * 2
            x = m
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 60)))
            painter.drawRoundedRect(x, y, w, bar_h, bar_h // 2, bar_h // 2)
            painter.setBrush(QBrush(QColor(37, 99, 235, 200)))
            painter.drawRoundedRect(x, y, int(w * self._progress), bar_h, bar_h // 2, bar_h // 2)
            painter.end()

    def _bar_margin(self) -> int:
        t = self._tokens
        return t.gap if t else 4

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            self._start_hold()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._timer.isActive():
                self._cancel_hold()
            self.setDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
