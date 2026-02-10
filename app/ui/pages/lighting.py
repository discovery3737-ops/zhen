"""灯光页面 - WVGA：两列开关列表（CompactToggleRow）+ 灯带亮度 TwoColumnFormRow"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QSlider,
    QScrollArea,
    QGridLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer

from app.ui.pages.base import PageBase
from app.ui.layout_profile import LayoutTokens, get_tokens
from app.ui.widgets import CompactToggleRow, TwoColumnFormRow
from app.devices.lighting import get_lighting_controller

_LIGHTING_SLAVE_ID = 3


class LightingPage(PageBase):
    """灯光页：两列开关（CompactToggleRow btn_h）+ 灯带亮度滑条。布局由 tokens 驱动。"""

    def __init__(self, app_state=None):
        super().__init__("灯光")
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        ly = QVBoxLayout(inner)
        ly.setSpacing(t.gap if t else 8)
        ly.setContentsMargins(t.pad_page if t else 10, t.pad_page if t else 10, t.pad_page if t else 10, t.pad_page if t else 10)

        title = QLabel("灯光")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(title)

        card = QFrame(objectName="card")
        card_ly = QVBoxLayout(card)
        card_ly.setSpacing(t.gap if t else 8)
        card_ly.setContentsMargins(t.pad_card if t else 10, t.pad_card if t else 10, t.pad_card if t else 10, t.pad_card if t else 10)

        # 两列开关：CompactToggleRow
        self._main_row = CompactToggleRow("顶主灯", tokens=t)
        self._main_row.checkbox().toggled.connect(self._on_main_clicked)
        self._night_row = CompactToggleRow("夜灯", tokens=t)
        self._night_row.checkbox().toggled.connect(self._on_night_clicked)
        self._reading_row = CompactToggleRow("阅读灯", tokens=t)
        self._reading_row.checkbox().toggled.connect(self._on_reading_clicked)
        self._strip_row = CompactToggleRow("灯带", tokens=t)
        self._strip_row.checkbox().toggled.connect(self._on_strip_clicked)

        grid = QGridLayout()
        grid.addWidget(self._main_row, 0, 0)
        grid.addWidget(self._night_row, 0, 1)
        grid.addWidget(self._reading_row, 1, 0)
        grid.addWidget(self._strip_row, 1, 1)
        card_ly.addLayout(grid)

        # 灯带亮度：TwoColumnFormRow（左侧「灯带亮度」，右侧滑条+数值）
        self._strip_slider = QSlider(Qt.Orientation.Horizontal)
        self._strip_slider.setRange(0, 1000)
        self._strip_slider.setValue(500)
        self._strip_slider.valueChanged.connect(self._on_strip_slider_changed)
        self._strip_value_label = QLabel("--")
        self._strip_value_label.setMinimumWidth(48)
        slider_row = QWidget()
        slider_ly = QHBoxLayout(slider_row)
        slider_ly.setContentsMargins(0, 0, 0, 0)
        slider_ly.addWidget(self._strip_slider, 1)
        slider_ly.addWidget(self._strip_value_label)
        card_ly.addWidget(TwoColumnFormRow("灯带亮度", slider_row, tokens=t))

        # 场景
        bh = t.btn_h if t else 44
        scene_row = QHBoxLayout()
        self._sleep_btn = QPushButton("Sleep")
        self._sleep_btn.setMinimumHeight(bh)
        self._sleep_btn.clicked.connect(self._on_sleep_clicked)
        self._reading_scene_btn = QPushButton("Reading")
        self._reading_scene_btn.setMinimumHeight(bh)
        self._reading_scene_btn.clicked.connect(self._on_reading_scene_clicked)
        scene_row.addWidget(self._sleep_btn)
        scene_row.addWidget(self._reading_scene_btn)
        card_ly.addLayout(scene_row)

        ly.addWidget(card)
        ly.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        if app_state:
            app_state.changed.connect(
                self._on_state_changed,
                Qt.ConnectionType.QueuedConnection,
            )
            QTimer.singleShot(0, self._refresh_once)

    def _refresh_once(self) -> None:
        if self._app_state:
            self._on_state_changed(self._app_state.get_snapshot())

    def _on_state_changed(self, snap) -> None:
        if snap is None:
            return
        L = snap.lighting
        for row, val in [
            (self._main_row, L.main),
            (self._night_row, L.night),
            (self._reading_row, L.reading),
            (self._strip_row, L.strip),
        ]:
            on = val if val is not None else False
            row.checkbox().blockSignals(True)
            row.set_checked(on)
            row.checkbox().blockSignals(False)
        bright = L.strip_brightness if L.strip_brightness is not None else 0
        self._strip_slider.blockSignals(True)
        self._strip_slider.setValue(max(0, min(1000, bright)))
        self._strip_slider.blockSignals(False)
        self._strip_value_label.setText(str(bright))

    def _ensure_online_then_write(self, slave_id: int) -> bool:
        """写入前检查从站是否在线，离线则提示并返回 False。"""
        if not self._app_state:
            return True
        comm = self._app_state.get_snapshot().comm.get(slave_id)
        if not (comm and comm.online):
            QMessageBox.warning(self, "设备离线", "设备离线，无法写入。")
            return False
        return True

    def _on_main_clicked(self, checked: bool) -> None:
        if not self._ensure_online_then_write(_LIGHTING_SLAVE_ID):
            return
        ctrl = get_lighting_controller()
        if ctrl:
            ctrl.set_main(checked)

    def _on_night_clicked(self, checked: bool) -> None:
        if not self._ensure_online_then_write(_LIGHTING_SLAVE_ID):
            return
        ctrl = get_lighting_controller()
        if ctrl:
            ctrl.set_night(checked)

    def _on_reading_clicked(self, checked: bool) -> None:
        if not self._ensure_online_then_write(_LIGHTING_SLAVE_ID):
            return
        ctrl = get_lighting_controller()
        if ctrl:
            ctrl.set_reading(checked)

    def _on_strip_clicked(self, checked: bool) -> None:
        if not self._ensure_online_then_write(_LIGHTING_SLAVE_ID):
            return
        ctrl = get_lighting_controller()
        if ctrl:
            ctrl.set_strip_on(checked)

    def _on_strip_slider_changed(self, value: int) -> None:
        self._strip_value_label.setText(str(value))
        if not self._ensure_online_then_write(_LIGHTING_SLAVE_ID):
            return
        ctrl = get_lighting_controller()
        if ctrl:
            ctrl.set_strip_brightness(value)

    def _on_sleep_clicked(self) -> None:
        if not self._ensure_online_then_write(_LIGHTING_SLAVE_ID):
            return
        ctrl = get_lighting_controller()
        if ctrl:
            ctrl.scene_sleep_pulse()

    def set_tokens(self, tokens: LayoutTokens) -> None:
        super().set_tokens(tokens)
        self._tokens = tokens
        for row in (self._main_row, self._night_row, self._reading_row, self._strip_row):
            row.set_tokens(tokens)

    def _on_reading_scene_clicked(self) -> None:
        if not self._ensure_online_then_write(_LIGHTING_SLAVE_ID):
            return
        ctrl = get_lighting_controller()
        if ctrl:
            ctrl.scene_reading_pulse()
