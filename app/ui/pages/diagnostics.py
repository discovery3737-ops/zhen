"""诊断页面 - WVGA：从站列表样式（每行在线点+错误计数）+ 告警列表折叠"""

import datetime

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer

from app.ui.pages.base import PageBase
from app.ui.layout_profile import LayoutTokens, get_tokens
from app.core.alarm_engine import Alarm, Severity

def _get_video_diagnostics() -> dict:
    try:
        from app.services.video_manager import get_diagnostics
        return get_diagnostics()
    except Exception:
        return {}

# 告警 ID -> 建议动作
SUGGESTED_ACTIONS: dict[str, str] = {
    "HVAC_HP_TRIP": "检查制冷系统压力，联系售后",
    "HVAC_LP_TRIP": "检查制冷剂泄漏，联系售后",
    "HVAC_REFRIG_SW": "检查制冷开关接线",
    "GAS_CO_WARN": "开窗通风，检查燃气设备",
    "GAS_CO_CRIT": "立即通风，撤离人员，检查燃气",
    "GAS_LPG_WARN": "开窗通风，检查 LPG 泄漏",
    "GAS_LPG_CRIT": "立即通风，关闭气源，撤离",
    "WEBASTO_FAULT": "查阅故障码手册，联系售后",
    "PDU_ESTOP": "解除急停开关后复位",
    "PDU_AC_CONTACTOR_MISMATCH": "检查逆变器 AC 接触器及反馈",
    "ENV_CABIN_TH_OFFLINE": "检查舱内温湿度传感器接线",
    "ENV_OUT_TH_OFFLINE": "检查舱外温湿度传感器接线",
}


def _format_ts(ts: float) -> str:
    if ts is None or ts <= 0:
        return "--"
    try:
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "--"


def _format_ts_short(ts: float) -> str:
    if ts is None or ts <= 0:
        return "--"
    try:
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return "--"


class AlarmDetailDialog(QDialog):
    def __init__(self, alarm: Alarm, parent=None):
        super().__init__(parent)
        self.setWindowTitle("告警详情")
        self.setMinimumWidth(400)
        layout = QGridLayout(self)
        row = 0
        layout.addWidget(QLabel("ID:"), row, 0)
        layout.addWidget(QLabel(alarm.id), row, 1)
        row += 1
        layout.addWidget(QLabel("级别:"), row, 0)
        layout.addWidget(QLabel(str(alarm.severity.value)), row, 1)
        row += 1
        layout.addWidget(QLabel("标题:"), row, 0)
        layout.addWidget(QLabel(alarm.title), row, 1)
        row += 1
        layout.addWidget(QLabel("消息:"), row, 0)
        layout.addWidget(QLabel(alarm.message), row, 1)
        row += 1
        slave = alarm.source_slave
        layout.addWidget(QLabel("来源从站:"), row, 0)
        layout.addWidget(QLabel(f"Slave{slave:02d}" if slave is not None else "--"), row, 1)
        row += 1
        layout.addWidget(QLabel("首次时间:"), row, 0)
        layout.addWidget(QLabel(_format_ts(alarm.first_seen_ts)), row, 1)
        row += 1
        layout.addWidget(QLabel("最近时间:"), row, 0)
        layout.addWidget(QLabel(_format_ts(alarm.last_seen_ts)), row, 1)
        row += 1
        layout.addWidget(QLabel("Ack 状态:"), row, 0)
        layout.addWidget(QLabel("已确认" if alarm.ack else "未确认"), row, 1)
        row += 1
        action = SUGGESTED_ACTIONS.get(alarm.id, "请查阅操作手册")
        layout.addWidget(QLabel("建议动作:"), row, 0)
        layout.addWidget(QLabel(action), row, 1)
        row += 1
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn.accepted.connect(self.accept)
        layout.addWidget(btn, row, 0, 1, 2)


class CollapsibleSection(QFrame):
    """可折叠区块：标题按钮 + 内容区。样式由 theme.qss collapsibleHeaderBtn 统一。"""

    def __init__(self, title: str, tokens: LayoutTokens | None, parent=None):
        super().__init__(parent)
        self.setObjectName("collapsibleSection")
        self._title = title
        self._content: QWidget | None = None
        self._expanded = False
        t = tokens
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        self._header_btn = QPushButton(objectName="collapsibleHeaderBtn")
        self._header_btn.setCheckable(True)
        bh = t.btn_h if t else 44
        self._header_btn.setMinimumHeight(bh)
        self._header_btn.clicked.connect(self._toggle)
        ly.addWidget(self._header_btn)
        self._update_header_text()

    def set_content(self, widget: QWidget) -> None:
        self._content = widget
        self._content.setVisible(self._expanded)
        self.layout().addWidget(self._content)

    def _update_header_text(self) -> None:
        prefix = "▼ " if self._expanded else "▶ "
        self._header_btn.setText(prefix + self._title)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._header_btn.setChecked(expanded)
        self._update_header_text()
        if self._content:
            self._content.setVisible(expanded)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self.set_expanded(self._expanded)


