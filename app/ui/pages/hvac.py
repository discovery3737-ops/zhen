"""空调页面 - WVGA 单列卡片布局：HVAC 快速控制 | 危险控制+状态灯 | Webasto | 可折叠高级参数"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QComboBox,
    QSlider,
    QPushButton,
    QScrollArea,
    QGridLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer

from app.ui.pages.base import PageBase
from app.ui.widgets.long_press_button import LongPressButton
from app.devices.hvac import get_hvac_controller
from app.devices.webasto import get_webasto_controller

_HVAC_SLAVE_ID = 1
_WEBASTO_SLAVE_ID = 2

# Slave01 MODE: Off=0, Cool=1, Vent=2, Auto=3
MODE_OFF, MODE_COOL, MODE_VENT, MODE_AUTO = 0, 1, 2, 3
MODE_ITEMS = [
    ("Off", MODE_OFF),
    ("Cool", MODE_COOL),
    ("Vent", MODE_VENT),
    ("Auto", MODE_AUTO),
]


def _temp_str(x10: int | None) -> str:
    if x10 is None:
        return "--.-"
    return f"{x10 / 10:.1f}"


def _pwm_str(x10: int | None) -> str:
    if x10 is None:
        return "--"
    return f"{x10 / 10:.1f}%"


class StatusLight(QLabel):
    """红绿灯指示：绿=OK，红=异常，灰=未知"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.set_ok(None)

    def set_ok(self, ok: bool | None) -> None:
        if ok is None:
            self.setStyleSheet("background-color: #9CA3AF; border-radius: 10px;")
        elif ok:
            self.setStyleSheet("background-color: #22C55E; border-radius: 10px;")
        else:
            self.setStyleSheet("background-color: #EF4444; border-radius: 10px;")


