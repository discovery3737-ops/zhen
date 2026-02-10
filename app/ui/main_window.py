"""主窗口 - 顶部状态栏 + 告警横幅 + 内容区 + 底部 TabBar（Icon+文字）。布局由 layout_profile 驱动。"""

import datetime
import logging

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
    QFrame,
    QPushButton,
    QLabel,
    QSizePolicy,
    QToolButton,
    QStyle,
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QKeySequence, QShortcut

from app.core.config import get_config, save_config
from app.services.modbus_master import get_modbus_master
from app.ui.widgets.alarm_banner import AlarmBanner
from app.ui.layout_profile import get_tokens, LayoutTokens
from app.ui.more_menu_dialog import MoreMenuDialog

logger = logging.getLogger(__name__)

# stack 索引: 0=Dashboard 1=Climate 2=Power 3=Exterior 4=Lighting 5=Environment 6=Camera 7=Diagnostics 8=Settings
IDX_DASHBOARD, IDX_CLIMATE, IDX_POWER, IDX_EXTERIOR = 0, 1, 2, 3
IDX_LIGHTING, IDX_ENV, IDX_CAMERA, IDX_DIAG, IDX_SETTINGS = 4, 5, 6, 7, 8

TAB_ITEMS = [
    ("仪表", "Dashboard", IDX_DASHBOARD, QStyle.StandardPixmap.SP_ComputerIcon),
    ("空调", "Climate", IDX_CLIMATE, QStyle.StandardPixmap.SP_FileDialogContentsView),
    ("电源", "Power", IDX_POWER, QStyle.StandardPixmap.SP_DriveHDIcon),
    ("外设", "Exterior", IDX_EXTERIOR, QStyle.StandardPixmap.SP_DirOpenIcon),
    ("更多", "More", -1, QStyle.StandardPixmap.SP_FileDialogDetailedView),  # -1 = 打开 MoreMenuDialog
]


