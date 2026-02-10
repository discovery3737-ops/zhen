"""外设页面 - 状态卡片 + 支腿 2×2 + 遮阳棚 2×2 + 外部照明大开关"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QGridLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer

from app.ui.pages.base import PageBase
from app.ui.layout_profile import LayoutTokens, get_tokens
from app.ui.widgets.long_press_button import LongPressButton
from app.devices.pdu import get_pdu_controller

_PDU_SLAVE_ID = 8

# PDU STATE: 0=Idle, 1=LegExt, 2=LegRet, 3=AwningExt, 4=AwningRet, 5=EStop, 6=Fault
PDU_STATE_NAMES = {
    0: "空闲",
    1: "支腿伸",
    2: "支腿收",
    3: "棚伸",
    4: "棚收",
    5: "急停",
    6: "故障",
}

LEG_EXTEND_STATE = 1
LEG_RETRACT_STATE = 2
AWNING_EXTEND_STATE = 3
AWNING_RETRACT_STATE = 4


def _limit_str(up: bool | None, down: bool | None) -> str:
    if up is None and down is None:
        return "--/--"
    u, d = ("✓" if up else "○"), ("✓" if down else "○")
    return f"UP:{u} DN:{d}"


def _awning_limit_str(ai: bool | None, ao: bool | None) -> str:
    if ai is None and ao is None:
        return "--/--"
    i, o = ("✓" if ai else "○"), ("✓" if ao else "○")
    return f"IN:{i} OUT:{o}"


class ExteriorPage(PageBase):
    """外设页：顶部状态卡 + 支腿 2×2 + 遮阳棚 2×2 + 外部照明。布局由 tokens 驱动。"""

    def __init__(self, app_state=None):
        super().__init__("外设")
        self._app_state = app_state
        self._tokens: LayoutTokens | None = get_tokens()
        t = self._tokens
        layout = self.layout()
        if layout is None:
            return

        while layout.count() > 0:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        g, p = (t.gap if t else 8), (t.pad_page if t else 10)

        # 固定头部：标题 + 关键状态（运行 / E-STOP / 故障）
        header = QWidget(objectName="pageHeader")
        header_ly = QVBoxLayout(header)
        header_ly.setSpacing(g // 2)
        header_ly.setContentsMargins(p, p, p, g)
        title = QLabel("外设")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_ly.addWidget(title)
        self._header_status_row = QHBoxLayout()
        self._header_run_label = QLabel("运行: 空闲", objectName="small")
        self._header_estop_label = QLabel("E-STOP: 正常", objectName="small")
        self._header_fault_label = QLabel("故障: --", objectName="small")
        self._header_status_row.addWidget(self._header_run_label)
        self._header_status_row.addWidget(self._header_estop_label)
        self._header_status_row.addWidget(self._header_fault_label)
        self._header_status_row.addStretch()
        header_ly.addLayout(self._header_status_row)
        layout.addWidget(header)

        scroll = QScrollArea(objectName="pageScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        ly = QVBoxLayout(inner)
        ly.setSpacing(g)
        ly.setContentsMargins(p, g, p, p)

        # 1) 状态卡片：限位、运行、E-STOP、故障码（紧凑两行）
        status_card = self._build_status_card()
        ly.addWidget(status_card)

        # 2) 支腿：2×2 大按钮
        leg_card = self._build_leg_card()
        ly.addWidget(leg_card)

        # 3) 遮阳棚：2×2 大按钮
        awning_card = self._build_awning_card()
        ly.addWidget(awning_card)

        # 4) 外部照明：独立一行大开关
        light_row = self._build_ext_light_row()
        ly.addLayout(light_row)

        ly.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        if app_state:
            app_state.changed.connect(
                self._on_state_changed,
                Qt.ConnectionType.QueuedConnection,
            )
            QTimer.singleShot(0, self._refresh_once)

    def _build_status_card(self) -> QFrame:
        """限位状态、运行状态、E-STOP、故障码，紧凑两行"""
        t = self._tokens
        g, p = (t.gap if t else 6), (t.pad_page if t else 10)
        card = QFrame(objectName="card")
        ly = QVBoxLayout(card)
        ly.setSpacing(g // 2)
        ly.setContentsMargins(p, p, p, p)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("支腿限位:", objectName="small"))
        self._leg_limit_label = QLabel("--/--")
        self._leg_limit_label.setObjectName("small")
        row1.addWidget(self._leg_limit_label)
        row1.addSpacing(12)
        row1.addWidget(QLabel("棚限位:", objectName="small"))
        self._awning_limit_label = QLabel("--/--")
        self._awning_limit_label.setObjectName("small")
        row1.addWidget(self._awning_limit_label)
        row1.addStretch()
        ly.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("运行:", objectName="small"))
        self._run_state_label = QLabel("空闲")
        self._run_state_label.setObjectName("small")
        row2.addWidget(self._run_state_label)
        row2.addSpacing(12)
        row2.addWidget(QLabel("E-STOP:", objectName="small"))
        self._estop_label = QLabel("正常")
        self._estop_label.setObjectName("small")
        row2.addWidget(self._estop_label)
        row2.addSpacing(12)
        row2.addWidget(QLabel("故障码:", objectName="small"))
        self._fault_label = QLabel("--")
        self._fault_label.setObjectName("small")
        row2.addWidget(self._fault_label)
        row2.addStretch()
        ly.addLayout(row2)

        return card

    def _build_leg_card(self) -> QFrame:
        """支腿 2×2：Extend / Retract / Stop / 留空"""
        t = self._tokens
        g, p, bhk = (t.gap if t else 8), (t.pad_card if t else 10), (t.btn_h_key if t else 52)
        card = QFrame(objectName="card")
        ly = QVBoxLayout(card)
        ly.setSpacing(g)
        ly.setContentsMargins(p, p, p, p)

        ly.addWidget(QLabel("支腿", objectName="accent"))

        grid = QGridLayout()
        self._leg_extend_btn = LongPressButton("伸出", tokens=t)
        self._leg_extend_btn.setHoldMs(1500)
        self._leg_extend_btn.confirmed.connect(self._on_leg_extend)
        self._leg_retract_btn = LongPressButton("收回", tokens=t)
        self._leg_retract_btn.setHoldMs(1500)
        self._leg_retract_btn.confirmed.connect(self._on_leg_retract)
        self._leg_stop_btn = LongPressButton("停止", tokens=t)
        self._leg_stop_btn.setHoldMs(1500)
        self._leg_stop_btn.setDanger(True)
        self._leg_stop_btn.confirmed.connect(self._on_leg_stop)

        grid.addWidget(self._leg_extend_btn, 0, 0)
        grid.addWidget(self._leg_retract_btn, 0, 1)
        grid.addWidget(self._leg_stop_btn, 1, 0)
        # 第 4 格留空
        ly.addLayout(grid)

        return card

    def _build_awning_card(self) -> QFrame:
        """遮阳棚 2×2：Extend / Retract / Stop / 留空"""
        t = self._tokens
        g, p = (t.gap if t else 8), (t.pad_card if t else 10)
        card = QFrame(objectName="card")
        ly = QVBoxLayout(card)
        ly.setSpacing(g)
        ly.setContentsMargins(p, p, p, p)

        ly.addWidget(QLabel("遮阳棚", objectName="accent"))

        grid = QGridLayout()
        self._awning_extend_btn = LongPressButton("伸出", tokens=t)
        self._awning_extend_btn.setHoldMs(1500)
        self._awning_extend_btn.confirmed.connect(self._on_awning_extend)
        self._awning_retract_btn = LongPressButton("收回", tokens=t)
        self._awning_retract_btn.setHoldMs(1500)
        self._awning_retract_btn.confirmed.connect(self._on_awning_retract)
        self._awning_stop_btn = LongPressButton("停止", tokens=t)
        self._awning_stop_btn.setHoldMs(1500)
        self._awning_stop_btn.setDanger(True)
        self._awning_stop_btn.confirmed.connect(self._on_awning_stop)

        grid.addWidget(self._awning_extend_btn, 0, 0)
        grid.addWidget(self._awning_retract_btn, 0, 1)
        grid.addWidget(self._awning_stop_btn, 1, 0)

        ly.addLayout(grid)

        return card

    def _build_ext_light_row(self) -> QHBoxLayout:
        """外部照明：独立一行大开关"""
        t = self._tokens
        bhk = t.btn_h_key if t else 52
        row = QHBoxLayout()
        row.addWidget(QLabel("外部照明", objectName="accent"))
        self._ext_light_btn = QPushButton("关")
        self._ext_light_btn.setCheckable(True)
        self._ext_light_btn.setMinimumHeight(bhk)
        self._ext_light_btn.clicked.connect(self._on_ext_light_clicked)
        row.addWidget(self._ext_light_btn, 1)
        return row

    def _refresh_once(self) -> None:
        if self._app_state:
            self._on_state_changed(self._app_state.get_snapshot())

    def _on_state_changed(self, snap) -> None:
        if snap is None:
            return
        pd = snap.pdu
        state = pd.pdu_state if pd.pdu_state is not None else 0
        leg_running = state in (LEG_EXTEND_STATE, LEG_RETRACT_STATE)
        awning_running = state in (AWNING_EXTEND_STATE, AWNING_RETRACT_STATE)
        estop_or_fault = state in (5, 6)

        # 状态卡
        ll = pd.leg_limits
        up = bool(ll[0]) if ll and len(ll) >= 1 else None
        down = bool(ll[1]) if ll and len(ll) >= 2 else None
        self._leg_limit_label.setText(_limit_str(up, down))

        al = pd.awning_limits
        ai = bool(al[0]) if al and len(al) >= 1 else None
        ao = bool(al[1]) if al and len(al) >= 2 else None
        self._awning_limit_label.setText(_awning_limit_str(ai, ao))

        state_name = PDU_STATE_NAMES.get(state, str(state))
        run_text = (state_name + "…") if (leg_running or awning_running) else "空闲"
        self._run_state_label.setText(run_text)
        if hasattr(self, "_header_run_label"):
            self._header_run_label.setText(f"运行: {run_text}")

        estop = pd.e_stop
        estop_text = "已按下" if estop else "正常"
        self._estop_label.setText(estop_text)
        if hasattr(self, "_header_estop_label"):
            self._header_estop_label.setText(f"E-STOP: {estop_text}")
            self._header_estop_label.setProperty("severity", "crit" if estop else "")
            self._header_estop_label.style().unpolish(self._header_estop_label)
            self._header_estop_label.style().polish(self._header_estop_label)
        self._estop_label.setProperty("severity", "crit" if estop else "")
        self._estop_label.style().unpolish(self._estop_label)
        self._estop_label.style().polish(self._estop_label)
        fc = pd.pdu_fault_code
        fault_text = str(fc) if fc is not None else "--"
        self._fault_label.setText(fault_text)
        if hasattr(self, "_header_fault_label"):
            self._header_fault_label.setText(f"故障: {fault_text}")

        # 支腿：运行时禁用相反方向，Stop 仅运行中可用
        self._leg_extend_btn.setEnabled(not estop_or_fault and state != LEG_RETRACT_STATE)
        self._leg_retract_btn.setEnabled(not estop_or_fault and state != LEG_EXTEND_STATE)
        self._leg_stop_btn.setEnabled(leg_running)

        # 遮阳棚：同上
        self._awning_extend_btn.setEnabled(not estop_or_fault and state != AWNING_RETRACT_STATE)
        self._awning_retract_btn.setEnabled(not estop_or_fault and state != AWNING_EXTEND_STATE)
        self._awning_stop_btn.setEnabled(awning_running)

        # 外部照明
        ext_on = pd.ext_light_on if pd.ext_light_on is not None else False
        self._ext_light_btn.blockSignals(True)
        self._ext_light_btn.setChecked(ext_on)
        self._ext_light_btn.setText("开" if ext_on else "关")
        self._ext_light_btn.blockSignals(False)

    def _ensure_pdu_online(self) -> bool:
        if not self._app_state:
            return True
        comm = self._app_state.get_snapshot().comm.get(_PDU_SLAVE_ID)
        if not (comm and comm.online):
            QMessageBox.warning(self, "设备离线", "设备离线，无法写入。")
            return False
        return True

    def _on_leg_extend(self) -> None:
        if not self._ensure_pdu_online():
            return
        ctrl = get_pdu_controller()
        if ctrl:
            ctrl.leg_extend()

    def _on_leg_retract(self) -> None:
        if not self._ensure_pdu_online():
            return
        ctrl = get_pdu_controller()
        if ctrl:
            ctrl.leg_retract()

    def _on_leg_stop(self) -> None:
        if not self._ensure_pdu_online():
            return
        ctrl = get_pdu_controller()
        if ctrl:
            ctrl.leg_stop()

    def _on_awning_extend(self) -> None:
        if not self._ensure_pdu_online():
            return
        ctrl = get_pdu_controller()
        if ctrl:
            ctrl.awning_extend()

    def _on_awning_retract(self) -> None:
        if not self._ensure_pdu_online():
            return
        ctrl = get_pdu_controller()
        if ctrl:
            ctrl.awning_retract()

    def _on_awning_stop(self) -> None:
        if not self._ensure_pdu_online():
            return
        ctrl = get_pdu_controller()
        if ctrl:
            ctrl.awning_stop()

    def set_tokens(self, tokens: LayoutTokens) -> None:
        super().set_tokens(tokens)
        self._tokens = tokens
        layout = self.layout()
        if layout and layout.count() >= 2:
            header = layout.itemAt(0).widget()
            if isinstance(header, QWidget) and header.layout():
                header.layout().setSpacing(tokens.gap)
                header.layout().setContentsMargins(
                    tokens.pad_page, tokens.pad_page, tokens.pad_page, tokens.gap
                )
            scroll = layout.itemAt(1).widget()
            if isinstance(scroll, QScrollArea) and scroll.widget() and scroll.widget().layout():
                scroll.widget().layout().setSpacing(tokens.gap)
                scroll.widget().layout().setContentsMargins(
                    tokens.pad_page, tokens.gap, tokens.pad_page, tokens.pad_page
                )
        for lp in self.findChildren(LongPressButton):
            lp.set_tokens(tokens)
        if hasattr(self, "_ext_light_btn"):
            self._ext_light_btn.setMinimumHeight(tokens.btn_h_key)

    def _on_ext_light_clicked(self, checked: bool) -> None:
        if not self._ensure_pdu_online():
            return
        ctrl = get_pdu_controller()
        if ctrl:
            ctrl.set_ext_light_on(checked)
