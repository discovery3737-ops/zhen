"""动力页面 - 布局由 LayoutTokens 驱动；状态/SOC 提示用 severity 动态属性 + QSS，无内联 setStyleSheet；LongPress 用 btn_h_key，折叠按钮用 btn_h。"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer

from app.ui.pages.base import PageBase
from app.ui.widgets.long_press_button import LongPressButton
from app.ui.layout_profile import LayoutTokens, get_tokens
from app.devices.pdu import get_pdu_controller

INV_STATE_NAMES = {0: "关", 1: "开", 2: "待机", 3: "故障"}
SOC_WARN_THRESH = 200   # 20%
SOC_CRIT_THRESH = 100   # 10%


def _soc_str(x10: int | None) -> str:
    if x10 is None:
        return "--.-"
    return f"{x10 / 10:.1f}"


def _voltage_str(x100: int | None) -> str:
    if x100 is None:
        return "--.-"
    return f"{x100 / 100:.2f}"


def _power_str(w: int | None) -> str:
    if w is None:
        return "--"
    return str(w)


def _apply_severity(widget: QLabel, severity: str | None) -> None:
    if severity:
        widget.setProperty("severity", severity)
    else:
        widget.setProperty("severity", "")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class PowerPage(PageBase):
    """动力页：首屏 3 卡片（电池 | 220V | 冰箱）+ 更多详情折叠。布局由 tokens 驱动。"""

    def __init__(self, app_state=None):
        super().__init__("动力")
        self._app_state = app_state
        self._tokens: LayoutTokens | None = get_tokens()
        layout = self.layout()
        if layout is None:
            return

        while layout.count() > 0:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        t = self._tokens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        inner = QWidget()
        ly = QVBoxLayout(inner)
        ly.setSpacing(t.gap)
        ly.setContentsMargins(t.pad_page, t.pad_page, t.pad_page, t.pad_page)

        title = QLabel("动力")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(title)

        card1 = self._build_battery_card()
        ly.addWidget(card1)
        card2 = self._build_220v_card()
        ly.addWidget(card2)
        card3 = self._build_fridge_card()
        ly.addWidget(card3)

        self._detail_widget, self._detail_btn = self._build_collapsible_detail()
        ly.addWidget(self._detail_btn)
        ly.addWidget(self._detail_widget)

        ly.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        if app_state:
            app_state.changed.connect(
                self._on_state_changed,
                Qt.ConnectionType.QueuedConnection,
            )
            QTimer.singleShot(0, self._refresh_once)

    def set_tokens(self, t: LayoutTokens) -> None:
        self._tokens = t
        layout = self.layout()
        if layout is None or not t:
            return
        if layout.count() > 0:
            w = layout.itemAt(0).widget()
            if isinstance(w, QScrollArea) and w.widget():
                inner_ly = w.widget().layout()
                if inner_ly:
                    inner_ly.setSpacing(t.gap)
                    inner_ly.setContentsMargins(t.pad_page, t.pad_page, t.pad_page, t.pad_page)
        for w in self.findChildren(LongPressButton):
            w.setMinimumHeight(t.btn_h_key)
        for w in self.findChildren(QPushButton):
            if w.isCheckable():
                txt = w.text()
                if "更多详情" in txt or "收起" in txt:
                    w.setMinimumHeight(t.btn_h)
                    break

    def _build_battery_card(self) -> QFrame:
        t = self._tokens
        card = QFrame(objectName="card")
        ly = QVBoxLayout(card)
        ly.setSpacing(t.gap)
        ly.setContentsMargins(t.pad_card, t.pad_card, t.pad_card, t.pad_card)
        ly.addWidget(QLabel("电池", objectName="accent"))
        self._soc_label = QLabel("--.- %")
        self._soc_label.setObjectName("bigNumber")
        ly.addWidget(self._soc_label)
        row = QHBoxLayout()
        self._batt_v_label = QLabel("--.- V")
        self._batt_v_label.setObjectName("small")
        self._batt_i_label = QLabel("--.- A")
        self._batt_i_label.setObjectName("small")
        self._batt_p_label = QLabel("-- W")
        self._batt_p_label.setObjectName("small")
        row.addWidget(self._batt_v_label)
        row.addWidget(self._batt_i_label)
        row.addWidget(self._batt_p_label)
        row.addStretch()
        ly.addLayout(row)
        return card

    def _build_220v_card(self) -> QFrame:
        t = self._tokens
        card = QFrame(objectName="card")
        ly = QVBoxLayout(card)
        ly.setSpacing(t.gap)
        ly.setContentsMargins(t.pad_card, t.pad_card, t.pad_card, t.pad_card)
        ly.addWidget(QLabel("220V 输出总控", objectName="accent"))

        row_status = QHBoxLayout()
        row_status.addWidget(QLabel("命令:"))
        self._inv_cmd_label = QLabel("--")
        row_status.addWidget(self._inv_cmd_label)
        row_status.addWidget(QLabel("反馈:"))
        self._inv_fb_label = QLabel("--")
        row_status.addWidget(self._inv_fb_label)
        row_status.addStretch()
        ly.addLayout(row_status)

        self._inv_mismatch_label = QLabel("")
        self._inv_mismatch_label.setObjectName("small")
        self._inv_mismatch_label.setWordWrap(True)
        ly.addWidget(self._inv_mismatch_label)

        self._inv_disable_reason = QLabel("")
        self._inv_disable_reason.setObjectName("small")
        self._inv_disable_reason.setWordWrap(True)
        ly.addWidget(self._inv_disable_reason)

        btn_row = QHBoxLayout()
        self._ac_close_btn = LongPressButton("长按合闸")
        self._ac_close_btn.setHoldMs(2000)
        self._ac_close_btn.setDanger(True)
        self._ac_close_btn.setMinimumHeight(t.btn_h_key)
        self._ac_close_btn.confirmed.connect(lambda: self._on_ac_set(True))
        self._ac_open_btn = LongPressButton("长按分闸")
        self._ac_open_btn.setHoldMs(2000)
        self._ac_open_btn.setDanger(True)
        self._ac_open_btn.setMinimumHeight(t.btn_h_key)
        self._ac_open_btn.confirmed.connect(lambda: self._on_ac_set(False))
        btn_row.addWidget(self._ac_close_btn)
        btn_row.addWidget(self._ac_open_btn)
        ly.addLayout(btn_row)
        return card

    def _build_fridge_card(self) -> QFrame:
        t = self._tokens
        card = QFrame(objectName="card")
        ly = QVBoxLayout(card)
        ly.setSpacing(t.gap)
        ly.setContentsMargins(t.pad_card, t.pad_card, t.pad_card, t.pad_card)
        ly.addWidget(QLabel("冰箱 24V", objectName="accent"))

        row_status = QHBoxLayout()
        row_status.addWidget(QLabel("状态:"))
        self._fridge_status_label = QLabel("--")
        row_status.addWidget(self._fridge_status_label)
        row_status.addStretch()
        ly.addLayout(row_status)

        self._fridge_soc_hint = QLabel("")
        self._fridge_soc_hint.setWordWrap(True)
        self._fridge_soc_hint.setObjectName("small")
        ly.addWidget(self._fridge_soc_hint)

        btn_row = QHBoxLayout()
        self._fridge_on_btn = LongPressButton("长按开启")
        self._fridge_on_btn.setHoldMs(2000)
        self._fridge_on_btn.setMinimumHeight(t.btn_h_key)
        self._fridge_on_btn.confirmed.connect(lambda: self._on_fridge_set(True))
        self._fridge_off_btn = LongPressButton("长按关闭")
        self._fridge_off_btn.setHoldMs(2000)
        self._fridge_off_btn.setDanger(True)
        self._fridge_off_btn.setMinimumHeight(t.btn_h_key)
        self._fridge_off_btn.confirmed.connect(lambda: self._on_fridge_set(False))
        btn_row.addWidget(self._fridge_on_btn)
        btn_row.addWidget(self._fridge_off_btn)
        ly.addLayout(btn_row)
        return card

    def _build_collapsible_detail(self) -> tuple[QWidget, QPushButton]:
        t = self._tokens
        content = QFrame(objectName="card")
        ly = QVBoxLayout(content)
        ly.setContentsMargins(t.pad_card, t.pad_card, t.pad_card, t.pad_card)
        ly.setSpacing(t.gap)

        ly.addWidget(QLabel("逆变器详情", objectName="accent"))
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("状态:"))
        self._inv_state_label = QLabel("--")
        row1.addWidget(self._inv_state_label)
        row1.addStretch()
        ly.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("功率:"))
        self._inv_p_label = QLabel("-- W")
        row2.addWidget(self._inv_p_label)
        row2.addStretch()
        ly.addLayout(row2)
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("交流电压:"))
        self._inv_v_label = QLabel("-- V")
        row3.addWidget(self._inv_v_label)
        row3.addStretch()
        ly.addLayout(row3)
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("故障:"))
        self._inv_fault_label = QLabel("--")
        row4.addWidget(self._inv_fault_label)
        row4.addStretch()
        ly.addLayout(row4)

        self._soc_hint = QLabel("")
        self._soc_hint.setWordWrap(True)
        self._soc_hint.setObjectName("small")
        ly.addWidget(self._soc_hint)

        btn = QPushButton("▼ 更多详情")
        btn.setMinimumHeight(t.btn_h)
        btn.setCheckable(True)
        btn.setChecked(False)
        content.setVisible(False)

        def _on_toggle(checked):
            content.setVisible(checked)
            btn.setText("▲ 收起" if checked else "▼ 更多详情")

        btn.clicked.connect(_on_toggle)
        return content, btn

    def _refresh_once(self) -> None:
        if self._app_state:
            self._on_state_changed(self._app_state.get_snapshot())

    def _on_state_changed(self, snap) -> None:
        if snap is None:
            return
        p = snap.power
        pd = snap.pdu
        comm4 = snap.comm.get(4)
        power_online = comm4.online if comm4 else False
        soc_x10 = p.soc_x10 if p.soc_x10 is not None else 999

        self._soc_label.setText(f"{_soc_str(p.soc_x10)} %")
        self._batt_v_label.setText(f"{_voltage_str(p.batt_v_x100)} V")
        self._batt_i_label.setText(f"{_voltage_str(p.batt_i_x100)} A")
        self._batt_p_label.setText(f"{_power_str(p.batt_p_w)} W")

        inv_on = pd.inv_ac_out_on if pd.inv_ac_out_on is not None else False
        inv_fb = pd.inv_ac_out_fb if pd.inv_ac_out_fb is not None else False
        self._inv_cmd_label.setText("合闸" if inv_on else "分闸")
        self._inv_fb_label.setText("有电" if inv_fb else "无电")
        mismatch = inv_on != inv_fb
        self._inv_mismatch_label.setText("⚠ 反馈不一致" if mismatch else "")
        if mismatch:
            _apply_severity(self._inv_mismatch_label, "crit")
        else:
            _apply_severity(self._inv_mismatch_label, None)

        inv_fault = p.inv_fault if p.inv_fault is not None else False
        ac_disabled = not power_online or inv_fault
        if ac_disabled:
            reasons = []
            if not power_online:
                reasons.append("Slave04 离线")
            if inv_fault:
                reasons.append("逆变器故障")
            self._inv_disable_reason.setText("禁用: " + " / ".join(reasons))
        else:
            self._inv_disable_reason.setText("")
        _apply_severity(self._inv_disable_reason, None)
        self._ac_close_btn.setEnabled(not ac_disabled and not inv_on)
        self._ac_open_btn.setEnabled(not ac_disabled and inv_on)

        fridge_on = pd.fridge_24v_on if pd.fridge_24v_on is not None else False
        self._fridge_status_label.setText("开" if fridge_on else "关")
        self._fridge_on_btn.setEnabled(not fridge_on)
        self._fridge_off_btn.setEnabled(fridge_on)

        if soc_x10 < SOC_CRIT_THRESH:
            self._fridge_soc_hint.setText("⚠ SOC 低于 10%，建议及时充电")
            _apply_severity(self._fridge_soc_hint, "crit")
        elif soc_x10 < SOC_WARN_THRESH:
            self._fridge_soc_hint.setText("⚠ SOC 低于 20%，注意电量")
            _apply_severity(self._fridge_soc_hint, "warn")
        else:
            self._fridge_soc_hint.setText("")
            _apply_severity(self._fridge_soc_hint, None)

        inv_state = INV_STATE_NAMES.get(p.inv_state, str(p.inv_state)) if p.inv_state is not None else "--"
        self._inv_state_label.setText(inv_state)
        self._inv_p_label.setText(f"{_power_str(p.inv_ac_p_w)} W")
        inv_v = f"{p.inv_ac_v_x10 / 10:.1f}" if p.inv_ac_v_x10 is not None else "--"
        self._inv_v_label.setText(f"{inv_v} V")
        self._inv_fault_label.setText("是" if inv_fault else "否")

        if soc_x10 < SOC_CRIT_THRESH:
            self._soc_hint.setText("⚠ SOC 低于 10%，建议充电")
            _apply_severity(self._soc_hint, "crit")
        elif soc_x10 < SOC_WARN_THRESH:
            self._soc_hint.setText("⚠ SOC 低于 20%，注意电量")
            _apply_severity(self._soc_hint, "warn")
        else:
            self._soc_hint.setText("")
            _apply_severity(self._soc_hint, None)

    def _on_ac_set(self, on: bool) -> None:
        ctrl = get_pdu_controller()
        if ctrl:
            ctrl.set_inv_ac_out_on(on)

    def _on_fridge_set(self, on: bool) -> None:
        ctrl = get_pdu_controller()
        if ctrl:
            ctrl.set_fridge_24v_on(on)