class HvacPage(PageBase):
    """空调页：单列 3 卡片 + 可折叠高级参数，WVGA 布局"""

    def __init__(self, app_state=None):
        super().__init__("空调")
        self._app_state = app_state
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
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        inner = QWidget()
        ly = QVBoxLayout(inner)
        ly.setSpacing(8)
        ly.setContentsMargins(10, 10, 10, 10)

        title = QLabel("空调")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(title)

        # Card 1: HVAC 快速控制
        card1 = self._build_card1_hvac_quick()
        ly.addWidget(card1)

        # Card 2: 危险控制 + 三色状态灯
        card2 = self._build_card2_hvac_danger()
        ly.addWidget(card2)

        # Card 3: Webasto
        card3 = self._build_card3_webasto()
        ly.addWidget(card3)

        # 可折叠：实际PWM / 故障码详情（默认收起）
        self._advanced_widget, self._advanced_btn = self._build_collapsible_advanced()
        ly.addWidget(self._advanced_btn)
        ly.addWidget(self._advanced_widget)

        ly.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        if app_state:
            app_state.changed.connect(
                self._on_state_changed,
                Qt.ConnectionType.QueuedConnection,
            )
            QTimer.singleShot(0, self._refresh_once)

    def _build_card1_hvac_quick(self) -> QFrame:
        """Card 1: MODE、目标温度 +/-、风机档位"""
        card = QFrame(objectName="card")
        ly = QVBoxLayout(card)
        ly.setSpacing(10)
        ly.setContentsMargins(10, 10, 10, 10)

        ly.addWidget(QLabel("HVAC 快速控制", objectName="accent"))

        # MODE
        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("MODE"))
        self._mode_combo = QComboBox()
        self._mode_combo.setMinimumHeight(44)
        for label, val in MODE_ITEMS:
            self._mode_combo.addItem(label, val)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        row_mode.addWidget(self._mode_combo, 1)
        ly.addLayout(row_mode)

        # 目标温度
        row_temp = QHBoxLayout()
        row_temp.addWidget(QLabel("目标温度"))
        self._temp_down = QPushButton("-")
        self._temp_down.setMinimumSize(44, 44)
        self._temp_down.clicked.connect(self._on_temp_down)
        self._temp_label = QLabel("--.- °C")
        self._temp_label.setMinimumWidth(64)
        self._temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._temp_up = QPushButton("+")
        self._temp_up.setMinimumSize(44, 44)
        self._temp_up.clicked.connect(self._on_temp_up)
        row_temp.addWidget(self._temp_down)
        row_temp.addWidget(self._temp_label, 1)
        row_temp.addWidget(self._temp_up)
        ly.addLayout(row_temp)

        self._temp_slider = QSlider(Qt.Orientation.Horizontal)
        self._temp_slider.setRange(150, 350)
        self._temp_slider.setValue(240)
        self._temp_slider.valueChanged.connect(self._on_temp_slider_changed)
        ly.addWidget(self._temp_slider)

        # 风机档位
        ly.addWidget(QLabel("蒸发风机"))
        self._evap_level = QSlider(Qt.Orientation.Horizontal)
        self._evap_level.setRange(0, 3)
        self._evap_level.setPageStep(1)
        self._evap_level.valueChanged.connect(self._on_evap_level_changed)
        ly.addWidget(self._evap_level)

        ly.addWidget(QLabel("冷凝风机"))
        self._cond_level = QSlider(Qt.Orientation.Horizontal)
        self._cond_level.setRange(0, 3)
        self._cond_level.setPageStep(1)
        self._cond_level.valueChanged.connect(self._on_cond_level_changed)
        ly.addWidget(self._cond_level)

        return card

    def _build_card2_hvac_danger(self) -> QFrame:
        """Card 2: COMP_ENABLE LongPress、AC_ENABLE 开关 + HP/LP/冷媒 三色灯"""
        card = QFrame(objectName="card")
        ly = QVBoxLayout(card)
        ly.setSpacing(10)
        ly.setContentsMargins(10, 10, 10, 10)

        ly.addWidget(QLabel("危险控制", objectName="accent"))

        # AC_ENABLE
        row_ac = QHBoxLayout()
        row_ac.addWidget(QLabel("AC 使能"))
        self._ac_enable = QPushButton("关")
        self._ac_enable.setCheckable(True)
        self._ac_enable.setMinimumHeight(44)
        self._ac_enable.clicked.connect(self._on_ac_enable_clicked)
        row_ac.addWidget(self._ac_enable, 1)
        ly.addLayout(row_ac)

        # COMP_ENABLE LongPress
        row_comp = QHBoxLayout()
        row_comp.addWidget(QLabel("压缩机"))
        self._comp_enable = LongPressButton("长按开启压缩机")
        self._comp_enable.setDanger(True)
        self._comp_enable.setHoldMs(2000)
        self._comp_enable.setMinimumHeight(52)
        self._comp_enable.confirmed.connect(self._on_comp_enable_confirmed)
        row_comp.addWidget(self._comp_enable, 1)
        ly.addLayout(row_comp)

        # 三色状态灯
        row_lights = QHBoxLayout()
        row_lights.addWidget(QLabel("HP:"))
        self._hp_ok = StatusLight()
        row_lights.addWidget(self._hp_ok)
        row_lights.addWidget(QLabel("LP:"))
        self._lp_ok = StatusLight()
        row_lights.addWidget(self._lp_ok)
        row_lights.addWidget(QLabel("冷媒:"))
        self._refrig_ok = StatusLight()
        row_lights.addWidget(self._refrig_ok)
        row_lights.addStretch()
        ly.addLayout(row_lights)

        return card

    def _build_card3_webasto(self) -> QFrame:
        """Card 3: 启停 LongPress、目标水温、水泵、状态/故障"""
        card = QFrame(objectName="card")
        ly = QVBoxLayout(card)
        ly.setSpacing(10)
        ly.setContentsMargins(10, 10, 10, 10)

        ly.addWidget(QLabel("Webasto", objectName="accent"))

        # 加热器 LongPress
        row_heater = QHBoxLayout()
        row_heater.addWidget(QLabel("加热器"))
        self._heater_on_btn = LongPressButton("长按开启")
        self._heater_on_btn.setHoldMs(2000)
        self._heater_on_btn.setMinimumHeight(52)
        self._heater_on_btn.confirmed.connect(lambda: self._on_heater_set(True))
        self._heater_off_btn = LongPressButton("长按关闭")
        self._heater_off_btn.setHoldMs(2000)
        self._heater_off_btn.setDanger(True)
        self._heater_off_btn.setMinimumHeight(52)
        self._heater_off_btn.confirmed.connect(lambda: self._on_heater_set(False))
        row_heater.addWidget(self._heater_on_btn)
        row_heater.addWidget(self._heater_off_btn)
        ly.addLayout(row_heater)

        # 目标水温
        row_wt = QHBoxLayout()
        row_wt.addWidget(QLabel("目标水温"))
        self._wt_down = QPushButton("-")
        self._wt_down.setMinimumSize(44, 44)
        self._wt_down.clicked.connect(self._on_wt_down)
        self._wt_label = QLabel("--.- °C")
        self._wt_label.setMinimumWidth(64)
        self._wt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wt_up = QPushButton("+")
        self._wt_up.setMinimumSize(44, 44)
        self._wt_up.clicked.connect(self._on_wt_up)
        row_wt.addWidget(self._wt_down)
        row_wt.addWidget(self._wt_label, 1)
        row_wt.addWidget(self._wt_up)
        ly.addLayout(row_wt)

        self._wt_slider = QSlider(Qt.Orientation.Horizontal)
        self._wt_slider.setRange(300, 850)
        self._wt_slider.setValue(600)
        self._wt_slider.valueChanged.connect(self._on_wt_slider_changed)
        ly.addWidget(self._wt_slider)

        # 水泵
        row_pump = QHBoxLayout()
        row_pump.addWidget(QLabel("水循环泵"))
        self._pump_on = QPushButton("关")
        self._pump_on.setCheckable(True)
        self._pump_on.setMinimumHeight(44)
        self._pump_on.clicked.connect(self._on_pump_clicked)
        row_pump.addWidget(self._pump_on, 1)
        ly.addLayout(row_pump)

        # 状态 / 故障 / 当前水温
        grid = QGridLayout()
        grid.addWidget(QLabel("加热状态"), 0, 0)
        self._heater_state_label = QLabel("--")
        grid.addWidget(self._heater_state_label, 0, 1)
        grid.addWidget(QLabel("故障码"), 1, 0)
        self._web_fault_label = QLabel("--")
        grid.addWidget(self._web_fault_label, 1, 1)
        grid.addWidget(QLabel("当前水温"), 2, 0)
        self._water_temp_label = QLabel("--.- °C")
        grid.addWidget(self._water_temp_label, 2, 1)
        ly.addLayout(grid)

        return card

    def _build_collapsible_advanced(self) -> tuple[QWidget, QPushButton]:
        """可折叠区域：故障码、压缩机/蒸发/冷凝 PWM（默认收起）"""
        content = QFrame(objectName="card")
        content_ly = QVBoxLayout(content)
        content_ly.setContentsMargins(10, 10, 10, 10)
        content_ly.setSpacing(8)

        grid = QGridLayout()
        grid.addWidget(QLabel("故障码"), 0, 0)
        self._fault_label = QLabel("--")
        grid.addWidget(self._fault_label, 0, 1)
        grid.addWidget(QLabel("压缩机PWM"), 1, 0)
        self._comp_pwm_label = QLabel("--")
        grid.addWidget(self._comp_pwm_label, 1, 1)
        grid.addWidget(QLabel("蒸发PWM"), 2, 0)
        self._evap_pwm_label = QLabel("--")
        grid.addWidget(self._evap_pwm_label, 2, 1)
        grid.addWidget(QLabel("冷凝PWM"), 3, 0)
        self._cond_pwm_label = QLabel("--")
        grid.addWidget(self._cond_pwm_label, 3, 1)
        content_ly.addLayout(grid)

        btn = QPushButton("▼ 实际PWM / 故障码详情")
        btn.setMinimumHeight(44)
        btn.setCheckable(True)
        btn.setChecked(False)
        content.setVisible(False)

        def _on_toggle(checked):
            content.setVisible(checked)
            btn.setText("▲ 收起" if checked else "▼ 实际PWM / 故障码详情")

        btn.clicked.connect(_on_toggle)

        return content, btn

    def _refresh_once(self) -> None:
        if self._app_state:
            self._on_state_changed(self._app_state.get_snapshot())

    def _on_state_changed(self, snap) -> None:
        if snap is None:
            return
        h = snap.hvac
        w = snap.webasto

        # HVAC
        mode = h.mode if h.mode is not None else MODE_OFF
        idx = self._mode_combo.findData(mode)
        if idx >= 0 and self._mode_combo.currentIndex() != idx:
            self._mode_combo.blockSignals(True)
            self._mode_combo.setCurrentIndex(idx)
            self._mode_combo.blockSignals(False)

        if h.target_temp_x10 is not None:
            self._temp_slider.blockSignals(True)
            self._temp_slider.setValue(max(150, min(350, h.target_temp_x10)))
            self._temp_slider.blockSignals(False)
        self._temp_label.setText(f"{_temp_str(h.target_temp_x10)} °C")

        if h.evap_fan_level is not None:
            self._evap_level.blockSignals(True)
            self._evap_level.setValue(h.evap_fan_level)
            self._evap_level.blockSignals(False)
        if h.cond_fan_level is not None:
            self._cond_level.blockSignals(True)
            self._cond_level.setValue(h.cond_fan_level)
            self._cond_level.blockSignals(False)

        ac_on = h.ac_enable if h.ac_enable is not None else False
        self._ac_enable.blockSignals(True)
        self._ac_enable.setChecked(ac_on)
        self._ac_enable.setText("开" if ac_on else "关")
        self._ac_enable.blockSignals(False)

        self._hp_ok.set_ok(h.hp_ok)
        self._lp_ok.set_ok(h.lp_ok)
        self._refrig_ok.set_ok(h.refrig_ok)
        self._fault_label.setText(str(h.hvac_fault_code) if h.hvac_fault_code is not None else "--")
        self._comp_pwm_label.setText(_pwm_str(h.comp_pwm_act_x10))
        self._evap_pwm_label.setText(_pwm_str(h.evap_pwm_act_x10))
        self._cond_pwm_label.setText(_pwm_str(h.cond_pwm_act_x10))

        # Webasto
        heater_on = w.heater_on if w.heater_on is not None else False
        self._heater_on_btn.setEnabled(not heater_on)
        self._heater_off_btn.setEnabled(heater_on)

        if w.target_water_temp_x10 is not None:
            self._wt_slider.blockSignals(True)
            self._wt_slider.setValue(max(300, min(850, w.target_water_temp_x10)))
            self._wt_slider.blockSignals(False)
        self._wt_label.setText(f"{_temp_str(w.target_water_temp_x10)} °C")

        pump_on = w.hydronic_pump_on if w.hydronic_pump_on is not None else False
        self._pump_on.blockSignals(True)
        self._pump_on.setChecked(pump_on)
        self._pump_on.setText("开" if pump_on else "关")
        self._pump_on.blockSignals(False)

        self._water_temp_label.setText(f"{_temp_str(w.water_temp_x10)} °C")
        state_map = {0: "关", 1: "预热", 2: "点火", 3: "运行", 4: "冷却", 5: "锁定"}
        self._heater_state_label.setText(
            state_map.get(w.heater_state, str(w.heater_state)) if w.heater_state is not None else "--"
        )
        self._web_fault_label.setText(str(w.web_fault_code) if w.web_fault_code is not None else "--")

    def _ensure_online(self, slave_id: int) -> bool:
        if not self._app_state:
            return True
        comm = self._app_state.get_snapshot().comm.get(slave_id)
        if not (comm and comm.online):
            QMessageBox.warning(self, "设备离线", "设备离线，无法写入。")
            return False
        return True

    def _on_mode_changed(self, index: int) -> None:
        val = self._mode_combo.currentData()
        if val is not None and self._ensure_online(_HVAC_SLAVE_ID):
            ctrl = get_hvac_controller()
            if ctrl:
                ctrl.set_mode(val)

    def _on_temp_down(self) -> None:
        if not self._ensure_online(_HVAC_SLAVE_ID):
            return
        snap = self._app_state.get_snapshot() if self._app_state else None
        cur = snap.hvac.target_temp_x10 if snap and snap.hvac.target_temp_x10 is not None else 240
        new = max(150, cur - 5)
        ctrl = get_hvac_controller()
        if ctrl:
            ctrl.set_target_temp_x10(new)

    def _on_temp_up(self) -> None:
        if not self._ensure_online(_HVAC_SLAVE_ID):
            return
        snap = self._app_state.get_snapshot() if self._app_state else None
        cur = snap.hvac.target_temp_x10 if snap and snap.hvac.target_temp_x10 is not None else 240
        new = min(350, cur + 5)
        ctrl = get_hvac_controller()
        if ctrl:
            ctrl.set_target_temp_x10(new)

    def _on_temp_slider_changed(self, value: int) -> None:
        self._temp_label.setText(f"{value / 10:.1f} °C")
        if not self._ensure_online(_HVAC_SLAVE_ID):
            return
        ctrl = get_hvac_controller()
        if ctrl:
            ctrl.set_target_temp_x10(value)

    def _on_evap_level_changed(self, value: int) -> None:
        if not self._ensure_online(_HVAC_SLAVE_ID):
            return
        ctrl = get_hvac_controller()
        if ctrl:
            ctrl.set_evap_fan_level(value)

    def _on_cond_level_changed(self, value: int) -> None:
        if not self._ensure_online(_HVAC_SLAVE_ID):
            return
        ctrl = get_hvac_controller()
        if ctrl:
            ctrl.set_cond_fan_level(value)

    def _on_ac_enable_clicked(self, checked: bool) -> None:
        if not self._ensure_online(_HVAC_SLAVE_ID):
            return
        ctrl = get_hvac_controller()
        if ctrl:
            ctrl.set_ac_enable(checked)

    def _on_comp_enable_confirmed(self) -> None:
        if not self._ensure_online(_HVAC_SLAVE_ID):
            return
        ctrl = get_hvac_controller()
        if ctrl:
            ctrl.set_comp_enable(True)

    def _on_heater_set(self, on: bool) -> None:
        if not self._ensure_online(_WEBASTO_SLAVE_ID):
            return
        ctrl = get_webasto_controller()
        if ctrl:
            ctrl.set_heater_on(on)

    def _on_wt_down(self) -> None:
        if not self._ensure_online(_WEBASTO_SLAVE_ID):
            return
        snap = self._app_state.get_snapshot() if self._app_state else None
        cur = snap.webasto.target_water_temp_x10 if snap and snap.webasto.target_water_temp_x10 is not None else 600
        new = max(300, cur - 5)
        ctrl = get_webasto_controller()
        if ctrl:
            ctrl.set_target_water_temp_x10(new)

    def _on_wt_up(self) -> None:
        if not self._ensure_online(_WEBASTO_SLAVE_ID):
            return
        snap = self._app_state.get_snapshot() if self._app_state else None
        cur = snap.webasto.target_water_temp_x10 if snap and snap.webasto.target_water_temp_x10 is not None else 600
        new = min(850, cur + 5)
        ctrl = get_webasto_controller()
        if ctrl:
            ctrl.set_target_water_temp_x10(new)

    def _on_wt_slider_changed(self, value: int) -> None:
        self._wt_label.setText(f"{value / 10:.1f} °C")
        if not self._ensure_online(_WEBASTO_SLAVE_ID):
            return
        ctrl = get_webasto_controller()
        if ctrl:
            ctrl.set_target_water_temp_x10(value)

    def _on_pump_clicked(self, checked: bool) -> None:
        if not self._ensure_online(_WEBASTO_SLAVE_ID):
            return
        ctrl = get_webasto_controller()
        if ctrl:
            ctrl.set_hydronic_pump_on(checked)
