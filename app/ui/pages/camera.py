"""摄像头页面：鸟瞰/分屏/单路模式，RTSP 源选择，VideoWidget 播放"""

import logging

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QButtonGroup,
    QStackedWidget,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.ui.pages.base import PageBase
from app.core.config import get_config

logger = logging.getLogger(__name__)


class VideoWidget(QFrame):
    """承载 GStreamer overlay 的 QWidget，提供 winId() 给 VideoManager"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("videoWidget")
        self.setMinimumSize(200, 120)
        self.setStyleSheet(
            "#videoWidget { background: #1a1a1a; border: none; }"
        )


# TODO: 分屏合成 - 多路 RTSP 并排显示
class SplitViewPlaceholder(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        ly = QVBoxLayout(self)
        ly.addWidget(QLabel("分屏模式 TODO", objectName="accent"))


# TODO: 鸟瞰合成 - 多路拼接俯视图
class BirdViewPlaceholder(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        ly = QVBoxLayout(self)
        ly.addWidget(QLabel("鸟瞰模式 TODO", objectName="accent"))


class SingleViewWidget(QWidget):
    """单路模式：一个 VideoWidget + 源选择按钮"""

    source_clicked = pyqtSignal(str)  # source_id -> url
    status_changed = pyqtSignal(str)  # playing|reconnecting|failed|stopped

    def __init__(self, video_manager, parent=None):
        super().__init__(parent)
        self._video_manager = video_manager
        self._current_source: str | None = None
        self._urls: dict[str, str] = {}
        self._setup_ui()
        self._connect_video_manager()

    def _setup_ui(self):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)

        # 单路全屏：先视频区撑满
        self._video_widget = VideoWidget(self)
        ly.addWidget(self._video_widget, 1)

        # 状态一行
        self._status_label = QLabel("未选择", objectName="accent")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setMaximumHeight(28)
        ly.addWidget(self._status_label)

        # 底部源选择：一排按钮，最多 4 个一屏，可横向滚动
        cfg = get_config()
        urls = cfg.camera.rtsp_urls or {}
        self._urls = {k: v for k, v in urls.items() if k in ("cam1", "cam2", "cam3", "cam4", "cam5", "cam6", "bird") and v}
        logger.debug("[Camera] RTSP URLs 已配置: %s", list(self._urls.keys()) or "无")

        self._source_buttons: dict[str, QPushButton] = {}
        self._btn_group = QButtonGroup(self)
        labels = {
            "cam1": "前", "cam2": "后", "cam3": "左", "cam4": "右",
            "cam5": "5", "cam6": "6", "bird": "鸟瞰",
        }
        btn_container = QWidget()
        btn_row = QHBoxLayout(btn_container)
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(8, 4, 8, 4)
        for sid in ("cam1", "cam2", "cam3", "cam4", "cam5", "cam6", "bird"):
            label = labels.get(sid, sid)
            btn = QPushButton(label, objectName="cameraSourceBtn")
            btn.setCheckable(True)
            btn.setMinimumHeight(44)
            btn.setMinimumWidth(72)
            btn.setProperty("source_id", sid)
            url = self._urls.get(sid, "")
            btn.setEnabled(bool(url))
            if not url:
                btn.setToolTip("未配置 RTSP")
            btn.clicked.connect(lambda checked, s=sid: self._on_source_click(s))
            btn_row.addWidget(btn)
            self._source_buttons[sid] = btn
            self._btn_group.addButton(btn)
        btn_row.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(btn_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(56)
        scroll.setMinimumHeight(52)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        ly.addWidget(scroll)

    def _connect_video_manager(self):
        self._video_manager.on_placeholder_hint(self._on_placeholder)
        self._video_manager.on_status_change(self._on_status)

    def _on_placeholder(self, msg: str):
        self.status_changed.emit("failed")
        self._update_status_label("失败", msg)

    def _on_status(self, status: str):
        self.status_changed.emit(status)
        labels = {"playing": "播放中", "reconnecting": "重连中", "failed": "失败", "stopped": "已停止"}
        self._update_status_label(labels.get(status, status))

    def _update_status_label(self, text: str, detail: str = ""):
        full = f"{text}" + (f" ({detail})" if detail else "")
        self._status_label.setText(full)

    def _on_source_click(self, source_id: str):
        url = self._urls.get(source_id, "")
        if not url:
            return
        self._current_source = source_id
        for sid, btn in self._source_buttons.items():
            btn.setChecked(sid == source_id)
        self._video_manager.switch(url)
        self._update_status_label("连接中...")

    def start_playback(self, source_id: str | None = None):
        """开始播放：若未选源则选第一个有 URL 的"""
        if not self._urls:
            logger.debug("[Camera] start_playback 跳过: 无已配置 RTSP 地址")
            self._update_status_label("未配置 RTSP 地址")
            return
        sid = source_id or next((k for k in ("cam1", "cam2", "cam3", "cam4", "cam5", "cam6", "bird") if self._urls.get(k)), None)
        if not sid:
            return
        url = self._urls[sid]
        self._current_source = sid
        for k, btn in self._source_buttons.items():
            btn.setChecked(k == sid)
        win_id_val = self._video_widget.winId()
        win_id = int(win_id_val) if win_id_val else 0
        logger.debug("[Camera] start_playback source=%s url=%s winId=%s", sid, url[:60] if url else "", win_id)
        if win_id:
            self._video_manager.start(url, win_id)
        else:
            self._video_manager.start(url, None)
        self._update_status_label("连接中...")

    def stop_playback(self):
        self._video_manager.stop()
        self._update_status_label("已停止")


class CameraPage(PageBase):
    """摄像头页：模式切换 + 单路/分屏/鸟瞰"""

    def __init__(self, video_manager=None):
        super().__init__("摄像头")
        self._video_manager = video_manager
        if self._video_manager is None:
            from app.services.video_manager import get_video_manager
            self._video_manager = get_video_manager()
        self._single_view: SingleViewWidget | None = None
        self._setup_ui()

    def _setup_ui(self):
        # 复用基类 layout，仅清空后添加相机内容（避免 QLayout 冲突导致主界面无法显示）
        root = self.layout()
        if not root:
            root = QVBoxLayout(self)
        while root.count():
            item = root.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)
        logger.debug("[Camera] CameraPage 布局已初始化")

        # 模式按钮：鸟瞰 / 分屏 / 单路（单路默认全屏）
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self._mode_group = QButtonGroup(self)
        modes = [("鸟瞰", "bird"), ("分屏", "split"), ("单路", "single")]
        for label, mode_id in modes:
            btn = QPushButton(label, objectName="tabButton")
            btn.setCheckable(True)
            btn.setProperty("mode_id", mode_id)
            btn.clicked.connect(lambda checked, m=mode_id: self._on_mode_click(m))
            mode_row.addWidget(btn)
            self._mode_group.addButton(btn)
        mode_row.addStretch()
        root.addLayout(mode_row)

        # 内容区：StackedWidget 切换 鸟瞰/分屏/单路（占位用 parent=None，由 stack 接管）
        self._stack = QStackedWidget()
        self._stack.addWidget(BirdViewPlaceholder())
        self._stack.addWidget(SplitViewPlaceholder())

        single_container = QWidget()
        single_layout = QVBoxLayout(single_container)
        single_layout.setContentsMargins(0, 0, 0, 0)
        self._single_view = SingleViewWidget(self._video_manager, single_container)
        single_layout.addWidget(self._single_view)
        self._stack.addWidget(single_container)

        root.addWidget(self._stack, 1)

        # 默认单路模式
        self._mode_group.buttons()[2].setChecked(True)
        self._stack.setCurrentIndex(2)
        self._single_view.start_playback()

    def _on_mode_click(self, mode_id: str):
        idx = {"bird": 0, "split": 1, "single": 2}.get(mode_id, 2)
        for i, btn in enumerate(self._mode_group.buttons()):
            btn.setChecked(btn.property("mode_id") == mode_id)
        self._stack.setCurrentIndex(idx)
        if mode_id == "single" and self._single_view:
            self._single_view.start_playback()
        elif mode_id in ("bird", "split"):
            if self._single_view:
                self._single_view.stop_playback()
            # TODO: 启动分屏/鸟瞰合成

    def hideEvent(self, event):
        if self._single_view and self._stack.currentIndex() == 2:
            self._single_view.stop_playback()
        super().hideEvent(event)
