"""摄像头页面：鸟瞰/分屏/单路模式，RTSP 源选择，VideoWidget 播放。布局由 LayoutTokens 驱动，WVGA 触控一致。"""

import logging
from typing import TYPE_CHECKING

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
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.ui.pages.base import PageBase
from app.ui.layout_profile import LayoutTokens, get_tokens
from app.core.config import get_config

if TYPE_CHECKING:
    from app.services.video_manager import VideoManager

logger = logging.getLogger(__name__)

# WVGA 下源按钮高度上限，避免挤压视频区
_SOURCE_BAR_HEIGHT_CAP = 64


class VideoWidget(QFrame):
    """承载 GStreamer overlay 的 QWidget，提供 winId() 给 VideoManager。样式由 theme.qss videoWidget 统一。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("videoWidget")
        self.setMinimumSize(200, 120)


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
    """单路模式：一个 VideoWidget + 状态条 + 源选择按钮。支持 tokens / set_tokens。"""

    source_clicked = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(
        self,
        video_manager: "VideoManager",
        tokens: LayoutTokens | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._video_manager = video_manager
        self._current_source: str | None = None
        self._urls: dict[str, str] = {}
        self._tokens = tokens
        self._setup_ui()
        self._connect_video_manager()

    def _setup_ui(self) -> None:
        t = self._tokens
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)

        self._video_widget = VideoWidget(self)
        ly.addWidget(self._video_widget, 1)

        # 状态一行（高度 token 化）
        self._status_label = QLabel("未选择", objectName="cameraStatusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_h = (t.font_small + t.gap * 2) if t else 28
        self._status_label.setMaximumHeight(status_h)
        ly.addWidget(self._status_label)

        # 底部源选择：横向滚动，按钮高度 t.btn_h，WVGA 下源栏总高不超过 64
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
        g = t.gap if t else 8
        p = t.pad_page if t else 8
        btn_row.setSpacing(g)
        btn_row.setContentsMargins(p, g // 2, p, g // 2)
        bh = t.btn_h if t else 44
        # 源按钮宽高：最小 t.btn_h 高；宽用 min(icon_btn_h, 64) 避免过宽
        src_w = min(t.icon_btn_h, _SOURCE_BAR_HEIGHT_CAP) if t else 56
        for sid in ("cam1", "cam2", "cam3", "cam4", "cam5", "cam6", "bird"):
            label = labels.get(sid, sid)
            btn = QPushButton(label, objectName="cameraSourceBtn")
            btn.setCheckable(True)
            btn.setMinimumHeight(bh)
            btn.setMinimumWidth(src_w)
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
        bar_h = min((bh + g * 2), _SOURCE_BAR_HEIGHT_CAP) if t else 56
        scroll.setMaximumHeight(bar_h)
        scroll.setMinimumHeight(bh + (g if t else 4))
        ly.addWidget(scroll)

    def set_tokens(self, tokens: LayoutTokens) -> None:
        self._tokens = tokens
        g = tokens.gap
        p = tokens.pad_page
        bh = tokens.btn_h
        src_w = min(tokens.icon_btn_h, _SOURCE_BAR_HEIGHT_CAP)
        status_h = tokens.font_small + g * 2
        self._status_label.setMaximumHeight(status_h)
        for btn in self._source_buttons.values():
            btn.setMinimumHeight(bh)
            btn.setMinimumWidth(src_w)
        layout = self.layout()
        if layout and layout.count() >= 3:
            scroll = layout.itemAt(2).widget()
            if isinstance(scroll, QScrollArea):
                bar_h = min(bh + g * 2, _SOURCE_BAR_HEIGHT_CAP)
                scroll.setMaximumHeight(bar_h)
                scroll.setMinimumHeight(bh + g)
                w = scroll.widget()
                if w and w.layout():
                    w.layout().setSpacing(g)
                    w.layout().setContentsMargins(p, g // 2, p, g // 2)

    def _connect_video_manager(self) -> None:
        self._video_manager.on_placeholder_hint(self._on_placeholder)
        self._video_manager.on_status_change(self._on_status)

    def _on_placeholder(self, msg: str) -> None:
        self.status_changed.emit("failed")
        self._update_status_label("失败", msg)

    def _on_status(self, status: str) -> None:
        self.status_changed.emit(status)
        labels = {"playing": "播放中", "reconnecting": "重连中", "failed": "失败", "stopped": "已停止"}
        self._update_status_label(labels.get(status, status))

    def _update_status_label(self, text: str, detail: str = "") -> None:
        full = f"{text}" + (f" ({detail})" if detail else "")
        self._status_label.setText(full)

    def _on_source_click(self, source_id: str) -> None:
        url = self._urls.get(source_id, "")
        if not url:
            return
        self._current_source = source_id
        for sid, btn in self._source_buttons.items():
            btn.setChecked(sid == source_id)
        self._video_manager.switch(url)
        self._update_status_label("连接中...")

    def start_playback(self, source_id: str | None = None) -> None:
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

    def stop_playback(self) -> None:
        self._video_manager.stop()
        self._update_status_label("已停止")


class CameraPage(PageBase):
    """摄像头页：模式切换 + 单路/分屏/鸟瞰。布局由 LayoutTokens 驱动。"""

    def __init__(self, video_manager=None):
        super().__init__("摄像头")
        self._video_manager = video_manager
        if self._video_manager is None:
            from app.services.video_manager import get_video_manager
            self._video_manager = get_video_manager()
        self._tokens: LayoutTokens | None = get_tokens()
        self._single_view: SingleViewWidget | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        t = self._tokens
        root = self.layout()
        if not root:
            root = QVBoxLayout(self)
        while root.count():
            item = root.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        g = t.gap if t else 8
        p = t.pad_page if t else 0
        root.setSpacing(g)
        root.setContentsMargins(p, p, p, p)
        logger.debug("[Camera] CameraPage 布局已初始化")

        # 模式按钮：鸟瞰 / 分屏 / 单路，等宽、高度 t.btn_h
        mode_row = QHBoxLayout()
        mode_row.setSpacing(g)
        self._mode_group = QButtonGroup(self)
        bh = t.btn_h if t else 44
        modes = [("鸟瞰", "bird"), ("分屏", "split"), ("单路", "single")]
        for label, mode_id in modes:
            btn = QPushButton(label, objectName="cameraModeBtn")
            btn.setCheckable(True)
            btn.setMinimumHeight(bh)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.setProperty("mode_id", mode_id)
            btn.clicked.connect(lambda checked, m=mode_id: self._on_mode_click(m))
            mode_row.addWidget(btn, 1)
            self._mode_group.addButton(btn)
        root.addLayout(mode_row)

        self._stack = QStackedWidget()
        self._stack.addWidget(BirdViewPlaceholder())
        self._stack.addWidget(SplitViewPlaceholder())

        single_container = QWidget()
        single_layout = QVBoxLayout(single_container)
        single_layout.setContentsMargins(0, 0, 0, 0)
        self._single_view = SingleViewWidget(self._video_manager, tokens=t, parent=single_container)
        single_layout.addWidget(self._single_view)
        self._stack.addWidget(single_container)

        root.addWidget(self._stack, 1)

        self._mode_group.buttons()[2].setChecked(True)
        self._stack.setCurrentIndex(2)
        self._single_view.start_playback()

    def set_tokens(self, tokens: LayoutTokens) -> None:
        super().set_tokens(tokens)
        self._tokens = tokens
        g = tokens.gap
        p = tokens.pad_page
        bh = tokens.btn_h
        if self.layout():
            self.layout().setSpacing(g)
            self.layout().setContentsMargins(p, p, p, p)
        for btn in self._mode_group.buttons():
            btn.setMinimumHeight(bh)
        if self._single_view:
            self._single_view.set_tokens(tokens)

    def _on_mode_click(self, mode_id: str) -> None:
        idx = {"bird": 0, "split": 1, "single": 2}.get(mode_id, 2)
        for btn in self._mode_group.buttons():
            btn.setChecked(btn.property("mode_id") == mode_id)
        self._stack.setCurrentIndex(idx)
        if mode_id == "single" and self._single_view:
            self._single_view.start_playback()
        elif mode_id in ("bird", "split"):
            if self._single_view:
                self._single_view.stop_playback()

    def hideEvent(self, event) -> None:
        if self._single_view and self._stack.currentIndex() == 2:
            self._single_view.stop_playback()
        super().hideEvent(event)
