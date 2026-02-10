"""告警横幅：订阅 AppState.alarms_changed，显示最高严重级 1 条告警 + Ack 按钮。支持 set_tokens。"""

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

from app.core.alarm_engine import Alarm, Severity

if TYPE_CHECKING:
    from app.core.state import AppState
    from app.core.alarm_controller import AlarmController
    from app.ui.layout_profile import LayoutTokens


_SEVERITY_ORDER = (Severity.CRITICAL, Severity.WARN, Severity.INFO)


def _top_alarm(alarms: list[Alarm]) -> Alarm | None:
    """取最高严重级 1 条：CRITICAL > WARN > INFO"""
    if not alarms:
        return None
    for sev in _SEVERITY_ORDER:
        for a in alarms:
            if a.severity == sev:
                return a
    return alarms[0]


class AlarmBanner(QFrame):
    """告警横幅：订阅 alarms_changed，显示最高级 1 条，Ack 调用 AlarmController。支持 set_tokens。"""

    def __init__(
        self,
        app_state: "AppState",
        alarm_controller: "AlarmController",
        tokens: "LayoutTokens | None" = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("alarmBanner")
        self._app_state = app_state
        self._alarm_controller = alarm_controller
        self._current: Alarm | None = None
        self._tokens = tokens

        layout = QHBoxLayout(self)
        self._apply_tokens(layout)
        self._label = QLabel("")
        self._label.setWordWrap(False)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._label, 1)
        self._ack_btn = QPushButton("确认")
        if tokens:
            self._ack_btn.setMinimumHeight(tokens.btn_h)
        else:
            self._ack_btn.setMinimumHeight(44)
        self._ack_btn.clicked.connect(self._on_ack)
        layout.addWidget(self._ack_btn)

        app_state.alarms_changed.connect(self._on_alarms_changed)
        if tokens:
            self.setFixedHeight(tokens.btn_h + tokens.gap * 2)
        self.hide()

    def _apply_tokens(self, layout: QHBoxLayout) -> None:
        t = self._tokens
        if t:
            layout.setContentsMargins(t.pad_page, t.gap, t.pad_page, t.gap)
            layout.setSpacing(t.gap)
        else:
            layout.setContentsMargins(10, 6, 10, 6)
            layout.setSpacing(12)

    def set_tokens(self, tokens: "LayoutTokens") -> None:
        self._tokens = tokens
        layout = self.layout()
        if layout:
            self._apply_tokens(layout)
        self._ack_btn.setMinimumHeight(tokens.btn_h)
        self.setFixedHeight(tokens.btn_h + tokens.gap * 2)

    def _on_alarms_changed(self, alarms: list) -> None:
        top = _top_alarm(alarms)
        if top is None:
            self.hide()
            self._current = None
            self.setProperty("severity", "")
            return
        self._current = top
        raw = f"{top.title}: {top.message}"
        max_len = 60
        self._label.setText(raw if len(raw) <= max_len else raw[: max_len - 3] + "...")
        # QSS 通过 property severity 区分颜色：info(绿) / warn(黄) / critical(红)
        self.setProperty("severity", top.severity.value.lower())
        self.style().unpolish(self)
        self.style().polish(self)
        self._ack_btn.setEnabled(not top.ack)
        self.show()

    def _on_ack(self) -> None:
        if self._current:
            self._alarm_controller.ack(self._current.id)
