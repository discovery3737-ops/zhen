"""环境页面 - WVGA：室内外小卡片并排 + 气体大卡片 + 离线横条"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer

from app.ui.pages.base import PageBase


def _temp_str(x10: int | None) -> str:
    if x10 is None:
        return "--.-"
    return f"{x10 / 10:.1f}"


def _rh_str(x10: int | None) -> str:
    if x10 is None:
        return "--.-"
    return f"{x10 / 10:.1f}"


def _co_str(ppm: int | None) -> str:
    if ppm is None:
        return "--"
    return str(ppm)


def _lpg_str(x10: int | None) -> str:
    if x10 is None:
        return "--.-"
    return f"{x10 / 10:.1f}"


class EnvironmentPage(PageBase):
    """环境页：室内外两张小卡片并排；气体一张大卡片；离线用横条"""

    def __init__(self, app_state=None):
        super().__init__("环境")
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

        title = QLabel("环境")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(title)

        # 离线提示横条
        self._offline_banner = QFrame(objectName="offlineBanner")
        self._offline_banner.setVisible(False)
        self._offline_banner.setStyleSheet(
            "QFrame#offlineBanner { background-color: #B91C1C; color: white; "
            "padding: 8px 10px; font-size: 12px; font-weight: bold; border-radius: 6px; }"
        )
        offline_ly = QVBoxLayout(self._offline_banner)
        self._offline_label = QLabel("")
        self._offline_label.setWordWrap(True)
        offline_ly.addWidget(self._offline_label)
        ly.addWidget(self._offline_banner)

        # 室内 / 室外 两张小卡片并排
        row_cards = QHBoxLayout()
        row_cards.setSpacing(8)

        indoor_card = QFrame(objectName="card")
        indoor_ly = QVBoxLayout(indoor_card)
        indoor_ly.setSpacing(4)
        indoor_ly.setContentsMargins(8, 8, 8, 8)
        indoor_ly.addWidget(QLabel("室内", objectName="accent"))
        self._cabin_temp_label = QLabel("--.- °C")
        self._cabin_temp_label.setObjectName("bigNumber")
        self._cabin_rh_label = QLabel("--.- %")
        self._cabin_rh_label.setObjectName("small")
        indoor_ly.addWidget(self._cabin_temp_label)
        indoor_ly.addWidget(self._cabin_rh_label)
        row_cards.addWidget(indoor_card, 1)

        outdoor_card = QFrame(objectName="card")
        outdoor_ly = QVBoxLayout(outdoor_card)
        outdoor_ly.setSpacing(4)
        outdoor_ly.setContentsMargins(8, 8, 8, 8)
        outdoor_ly.addWidget(QLabel("室外", objectName="accent"))
        self._out_temp_label = QLabel("--.- °C")
        self._out_temp_label.setObjectName("bigNumber")
        self._out_rh_label = QLabel("--.- %")
        self._out_rh_label.setObjectName("small")
        outdoor_ly.addWidget(self._out_temp_label)
        outdoor_ly.addWidget(self._out_rh_label)
        row_cards.addWidget(outdoor_card, 1)

        ly.addLayout(row_cards)

        # 气体一张大卡片
        gas_card = QFrame(objectName="card")
        gas_ly = QVBoxLayout(gas_card)
        gas_ly.setSpacing(8)
        gas_ly.setContentsMargins(10, 10, 10, 10)
        gas_ly.addWidget(QLabel("气体", objectName="accent"))
        gas_ly.addWidget(QLabel("CO (ppm):"))
        self._co_label = QLabel("--")
        self._co_label.setObjectName("bigNumber")
        gas_ly.addWidget(self._co_label)
        gas_ly.addWidget(QLabel("LPG (%LEL):"))
        self._lpg_label = QLabel("--.-")
        self._lpg_label.setObjectName("bigNumber")
        gas_ly.addWidget(self._lpg_label)
        self._gas_status_label = QLabel("")
        self._gas_status_label.setObjectName("small")
        self._gas_status_label.setWordWrap(True)
        gas_ly.addWidget(self._gas_status_label)
        ly.addWidget(gas_card)

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
        env = snap.env
        gas = snap.gas
        comm = snap.comm

        offline_slaves = []
        if not (comm.get(6) and comm[6].online):
            offline_slaves.append("Slave06 舱内")
        if not (comm.get(9) and comm[9].online):
            offline_slaves.append("Slave09 室外")
        if not (comm.get(7) and comm[7].online):
            offline_slaves.append("Slave07 气体")
        if offline_slaves:
            self._offline_banner.setVisible(True)
            self._offline_label.setText("传感器离线: " + " / ".join(offline_slaves))
        else:
            self._offline_banner.setVisible(False)

        self._cabin_temp_label.setText(f"{_temp_str(env.cabin_temp_x10)} °C")
        self._cabin_rh_label.setText(f"湿度 {_rh_str(env.cabin_rh_x10)} %")
        self._out_temp_label.setText(f"{_temp_str(env.out_temp_x10)} °C")
        self._out_rh_label.setText(f"湿度 {_rh_str(env.out_rh_x10)} %")

        self._co_label.setText(_co_str(gas.co_ppm))
        self._lpg_label.setText(_lpg_str(gas.lpg_lel_x10))
        status_parts = []
        if gas.warmup:
            status_parts.append("预热中")
        if gas.gas_alarm:
            status_parts.append("报警")
        if gas.gas_fault:
            status_parts.append("故障")
        if status_parts:
            self._gas_status_label.setText(" | ".join(status_parts))
            self._gas_status_label.setStyleSheet(
                "font-size: 12px; color: #B91C1C; font-weight: bold;"
                if (gas.gas_alarm or gas.gas_fault)
                else "font-size: 12px; color: #EAB308;"
            )
        else:
            self._gas_status_label.setText("正常")
            self._gas_status_label.setStyleSheet("font-size: 12px; color: #22C55E;")
