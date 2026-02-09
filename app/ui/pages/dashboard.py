"""仪表盘页面 - 布局完全由 LayoutTokens 驱动；状态/告警颜色用 severity 动态属性 + QSS，无内联 setStyleSheet。"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor

from app.ui.pages.base import PageBase
from app.ui.layout_profile import LayoutTokens, get_tokens

# 底部 Tab / More 子页
TAB_HVAC, TAB_POWER, TAB_EXTERIOR, TAB_MORE = 1, 2, 3, 4
SUB_LIGHTING, SUB_ENV, SUB_DIAG, SUB_SETTINGS, SUB_CAMERA = 1, 2, 3, 4, 5

HVAC_MODE_NAMES = {0: "Off", 1: "Cool", 2: "Vent", 3: "Auto"}


def _v(x10: int | None) -> str:
    return f"{x10 / 10:.1f}" if x10 is not None else "--"


def _ok(ok: bool | None) -> str:
    if ok is None:
        return "?"
    return "✓" if ok else "✗"


def _voltage(x100: int | None) -> str:
    return f"{x100 / 100:.1f}" if x100 is not None else "--"


def _apply_severity(widget: QLabel, severity: str | None) -> None:
    """设置 severity 并刷新样式（unpolish/polish）。"""
    if severity:
        widget.setProperty("severity", severity)
    else:
        widget.setProperty("severity", "")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ClickableCard(QFrame):
    """可点击卡片：整个区域点击跳转，不改变 state 定义"""

    def __init__(self, on_click=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._on_click = on_click
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._on_click:
            self._on_click()
        super().mousePressEvent(event)


class DashboardPage(PageBase):
    """仪表盘：标题 + 快捷按钮 | 2 列 4 卡片 | 底部状态条。布局由 tokens 驱动。"""

    def __init__(self, app_state=None, on_switch_page=None):
        super().__init__("仪表盘")
        self._app_state = app_state
        self._on_switch_page = on_switch_page
        self._tokens: LayoutTokens | None = get_tokens()
        layout = self.layout()
        if layout is None:
            return

        while layout.count() > 0:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        t = self._tokens
        layout.setSpacing(t.gap)
        layout.setContentsMargins(t.pad_page, t.pad_page, t.pad_page, t.pad_page)

        # 1) 顶部：标题 + Alarms / Settings 快捷按钮
        header = QHBoxLayout()
        title = QLabel("仪表盘")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        alarms_btn = QPushButton("告警")
        alarms_btn.setObjectName("shortcutBtn")
        alarms_btn.setMinimumHeight(t.btn_h_key)
        alarms_btn.clicked.connect(lambda: on_switch_page and on_switch_page(4, SUB_DIAG))
        settings_btn = QPushButton("设置")
        settings_btn.setObjectName("shortcutBtn")
        settings_btn.setMinimumHeight(t.btn_h_key)
        settings_btn.clicked.connect(lambda: on_switch_page and on_switch_page(4, SUB_SETTINGS))
        header.addWidget(alarms_btn)
        header.addWidget(settings_btn)
        layout.addLayout(header)

        # 2) 主体：2 列网格，4 张核心卡片
        grid = QGridLayout()
        grid.setSpacing(t.gap)

        card_batt = self._build_battery_card()
        grid.addWidget(card_batt, 0, 0)
        card_climate = self._build_climate_card()
        grid.addWidget(card_climate, 0, 1)
        card_power = self._build_power_card()
        grid.addWidget(card_power, 1, 0)
        card_env = self._build_env_card()
        grid.addWidget(card_env, 1, 1)

        layout.addLayout(grid)

        # 3) 底部状态条
        status_row = QHBoxLayout()
        self._status_label = QLabel("从站 -- | 错误 --")
        self._status_label.setObjectName("small")
        status_row.addWidget(self._status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        layout.addStretch()

        if app_state:
            app_state.changed.connect(
                self._on_state_changed,
                Qt.ConnectionType.QueuedConnection,
            )
            QTimer.singleShot(0, self._refresh_once)

    def set_tokens(self, t: LayoutTokens) -> None:
        """由 MainWindow 注入/更新 tokens，重新应用布局与按钮高度。"""
        self._tokens = t
        layout = self.layout()
        if layout is not None and t:
            layout.setSpacing(t.gap)
            layout.setContentsMargins(t.pad_page, t.pad_page, t.pad_page, t.pad_page)
        for c in self.findChildren(QPushButton):
            if c.objectName() == "shortcutBtn":
                c.setMinimumHeight(t.btn_h_key)

    def _build_battery_card(self) -> QFrame:
        t = self._tokens
        card = ClickableCard(on_click=lambda: self._on_switch_page and self._on_switch_page(TAB_POWER, None))
        lay = QVBoxLayout(card)
        lay.setSpacing(t.gap)
        lay.setContentsMargins(t.pad_card, t.pad_card, t.pad_card, t.pad_card)
        lay.addWidget(QLabel("电池 / SOC"))
        self._soc_label = QLabel("--")
        self._soc_label.setObjectName("bigNumber")
        lay.addWidget(self._soc_label)
        self._batt_detail = QLabel("电压 --V | 功率 --W")
        self._batt_detail.setObjectName("small")
        lay.addWidget(self._batt_detail)
        return card

    def _build_climate_card(self) -> QFrame:
        t = self._tokens
        card = ClickableCard(on_click=lambda: self._on_switch_page and self._on_switch_page(TAB_HVAC, None))
        lay = QVBoxLayout(card)
        lay.setSpacing(t.gap)
        lay.setContentsMargins(t.pad_card, t.pad_card, t.pad_card, t.pad_card)
        lay.addWidget(QLabel("空调"))
        self._mode_label = QLabel("--")
        self._mode_label.setObjectName("midNumber")
        lay.addWidget(self._mode_label)
        self._temp_label = QLabel("目标 --°C")
        self._temp_label.setObjectName("small")
        lay.addWidget(self._temp_label)
        self._fault_label = QLabel("HP? LP? 故障0")
        self._fault_label.setObjectName("small")
        lay.addWidget(self._fault_label)
        return card

    def _build_power_card(self) -> QFrame:
        t = self._tokens
        card = ClickableCard(on_click=lambda: self._on_switch_page and self._on_switch_page(TAB_POWER, None))
        lay = QVBoxLayout(card)
        lay.setSpacing(t.gap)
        lay.setContentsMargins(t.pad_card, t.pad_card, t.pad_card, t.pad_card)
        lay.addWidget(QLabel("220V / 冰箱"))
        self._ac_label = QLabel("220V: --")
        self._ac_label.setObjectName("small")
        lay.addWidget(self._ac_label)
        self._fridge_label = QLabel("冰箱: --")
        self._fridge_label.setObjectName("small")
        lay.addWidget(self._fridge_label)
        return card

    def _build_env_card(self) -> QFrame:
        t = self._tokens
        card = ClickableCard(on_click=lambda: self._on_switch_page and self._on_switch_page(TAB_MORE, SUB_ENV))
        lay = QVBoxLayout(card)
        lay.setSpacing(t.gap)
        lay.setContentsMargins(t.pad_card, t.pad_card, t.pad_card, t.pad_card)
        lay.addWidget(QLabel("环境 / 气体"))
        self._cabin_label = QLabel("室内 --°C --%")
        self._cabin_label.setObjectName("small")
        lay.addWidget(self._cabin_label)
        self._gas_label = QLabel("CO -- LPG --")
        self._gas_label.setObjectName("small")
        lay.addWidget(self._gas_label)
        self._gas_status_label = QLabel("正常")
        self._gas_status_label.setObjectName("statusPill")
        self._gas_status_label.setProperty("severity", "ok")
        lay.addWidget(self._gas_status_label)
        return card

    def _refresh_once(self) -> None:
        if self._app_state:
            self._on_state_changed(self._app_state.get_snapshot())

    def _on_state_changed(self, snap) -> None:
        if snap is None:
            return
        p, h, pd, env, gas, comm = (
            snap.power, snap.hvac, snap.pdu, snap.env, snap.gas, snap.comm,
        )

        soc = _v(p.soc_x10) if p.soc_x10 is not None else "--"
        self._soc_label.setText(f"{soc}%")
        v = _voltage(p.batt_v_x100)
        pw = str(p.batt_p_w) if p.batt_p_w is not None else "--"
        self._batt_detail.setText(f"电压 {v}V | 功率 {pw}W")

        mode = HVAC_MODE_NAMES.get(h.mode, str(h.mode)) if h.mode is not None else "--"
        target = _v(h.target_temp_x10) if h.target_temp_x10 is not None else "--"
        fc = str(h.hvac_fault_code) if h.hvac_fault_code is not None else "0"
        hp, lp = _ok(h.hp_ok), _ok(h.lp_ok)
        self._mode_label.setText(mode)
        self._temp_label.setText(f"目标 {target}°C")
        self._fault_label.setText(f"HP{hp} LP{lp} 故障{fc}")

        cmd = "合闸" if pd.inv_ac_out_on else "分闸"
        fb = "有电" if pd.inv_ac_out_fb else "无电"
        mismatch = pd.inv_ac_out_on != pd.inv_ac_out_fb if pd.inv_ac_out_on is not None and pd.inv_ac_out_fb is not None else False
        self._ac_label.setText(f"220V: {cmd} / {fb}" + (" ⚠" if mismatch else ""))
        self._fridge_label.setText("冰箱: " + ("开" if pd.fridge_24v_on else "关"))

        self._cabin_label.setText(f"室内 {_v(env.cabin_temp_x10)}°C {_v(env.cabin_rh_x10)}%")
        co = str(gas.co_ppm) if gas.co_ppm is not None else "--"
        lpg = _v(gas.lpg_lel_x10) if gas.lpg_lel_x10 is not None else "--"
        self._gas_label.setText(f"CO {co}ppm LPG {lpg}%LEL")

        if gas.gas_fault or gas.gas_alarm:
            self._gas_status_label.setText("故障/报警")
            _apply_severity(self._gas_status_label, "crit")
        elif gas.warmup:
            self._gas_status_label.setText("预热")
            _apply_severity(self._gas_status_label, "warn")
        else:
            self._gas_status_label.setText("正常")
            _apply_severity(self._gas_status_label, "ok")

        online = sum(1 for c in comm.values() if getattr(c, "online", False))
        total = len(comm) if comm else 0
        errs = sum(getattr(c, "error_count", 0) for c in comm.values())
        self._status_label.setText(f"从站 {online}/{total} | 错误 {errs}")
