"""More 页面 - 入口菜单：灯光/环境/诊断/设置/摄像头"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QStackedWidget,
    QScrollArea,
)
from PyQt6.QtCore import Qt

from app.ui.pages.base import PageBase
from app.ui.layout_profile import LayoutTokens, get_tokens


SUB_INDEX_MENU = 0
SUB_INDEX_LIGHTING = 1
SUB_INDEX_ENVIRONMENT = 2
SUB_INDEX_DIAGNOSTICS = 3
SUB_INDEX_SETTINGS = 4
SUB_INDEX_CAMERA = 5


class MoreMenuWidget(QWidget):
    """More 菜单：5 个大按钮，触控 >= btn_h_key"""

    def __init__(self, on_item_clicked=None, tokens: LayoutTokens | None = None, parent=None):
        super().__init__(parent)
        self._on_item_clicked = on_item_clicked
        t = tokens
        layout = QVBoxLayout(self)
        layout.setSpacing(t.gap if t else 8)
        layout.setContentsMargins(t.pad_page if t else 10, t.pad_page if t else 10, t.pad_page if t else 10, t.pad_page if t else 10)

        title = QLabel("更多")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        bhk = t.btn_h_key if t else 52
        items = [
            ("灯光", SUB_INDEX_LIGHTING),
            ("环境", SUB_INDEX_ENVIRONMENT),
            ("诊断", SUB_INDEX_DIAGNOSTICS),
            ("设置", SUB_INDEX_SETTINGS),
            ("摄像头", SUB_INDEX_CAMERA),
        ]
        for label, idx in items:
            btn = QPushButton(label, objectName="tabButton")
            btn.setMinimumHeight(bhk)
            btn.setProperty("sub_index", idx)
            btn.clicked.connect(lambda checked, i=idx: self._on_click(i))
            layout.addWidget(btn)
        layout.addStretch()

    def _on_click(self, idx: int):
        if self._on_item_clicked:
            self._on_item_clicked(idx)


class MorePage(PageBase):
    """More 容器：菜单 + 子页面堆叠，带返回按钮。布局由 tokens 驱动。"""

    def __init__(
        self,
        app_state=None,
        alarm_controller=None,
        video_manager=None,
        config_getter=None,
        save_config_fn=None,
        modbus_master_getter=None,
    ):
        super().__init__("更多")
        self._app_state = app_state
        self._alarm_controller = alarm_controller
        self._video_manager = video_manager
        self._config_getter = config_getter
        self._save_config_fn = save_config_fn
        self._modbus_master_getter = modbus_master_getter
        self._stack: QStackedWidget | None = None
        self._back_btn: QPushButton | None = None
        self._header: QWidget | None = None
        self._sub_widgets: list[QWidget] = []
        self._tokens: LayoutTokens | None = get_tokens()
        self._setup_ui()

    def _setup_ui(self):
        layout = self.layout()
        if layout is None:
            return
        while layout.count() > 0:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 子页头部（返回按钮），默认隐藏。样式由 theme.qss moreHeader 统一
        self._header = QFrame(objectName="moreHeader")
        self._header.setVisible(False)
        t = self._tokens
        h = t.icon_btn_h if t else 48
        self._header.setFixedHeight(h)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(10, 4, 10, 4)
        t = self._tokens
        bh = t.btn_h if t else 44
        self._back_btn = QPushButton("← 返回", objectName="tabButton")
        self._back_btn.setMinimumHeight(bh)
        self._back_btn.clicked.connect(self._go_back)
        header_layout.addWidget(self._back_btn)
        header_layout.addStretch()
        main_layout.addWidget(self._header)

        self._stack = QStackedWidget()
        menu = MoreMenuWidget(on_item_clicked=self._on_menu_item_clicked, tokens=self._tokens)
        self._stack.addWidget(menu)

        # 子页面
        from app.ui.pages.lighting import LightingPage
        from app.ui.pages.environment import EnvironmentPage
        from app.ui.pages.diagnostics import DiagnosticsPage
        from app.ui.pages.settings import SettingsPage
        from app.ui.pages.camera import CameraPage
        from app.core.config import get_config, save_config

        cfg_get = self._config_getter or get_config
        save_cfg = self._save_config_fn or save_config
        mm_get = self._modbus_master_getter or (lambda: None)

        self._sub_widgets = [
            LightingPage(app_state=self._app_state),
            EnvironmentPage(app_state=self._app_state),
            DiagnosticsPage(app_state=self._app_state, alarm_controller=self._alarm_controller),
            SettingsPage(
                config_getter=cfg_get,
                save_config_fn=save_cfg,
                app_state=self._app_state,
                modbus_master_getter=mm_get,
                alarm_controller=self._alarm_controller,
            ),
            CameraPage(video_manager=self._video_manager),
        ]
        for w in self._sub_widgets:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(w)
            self._stack.addWidget(scroll)

        main_layout.addWidget(self._stack, 1)

    def set_tokens(self, tokens: LayoutTokens) -> None:
        super().set_tokens(tokens)
        for w in self._sub_widgets:
            if hasattr(w, "set_tokens"):
                w.set_tokens(tokens)

    def _on_menu_item_clicked(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._header.setVisible(True)
        if idx == SUB_INDEX_CAMERA and hasattr(self._sub_widgets[4], "hideEvent"):
            pass  # CameraPage handles start/stop in show/hide
        if hasattr(self._sub_widgets[idx - 1], "showEvent"):
            pass  # TODO: start playback for camera when shown

    def _go_back(self):
        self._stack.setCurrentIndex(SUB_INDEX_MENU)
        self._header.setVisible(False)
        # CameraPage 通过 hideEvent 自动停止播放