class MainWindow(QMainWindow):
    """主窗口：StatusBar + AlarmBanner + QStackedWidget + 底部 TabBar（Icon+文字，上图下字）。"""

    def __init__(self, app_state=None, alarm_controller=None, video_manager=None):
        super().__init__()
        self._app_state = app_state
        self._alarm_controller = alarm_controller
        self._video_manager = video_manager
        self._tokens: LayoutTokens = self._resolve_layout_tokens()
        logger.info("布局 profile: %s", self._tokens.profile)
        self._stack = QStackedWidget()
        self._tab_buttons: list[QToolButton] = []
        self._setup_ui()
        self._load_theme()

    def _setup_ui(self):
        cfg = get_config().display
        if cfg.fullscreen:
            self.resize(cfg.width, cfg.height)
        else:
            self.setFixedSize(cfg.width, cfg.height)
        self.setWindowTitle("车载 HMI")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        t = self._tokens
        status_h = min(t.status_bar_h, t.icon_btn_h)

        # 顶部状态栏（压缩 <= 56px，WVGA 仅显示：时间、SOC、告警图标、通讯图标）
        status_bar = self._build_status_bar(status_h)
        layout.addWidget(status_bar)

        # 告警横幅（显式关键字参数，避免 tokens/parent 错位）
        if self._app_state and self._alarm_controller:
            self._alarm_banner = AlarmBanner(
                self._app_state,
                self._alarm_controller,
                tokens=self._tokens,
                parent=self,
            )
            layout.addWidget(self._alarm_banner)

        # 中间内容区
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._stack, 1)

        # 底部 TabBar（Icon + 文字，上图下字，高度 >= icon_btn_h）
        tab_bar = self._build_tab_bar(t)
        layout.addWidget(tab_bar)

        self._load_pages()
        self._update_tab_checked(IDX_DASHBOARD)
        self._stack.setCurrentIndex(IDX_DASHBOARD)

        if cfg.fullscreen:
            esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
            esc_shortcut.activated.connect(self._on_escape_fullscreen)

        QTimer.singleShot(1000, self._apply_backlight_from_config)

    def _apply_backlight_from_config(self) -> None:
        """启动后约 1s 应用 config 中的硬件背光亮度。"""
        try:
            from app.services.backlight import BacklightService
            svc = BacklightService()
            if not svc.is_available():
                return
            cfg = get_config()
            pct = max(5, min(100, getattr(cfg.display, "brightness_percent", 60)))
            svc.set_percent(pct, min_pct=5)
        except Exception as e:
            logger.debug("启动时应用背光亮度失败: %s", e)

    def _resolve_layout_tokens(self) -> LayoutTokens:
        """从 config 获取目标分辨率并选用对应 profile。ui.force_resolution 优先，否则用 display。"""
        cfg = get_config()
        if cfg.ui.force_resolution and len(cfg.ui.force_resolution) >= 2:
            w, h = cfg.ui.force_resolution[0], cfg.ui.force_resolution[1]
        else:
            w, h = cfg.display.width, cfg.display.height
        return get_tokens(width=w, height=h)

    def _build_status_bar(self, height: int) -> QFrame:
        """StatusBar：时间、SOC、告警图标、通讯图标。"""
        bar = QFrame(objectName="statusBar")
        bar.setFixedHeight(height)
        ly = QHBoxLayout(bar)
        ly.setContentsMargins(self._tokens.pad_page, 2, self._tokens.pad_page, 2)
        ly.setSpacing(self._tokens.gap)

        self._status_time = QLabel("--:--:--")
        self._status_time.setObjectName("statusTime")
        ly.addWidget(self._status_time)

        self._status_soc = QLabel("SOC --")
        self._status_soc.setObjectName("statusSoc")
        ly.addWidget(self._status_soc)

        self._status_alarm = QLabel("")
        self._status_alarm.setObjectName("statusAlarm")
        self._status_alarm.setMinimumWidth(24)
        ly.addWidget(self._status_alarm)

        self._status_comm = QLabel("")
        self._status_comm.setObjectName("statusComm")
        self._status_comm.setMinimumWidth(24)
        ly.addWidget(self._status_comm)

        ly.addStretch()

        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_status_time)
        self._time_timer.start(1000)
        self._update_status_time()

        if self._app_state:
            self._app_state.changed.connect(
                self._update_status_data,
                Qt.ConnectionType.QueuedConnection,
            )
        QTimer.singleShot(0, self._update_status_data)

        if self._app_state:
            self._app_state.alarms_changed.connect(
                self._update_status_alarm,
                Qt.ConnectionType.QueuedConnection,
            )

        return bar

    def _update_status_time(self):
        try:
            self._status_time.setText(datetime.datetime.now().strftime("%H:%M:%S"))
        except Exception:
            pass

    def _update_status_data(self):
        if not self._app_state:
            return
        snap = self._app_state.get_snapshot()
        if snap is None:
            return
        p = snap.power
        soc = p.soc_x10
        if soc is not None:
            self._status_soc.setText(f"SOC {soc / 10:.0f}%")
        else:
            self._status_soc.setText("SOC --")

        comm = snap.comm
        online = sum(1 for c in comm.values() if getattr(c, "online", False))
        total = len(comm) if comm else 0
        self._status_comm.setText("●" if online > 0 else "○")
        self._status_comm.setToolTip(f"通讯 {online}/{total}")

    def _update_status_alarm(self, alarms=None):
        if alarms is None:
            alarms = []
        has_unacked = any(not getattr(a, "ack", True) for a in alarms) if alarms else False
        self._status_alarm.setText("⚠" if has_unacked else "")
        self._status_alarm.setToolTip("有未确认告警" if has_unacked else "")

    def _build_tab_bar(self, t: LayoutTokens) -> QWidget:
        tab_bar = QWidget(objectName="tabBar")
        top_m = bot_m = t.tab_bar_v_margin
        content_needed = t.icon_btn_h
        h = max(t.tab_bar_h, content_needed + top_m + bot_m)
        tab_bar.setFixedHeight(h)
        ly = QHBoxLayout(tab_bar)
        ly.setContentsMargins(t.gap, top_m, t.gap, bot_m)
        ly.setSpacing(t.gap)

        # WVGA 图标 24~26px，WXGA 28~32px，保证不挤不裁切
        is_wvga = t.profile == "WVGA"
        icon_sz = 25 if is_wvga else 30
        style = self.style()
        for label, _key, idx, sp in TAB_ITEMS:
            btn = QToolButton(objectName="tabButton")
            btn.setText(label)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setAutoRaise(True)
            btn.setProperty("tab", True)
            btn.setProperty("compact", is_wvga)
            btn.setIcon(style.standardIcon(sp))
            btn.setIconSize(QSize(icon_sz, icon_sz))
            btn.setMinimumHeight(t.icon_btn_h)
            btn.setMinimumWidth(t.icon_btn_h)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.setCheckable(True)
            btn.setProperty("tab_index", idx)
            btn.clicked.connect(lambda checked, i=idx: self._on_tab_click(i))
            ly.addWidget(btn, 1)
            self._tab_buttons.append(btn)

        return tab_bar

    def _load_pages(self):
        from app.ui.pages import (
            DashboardPage,
            HvacPage,
            PowerPage,
            ExteriorPage,
            LightingPage,
            EnvironmentPage,
            CameraPage,
            DiagnosticsPage,
            SettingsPage,
        )

        t = self._tokens
        cfg_get = get_config
        save_cfg = save_config
        mm_get = get_modbus_master

        pages = [
            DashboardPage(app_state=self._app_state, on_switch_page=self._on_switch_page),
            HvacPage(app_state=self._app_state),
            PowerPage(app_state=self._app_state),
            ExteriorPage(app_state=self._app_state),
            LightingPage(app_state=self._app_state),
            EnvironmentPage(app_state=self._app_state),
            CameraPage(video_manager=self._video_manager),
            DiagnosticsPage(app_state=self._app_state, alarm_controller=self._alarm_controller),
            SettingsPage(
                config_getter=cfg_get,
                save_config_fn=save_cfg,
                app_state=self._app_state,
                modbus_master_getter=mm_get,
                alarm_controller=self._alarm_controller,
            ),
        ]
        for p in pages:
            self._stack.addWidget(p)
            if hasattr(p, "set_tokens") and t:
                p.set_tokens(t)

    # sub_index 1-5: Lighting/Env/Diag/Settings/Camera -> stack 4-8
    _SUB_TO_STACK = {1: 4, 2: 5, 3: 7, 4: 8, 5: 6}

    def _on_switch_page(self, tab_index: int, sub_index: int | None = None):
        """Dashboard 跳转回调。tab_index 0-4；tab_index=4 时 sub_index 1-5 -> stack 4-8。"""
        if tab_index <= 3:
            self._stack.setCurrentIndex(tab_index)
            self._update_tab_checked(tab_index)
        elif tab_index == 4 and sub_index is not None and sub_index in self._SUB_TO_STACK:
            stack_idx = self._SUB_TO_STACK[sub_index]
            self._stack.setCurrentIndex(stack_idx)
            self._update_tab_checked(4)

    def _on_tab_click(self, index: int):
        if index == -1:
            # More: 打开 MoreMenuDialog
            dlg = MoreMenuDialog(tokens=self._tokens, parent=self)
            dlg.page_selected.connect(self._on_more_page_selected)
            dlg.exec()
            return
        self._stack.setCurrentIndex(index)
        self._update_tab_checked(index)

    def _on_more_page_selected(self, stack_index: int):
        self._stack.setCurrentIndex(stack_index)
        self._update_tab_checked(4)

    def _update_tab_checked(self, active_tab: int):
        """active_tab 0-3 表示主 Tab 选中；4 表示 More 选中（当前在 Lighting/Env/Camera/Diag/Settings）。"""
        for i, btn in enumerate(self._tab_buttons):
            tab_idx = TAB_ITEMS[i][2]
            if tab_idx == -1:
                btn.setChecked(active_tab == 4)
            else:
                btn.setChecked(active_tab == tab_idx)

    def _on_escape_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()

    def _load_theme(self):
        theme_path = get_config().theme_path
        if not theme_path.exists():
            logger.warning("主题文件不存在: %s", theme_path)
            return
        with open(theme_path, "r", encoding="utf-8") as f:
            qss = f.read()
        t = self._tokens
        qss = (
            qss.replace("{{FONT_BASE}}", str(t.font_base))
            .replace("{{FONT_TITLE}}", str(t.font_title))
            .replace("{{FONT_BIG}}", str(t.font_big))
            .replace("{{FONT_SMALL}}", str(t.font_small))
            .replace("{{PAD_PAGE}}", str(t.pad_page))
            .replace("{{PAD_CARD}}", str(t.pad_card))
            .replace("{{GAP}}", str(t.gap))
            .replace("{{BTN_H}}", str(t.btn_h))
            .replace("{{BTN_H_KEY}}", str(t.btn_h_key))
            .replace("{{ICON_BTN_H}}", str(t.icon_btn_h))
            .replace("{{STATUS_BAR_H}}", str(t.status_bar_h))
            .replace("{{TAB_BAR_H}}", str(t.tab_bar_h))
            .replace("{{SCROLL_HANDLE_MIN}}", str(t.scroll_handle_min))
        )
        self.setStyleSheet(qss)
        logger.info("已加载主题: %s (profile=%s)", theme_path, t.profile)