class DiagnosticsPage(PageBase):
    """诊断页：从站列表（每行在线点+错误计数）+ 告警列表折叠。布局由 tokens 驱动，无内联 setStyleSheet。"""

    def __init__(self, app_state=None, alarm_controller=None):
        super().__init__("诊断")
        self._app_state = app_state
        self._alarm_controller = alarm_controller
        self._alarms: list[Alarm] = []
        self._severity_filter: Severity | None = None
        self._tokens: LayoutTokens | None = get_tokens()
        t = self._tokens
        layout = self.layout()
        if layout is None:
            return

        while layout.count() > 0:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(t.gap if t else 8)
        inner_layout.setContentsMargins(t.pad_page if t else 10, t.pad_page if t else 10, t.pad_page if t else 10, t.pad_page if t else 10)

        title = QLabel("诊断")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner_layout.addWidget(title)

        # 从站列表：每行一个 slave，在线点 + 错误计数，列表样式不密
        slave_card = QFrame(objectName="card")
        slave_layout = QVBoxLayout(slave_card)
        slave_layout.setSpacing(4)
        slave_title = QLabel("从站通信")
        slave_title.setObjectName("accent")
        slave_layout.addWidget(slave_title)
        self._slave_rows: list[tuple[QLabel, QLabel, QLabel]] = []
        bh = t.btn_h if t else 44
        p, g = (t.pad_card if t else 8), (t.gap if t else 4)
        for sid in range(1, 10):
            row_w = QFrame(objectName="slaveRow")
            row_w.setMinimumHeight(bh)
            row_ly = QHBoxLayout(row_w)
            row_ly.setContentsMargins(p, g // 2, p, g // 2)
            dot = QLabel("●", objectName="slaveDot")
            dot.setProperty("severity", "unknown")
            dot.setFixedWidth(20)
            err_lbl = QLabel("0")
            err_lbl.setMinimumWidth(36)
            last_lbl = QLabel("--")
            last_lbl.setObjectName("small")
            row_ly.addWidget(dot)
            row_ly.addWidget(QLabel(f"Slave{sid:02d}"))
            row_ly.addStretch()
            row_ly.addWidget(QLabel("错误:"))
            row_ly.addWidget(err_lbl)
            row_ly.addWidget(QLabel("最后:"))
            row_ly.addWidget(last_lbl)
            slave_layout.addWidget(row_w)
            self._slave_rows.append((dot, err_lbl, last_lbl))
        inner_layout.addWidget(slave_card)

        # 视频诊断：折叠区块，默认折叠
        video_diag_section = CollapsibleSection("视频诊断", t, self)
        video_diag_inner = QWidget()
        vd_ly = QVBoxLayout(video_diag_inner)
        vd_ly.setSpacing(4)
        self._vd_session = QLabel("--")
        self._vd_sink = QLabel("--")
        self._vd_overlay = QLabel("--")
        vd_ly.addWidget(QLabel("会话类型 (XDG_SESSION_TYPE):"))
        vd_ly.addWidget(self._vd_session)
        vd_ly.addWidget(QLabel("Sink:"))
        vd_ly.addWidget(self._vd_sink)
        vd_ly.addWidget(QLabel("Overlay 嵌入支持:"))
        vd_ly.addWidget(self._vd_overlay)
        self._vd_error_btn = QPushButton("显示最近错误")
        self._vd_error_btn.setCheckable(True)
        self._vd_error_btn.setMinimumHeight(bh)
        self._vd_error_btn.toggled.connect(self._on_video_error_toggled)
        vd_ly.addWidget(self._vd_error_btn)
        self._vd_error_lbl = QLabel("")
        self._vd_error_lbl.setWordWrap(True)
        self._vd_error_lbl.setVisible(False)
        vd_ly.addWidget(self._vd_error_lbl)
        video_diag_section.set_content(video_diag_inner)
        inner_layout.addWidget(video_diag_section)
        self._video_diag_section = video_diag_section
        self._refresh_video_diagnostics()

        # 告警列表：折叠区块，默认折叠
        alarm_section = CollapsibleSection("告警列表", t, self)
        alarm_section.set_expanded(False)
        alarm_inner = QWidget()
        alarm_ly = QVBoxLayout(alarm_inner)
        alarm_ly.setSpacing(6)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("级别:"))
        self._severity_combo = QComboBox()
        self._severity_combo.addItems(["全部", "INFO", "WARN", "CRITICAL"])
        self._severity_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._severity_combo)
        filter_row.addStretch()
        ack_warn_btn = QPushButton("一键 Ack 当前所有 WARN")
        ack_warn_btn.setObjectName("warn")
        ack_warn_btn.setMinimumHeight(bh)
        ack_warn_btn.clicked.connect(self._on_ack_all_warn)
        filter_row.addWidget(ack_warn_btn)
        alarm_ly.addLayout(filter_row)
        self._alarm_table = QTableWidget(0, 5)
        self._alarm_table.setHorizontalHeaderLabels(["ID", "级别", "消息", "Ack", "操作"])
        self._alarm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._alarm_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._alarm_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._alarm_table.cellClicked.connect(self._on_alarm_cell_clicked)
        self._alarm_table.verticalHeader().setDefaultSectionSize(bh)
        alarm_ly.addWidget(self._alarm_table)
        alarm_section.set_content(alarm_inner)
        inner_layout.addWidget(alarm_section)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        if app_state:
            app_state.changed.connect(
                self._on_state_changed,
                Qt.ConnectionType.QueuedConnection,
            )
            app_state.alarms_changed.connect(
                self._on_alarms_changed,
                Qt.ConnectionType.QueuedConnection,
            )
            QTimer.singleShot(0, self._refresh_once)

    def _get_filtered_sorted_alarms(self) -> list[Alarm]:
        filtered = self._alarms
        if self._severity_filter is not None:
            filtered = [a for a in filtered if a.severity == self._severity_filter]
        return sorted(filtered, key=lambda a: a.last_seen_ts or 0, reverse=True)

    def _on_filter_changed(self, text: str) -> None:
        if text == "全部":
            self._severity_filter = None
        else:
            try:
                self._severity_filter = Severity(text)
            except ValueError:
                self._severity_filter = None
        self._refresh_alarm_table()

    def _on_state_changed(self, snap) -> None:
        if snap is None:
            return
        comm = snap.comm
        for row, (dot, err_lbl, last_lbl) in enumerate(self._slave_rows):
            sid = row + 1
            c = comm.get(sid)
            if c is None:
                dot.setProperty("severity", "unknown")
                err_lbl.setText("--")
                last_lbl.setText("--")
            else:
                dot.setProperty("severity", "ok" if c.online else "crit")
                err_lbl.setText(str(c.error_count))
                ts = getattr(c, "last_ok_ts", None) or 0.0
                last_lbl.setText(_format_ts_short(ts))
            dot.style().unpolish(dot)
            dot.style().polish(dot)

    def _on_alarms_changed(self, alarms: list) -> None:
        self._alarms = alarms if isinstance(alarms, list) else []
        self._refresh_alarm_table()

    def _refresh_alarm_table(self) -> None:
        alarms = self._get_filtered_sorted_alarms()
        self._alarm_table.setRowCount(len(alarms))
        for row, a in enumerate(alarms):
            if isinstance(a, Alarm):
                self._alarm_table.setItem(row, 0, QTableWidgetItem(a.id))
                self._alarm_table.setItem(row, 1, QTableWidgetItem(str(a.severity.value)))
                self._alarm_table.setItem(row, 2, QTableWidgetItem(f"{a.title}: {a.message}"))
                self._alarm_table.setItem(row, 3, QTableWidgetItem("已确认" if a.ack else "未确认"))
                btn = QPushButton("Ack")
                btn.setMinimumHeight(self._tokens.btn_h if self._tokens else 44)
                btn.setEnabled(not a.ack)
                btn.clicked.connect(lambda checked, aid=a.id: self._on_ack(aid))
                self._alarm_table.setCellWidget(row, 4, btn)
            else:
                for col in range(5):
                    self._alarm_table.setItem(row, col, QTableWidgetItem("--"))

    def _on_alarm_cell_clicked(self, row: int, col: int) -> None:
        if col == 4:
            return
        alarms = self._get_filtered_sorted_alarms()
        if 0 <= row < len(alarms):
            a = alarms[row]
            if isinstance(a, Alarm):
                dlg = AlarmDetailDialog(a, self)
                dlg.exec()

    def _on_ack(self, alarm_id: str) -> None:
        if self._alarm_controller:
            self._alarm_controller.ack(alarm_id)

    def _on_ack_all_warn(self) -> None:
        if self._alarm_controller:
            self._alarm_controller.ack_all_warn()

    def _refresh_video_diagnostics(self) -> None:
        diag = _get_video_diagnostics()
        self._vd_session.setText(diag.get("session_type", "--"))
        self._vd_sink.setText(diag.get("selected_sink", "--"))
        self._vd_overlay.setText("是" if diag.get("overlay_supported") else "否")
        err = (diag.get("last_error") or "").strip()
        self._vd_error_lbl.setText(err or "无")
        self._vd_error_btn.setText("显示最近错误" if not self._vd_error_btn.isChecked() else "收起最近错误")

    def _on_video_error_toggled(self, checked: bool) -> None:
        self._vd_error_lbl.setVisible(checked)
        self._vd_error_btn.setText("收起最近错误" if checked else "显示最近错误")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_video_diagnostics()

    def _refresh_once(self) -> None:
        if self._app_state:
            self._on_state_changed(self._app_state.get_snapshot())
        self._refresh_alarm_table()
        self._refresh_video_diagnostics()
