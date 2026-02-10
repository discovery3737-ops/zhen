"""设置页面 - 显示/语言、时间、通讯、告警阈值、维护调试。适配 800×480/1280×800 触控。"""

import datetime
import shutil
import time
import zipfile
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer

from app.ui.pages.base import PageBase
from app.core.config import (
    get_config,
    save_config,
    load_config,
    AppConfig,
    get_config_path,
    get_last_save_error,
)
from app.ui.layout_profile import LayoutTokens, get_tokens
from app.ui.widgets.long_press_button import LongPressButton
from app.ui.widgets import CompactToggleRow, TwoColumnFormRow
from app.ui.widgets.pin_pad_dialog import ask_maintenance_pin

try:
    from app.services.backlight import BacklightService, BacklightError
    _backlight_service: BacklightService | None = BacklightService()
except Exception:
    _backlight_service = None

# 项目根目录（与 config 一致）
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"
_LOGS_DIR = _ROOT / "logs"
_EXPORTS_DIR = _ROOT / "exports"


def _make_card(title: str, tokens: LayoutTokens | None, parent: QWidget | None = None) -> QFrame:
    """Card 风格分区，布局由 tokens 驱动"""
    t = tokens
    g, p = (t.gap if t else 10), (t.pad_card if t else 10)
    card = QFrame(objectName="card", parent=parent)
    ly = QVBoxLayout(card)
    ly.setSpacing(g)
    ly.setContentsMargins(p, p, p, p)
    lbl = QLabel(title, objectName="cardTitle")
    ly.addWidget(lbl)
    return card


class _CollapsibleSection(QFrame):
    """可折叠分区：标题按钮 + 内容，用于 Display/Comm/Alarm/Service。样式由 theme.qss collapsibleHeaderBtn 统一。"""

    def __init__(self, title: str, tokens: LayoutTokens | None, parent=None):
        super().__init__(parent)
        self._title = title
        self._content: QWidget | None = None
        self._expanded = False
        self._tokens = tokens
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        self._header_btn = QPushButton(objectName="collapsibleHeaderBtn")
        self._header_btn.setCheckable(True)
        bh = tokens.btn_h if tokens else 44
        self._header_btn.setMinimumHeight(bh)
        self._header_btn.clicked.connect(self._toggle)
        ly.addWidget(self._header_btn)
        self._update_text()

    def set_content(self, w: QWidget) -> None:
        self._content = w
        self._content.setVisible(self._expanded)
        self.layout().addWidget(self._content)

    def _update_text(self) -> None:
        self._header_btn.setText(("▼ " if self._expanded else "▶ ") + self._title)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._header_btn.setChecked(expanded)
        self._update_text()
        if self._content:
            self._content.setVisible(expanded)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self.set_expanded(self._expanded)


class SettingsPage(PageBase):
    """设置页：显示/语言、时间、通讯、告警阈值、维护。控件值与 config 双向绑定，点击保存才落盘。"""

    def __init__(
        self,
        config_getter=None,
        save_config_fn=None,
        app_state=None,
        modbus_master_getter=None,
        alarm_controller=None,
    ):
        super().__init__("设置")
        self._config_getter = config_getter or get_config
        self._save_config_fn = save_config_fn or save_config
        self._app_state = app_state
        self._modbus_master_getter = modbus_master_getter or (lambda: None)
        self._alarm_controller = alarm_controller
        self._config = self._config_getter()
        self._tokens: LayoutTokens | None = get_tokens()
        self._maintenance_verified = False
        self._maintenance_session_timer: QTimer | None = None
        self._section_service: _CollapsibleSection | None = None
        self._setup_ui()
        self._load_from_config()
        self._start_time_timer()

    def _setup_ui(self):
        root = self.layout()
        if root:
            while root.count():
                item = root.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        t = self._tokens
        g, p = (t.gap if t else 8), (t.pad_page if t else 10)
        inner = QWidget()
        ly = QVBoxLayout(inner)
        ly.setSpacing(g)
        ly.setContentsMargins(p, p, p, p)

        title = QLabel("设置")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(title)

        # Display：显示与语言 + 屏幕亮度卡片 + 时间与日期（默认展开）
        section_display = _CollapsibleSection("Display", t, self)
        section_display.set_expanded(True)
        display_content = QWidget()
        display_ly = QVBoxLayout(display_content)
        display_ly.setSpacing(g)
        card_a = _make_card("显示与语言", t, self)
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Light", "Dark"])
        card_a.layout().addWidget(TwoColumnFormRow("主题模式", self._theme_combo, tokens=t))
        self._language_combo = QComboBox()
        self._language_combo.addItems(["zh_CN", "en_US"])
        card_a.layout().addWidget(TwoColumnFormRow("语言", self._language_combo, tokens=t))
        bhk = t.btn_h_key if t else 52
        self._apply_restart_btn = QPushButton("应用并重启提示")
        self._apply_restart_btn.setMinimumHeight(bhk)
        self._apply_restart_btn.clicked.connect(self._on_apply_restart)
        card_a.layout().addWidget(self._apply_restart_btn)
        display_ly.addWidget(card_a)

        # 车机风格亮度卡片：大滑条 + 实时预览（松手保存）+ 恢复默认长按
        self._backlight_available = _backlight_service is not None and _backlight_service.is_available()
        card_brightness = QFrame(objectName="brightnessCard", parent=self)
        card_brightness.setProperty("disabled", not self._backlight_available)
        if t:
            card_brightness.setStyleSheet("")  # 由 theme.qss 统一
        ly_bc = QVBoxLayout(card_brightness)
        ly_bc.setSpacing(g)
        ly_bc.setContentsMargins(t.pad_card if t else 10, t.pad_card if t else 10, t.pad_card if t else 10, t.pad_card if t else 10)
        row_title = QHBoxLayout()
        row_title.addWidget(QLabel("☀", objectName="accent"))  # 简单图标
        row_title.addWidget(QLabel("屏幕亮度", objectName="cardTitle"))
        row_title.addStretch()
        ly_bc.addLayout(row_title)
        row_slider = QHBoxLayout()
        self._screen_brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self._screen_brightness_slider.setObjectName("brightnessSlider")
        self._screen_brightness_slider.setRange(0, 100)
        self._screen_brightness_slider.setMinimumHeight(t.btn_h if t else 44)
        self._screen_brightness_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._screen_brightness_slider.valueChanged.connect(self._on_screen_brightness_value_changed)
        self._screen_brightness_slider.sliderReleased.connect(self._on_screen_brightness_released)
        right_brightness = QWidget()
        right_ly = QVBoxLayout(right_brightness)
        right_ly.setContentsMargins(0, 0, 0, 0)
        right_ly.setSpacing(0)
        lbl_current = QLabel("当前屏幕亮度", objectName="small")
        self._screen_brightness_label = QLabel("--")
        self._screen_brightness_label.setObjectName("brightnessPercent")
        self._screen_brightness_label.setMinimumWidth(56)
        self._screen_brightness_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_ly.addWidget(lbl_current)
        right_ly.addWidget(self._screen_brightness_label)
        row_slider.addWidget(self._screen_brightness_slider, stretch=7)
        row_slider.addWidget(right_brightness, stretch=0)
        ly_bc.addLayout(row_slider)
        self._screen_brightness_hint = QLabel("拖动即时预览，松手保存", objectName="small")
        self._screen_brightness_hint.setWordWrap(True)
        ly_bc.addWidget(self._screen_brightness_hint)
        row_shortcuts = QHBoxLayout()
        self._btn_night = QPushButton("夜间")
        self._btn_night.setProperty("compact", "true")
        self._btn_night.setMinimumHeight(t.btn_h if t else 44)
        self._btn_night.clicked.connect(lambda: self._set_brightness_preset(15))
        self._btn_day = QPushButton("日间")
        self._btn_day.setProperty("primary", "true")
        self._btn_day.setProperty("compact", "true")
        self._btn_day.setMinimumHeight(t.btn_h if t else 44)
        self._btn_day.clicked.connect(lambda: self._set_brightness_preset(70))
        row_shortcuts.addWidget(self._btn_night)
        row_shortcuts.addWidget(self._btn_day)
        ly_bc.addLayout(row_shortcuts)
        self._screen_brightness_debounce_timer = QTimer(self)
        self._screen_brightness_debounce_timer.setSingleShot(True)
        self._screen_brightness_debounce_timer.timeout.connect(self._apply_screen_brightness_preview)
        self._screen_brightness_last_write_time = 0.0
        self._screen_brightness_saved_timer = QTimer(self)
        self._screen_brightness_saved_timer.setSingleShot(True)
        self._screen_brightness_saved_timer.timeout.connect(self._restore_brightness_hint_text)
        self._restore_default_brightness_btn = LongPressButton("恢复默认亮度", tokens=t)
        self._restore_default_brightness_btn.setDanger(True)
        self._restore_default_brightness_btn.setHoldMs(1500)
        self._restore_default_brightness_btn.confirmed.connect(self._on_restore_default_brightness)
        if not self._backlight_available:
            self._screen_brightness_slider.setEnabled(False)
            self._screen_brightness_label.setEnabled(False)
            self._screen_brightness_hint.setText("当前屏幕不支持硬件亮度控制")
            self._restore_default_brightness_btn.setEnabled(False)
            self._restore_default_brightness_btn.setToolTip("当前屏幕不支持硬件亮度控制")
            self._btn_night.setEnabled(False)
            self._btn_day.setEnabled(False)
        ly_bc.addWidget(self._restore_default_brightness_btn)
        display_ly.addWidget(card_brightness)
        card_b = _make_card("时间与日期", t, self)
        self._time_label = QLabel("--:--:--")
        self._time_label.setObjectName("bigNumber")
        card_b.layout().addWidget(TwoColumnFormRow("当前时间", self._time_label, tokens=t))
        self._timezone_combo = QComboBox()
        self._timezone_combo.addItems(["Asia/Shanghai", "America/Phoenix"])
        card_b.layout().addWidget(TwoColumnFormRow("时区", self._timezone_combo, tokens=t))
        self._ntp_btn = QPushButton("同步时间（NTP）")
        self._ntp_btn.setMinimumHeight(bhk)
        self._ntp_btn.clicked.connect(self._on_ntp_sync)
        card_b.layout().addWidget(self._ntp_btn)
        display_ly.addWidget(card_b)
        section_display.set_content(display_content)
        ly.addWidget(section_display)

        # Comm：通讯（默认折叠）
        section_comm = _CollapsibleSection("Comm", t, self)
        section_comm.set_expanded(False)
        card_c = _make_card("通讯（Modbus RS485）", t, self)
        self._port_edit = QLineEdit()
        self._port_edit.setPlaceholderText("/dev/ttyUSB0")
        card_c.layout().addWidget(TwoColumnFormRow("串口端口", self._port_edit, tokens=t))
        self._baudrate_combo = QComboBox()
        self._baudrate_combo.addItems(["9600", "19200", "38400", "115200"])
        card_c.layout().addWidget(TwoColumnFormRow("波特率", self._baudrate_combo, tokens=t))
        self._parity_combo = QComboBox()
        self._parity_combo.addItems(["N", "E", "O"])
        card_c.layout().addWidget(TwoColumnFormRow("奇偶校验", self._parity_combo, tokens=t))
        self._timeout_edit = QLineEdit()
        self._timeout_edit.setPlaceholderText("0.1~1.0")
        card_c.layout().addWidget(TwoColumnFormRow("超时 (s)", self._timeout_edit, tokens=t))
        self._comm_status_label = QLabel("--")
        card_c.layout().addWidget(TwoColumnFormRow("通讯状态", self._comm_status_label, tokens=t))
        self._reconnect_btn = QPushButton("保存并重新连接")
        self._reconnect_btn.setMinimumHeight(bhk)
        self._reconnect_btn.clicked.connect(self._on_reconnect)
        card_c.layout().addWidget(self._reconnect_btn)
        section_comm.set_content(card_c)
        ly.addWidget(section_comm)

        # Alarm：告警阈值（默认折叠）
        section_alarm = _CollapsibleSection("Alarm", t, self)
        section_alarm.set_expanded(False)
        card_d = _make_card("告警阈值（软件侧）", t, self)
        self._co_warn_edit = QLineEdit()
        card_d.layout().addWidget(TwoColumnFormRow("CO 警告 (ppm)", self._co_warn_edit, tokens=t))
        self._co_crit_edit = QLineEdit()
        card_d.layout().addWidget(TwoColumnFormRow("CO 严重 (ppm)", self._co_crit_edit, tokens=t))
        self._lpg_warn_edit = QLineEdit()
        card_d.layout().addWidget(TwoColumnFormRow("LPG 警告 (%LEL)", self._lpg_warn_edit, tokens=t))
        self._lpg_crit_edit = QLineEdit()
        card_d.layout().addWidget(TwoColumnFormRow("LPG 严重 (%LEL)", self._lpg_crit_edit, tokens=t))
        self._save_thresholds_btn = QPushButton("保存阈值")
        self._save_thresholds_btn.setMinimumHeight(bhk)
        self._save_thresholds_btn.clicked.connect(self._on_save_thresholds)
        card_d.layout().addWidget(self._save_thresholds_btn)
        section_alarm.set_content(card_d)
        ly.addWidget(section_alarm)

        # 维护与调试（默认收起）；展开时先验证 PIN，会话期内可操作危险项
        section_service = _CollapsibleSection("维护与调试", t, self)
        section_service.set_expanded(False)
        self._section_service = section_service
        card_e = _make_card("危险操作", t, self)
        self._dev_mode_row = CompactToggleRow("开发模式", tokens=t)
        card_e.layout().addWidget(self._dev_mode_row)
        self._export_logs_btn = QPushButton("导出日志")
        self._export_logs_btn.setMinimumHeight(bhk)
        self._export_logs_btn.clicked.connect(self._on_export_logs)
        card_e.layout().addWidget(self._export_logs_btn)
        self._export_config_btn = QPushButton("导出配置")
        self._export_config_btn.setMinimumHeight(bhk)
        self._export_config_btn.clicked.connect(self._on_export_config)
        card_e.layout().addWidget(self._export_config_btn)
        self._reset_btn = LongPressButton("长按恢复默认设置", tokens=t)
        self._reset_btn.setDanger(True)
        self._reset_btn.setHoldMs(2000)
        self._reset_btn.confirmed.connect(self._on_reset_defaults)
        card_e.layout().addWidget(self._reset_btn)
        section_service.set_content(card_e)
        ly.addWidget(section_service)

        # 维护区：点击展开时先验证 PIN，未验证时按钮禁用
        section_service._header_btn.clicked.disconnect(section_service._toggle)
        section_service._header_btn.clicked.connect(self._on_service_header_clicked)
        self._update_maintenance_buttons()

        ly.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        if self._app_state:
            self._app_state.changed.connect(self._on_comm_changed, Qt.ConnectionType.QueuedConnection)
        QTimer.singleShot(0, self._refresh_comm_status)

    def showEvent(self, event):
        super().showEvent(event)
        if self._backlight_available and _backlight_service is not None:
            _backlight_service.apply_percent_from_config(self._config_getter())

    def _on_screen_brightness_value_changed(self, value: int) -> None:
        self._screen_brightness_label.setText(f"{value}%")
        self._screen_brightness_debounce_timer.stop()
        self._screen_brightness_debounce_timer.start(80)

    def _apply_screen_brightness_preview(self) -> None:
        """去抖 + 限速：仅设置硬件背光（实时预览），不写 config。"""
        if not self._backlight_available or _backlight_service is None:
            return
        value = self._screen_brightness_slider.value()
        now = time.time()
        if now - self._screen_brightness_last_write_time < 0.08:
            return
        self._screen_brightness_last_write_time = now
        effective = max(5, value) if value > 0 else 5
        try:
            _backlight_service.set_percent(effective, min_pct=5)
        except BacklightError as e:
            self._screen_brightness_hint.setText(str(e))
            return
        except Exception as e:
            self._screen_brightness_hint.setText(f"设置失败: {e}")
            return
        if value == 0:
            self._screen_brightness_hint.setText("为避免全黑，已限制最低亮度为 5%")
        elif self._screen_brightness_hint.text() == "为避免全黑，已限制最低亮度为 5%":
            self._screen_brightness_hint.setText("拖动即时预览，松手保存")

    def _on_screen_brightness_released(self) -> None:
        """松手：写 config 并保存，成功轻提示「已保存」；失败弹窗显示路径、原因与 chown 提示。"""
        value = self._screen_brightness_slider.value()
        pct = max(5, min(100, value))
        self._config.display.brightness_percent = pct
        if self._backlight_available and _backlight_service is not None:
            try:
                _backlight_service.set_percent(pct, min_pct=5)
            except (BacklightError, Exception):
                pass
        if self._save_config_fn(self._config):
            self._screen_brightness_hint.setText("已保存")
            self._screen_brightness_saved_timer.stop()
            self._screen_brightness_saved_timer.start(2000)
        else:
            self._show_save_error_dialog()

    def _restore_brightness_hint_text(self) -> None:
        if self._backlight_available:
            self._screen_brightness_hint.setText("拖动即时预览，松手保存")
        else:
            self._screen_brightness_hint.setText("当前屏幕不支持硬件亮度控制")

    def _show_save_error_dialog(self) -> None:
        """保存失败时弹窗：异常摘要 + config.yaml 绝对路径 + 权限修复提示（chown）+ logs。"""
        path_str = get_config_path()
        reason = get_last_save_error() or "未知错误"
        msg = (
            f"配置保存失败。\n\n原因：{reason}\n\n"
            f"配置文件路径：\n{path_str}\n\n"
            "若为权限问题，可在终端执行（将 <用户> 改为当前用户名）：\n"
            "  sudo chown <用户> <配置文件路径>\n\n"
            "详细日志请查看：logs/app.log"
        )
        QMessageBox.warning(self, "保存失败", msg, QMessageBox.StandardButton.Ok)

    def _set_brightness_preset(self, pct: int) -> None:
        """一键预设：夜间 15% / 日间 70%，立即生效并保存到 config。"""
        pct = max(5, min(100, pct))
        if not self._backlight_available or _backlight_service is None:
            self._screen_brightness_hint.setText("当前屏幕不支持硬件亮度控制")
            return
        try:
            _backlight_service.set_percent(pct, min_pct=5)
        except BacklightError as e:
            self._screen_brightness_hint.setText(str(e))
            return
        self._screen_brightness_slider.setValue(pct)
        self._screen_brightness_label.setText(f"{pct}%")
        self._config.display.brightness_percent = pct
        if self._save_config_fn(self._config):
            self._screen_brightness_hint.setText("已保存")
            self._screen_brightness_saved_timer.stop()
            self._screen_brightness_saved_timer.start(2000)
        else:
            self._show_save_error_dialog()

    def _on_restore_default_brightness(self) -> None:
        """长按确认后：设为默认亮度、写硬件、写 config 并保存。"""
        cfg = self._config
        default_pct = getattr(getattr(cfg, "display", None), "default_brightness_percent", 60)
        default_pct = max(5, min(100, int(default_pct)))
        if not self._backlight_available or _backlight_service is None:
            self._screen_brightness_hint.setText("当前屏幕不支持硬件亮度控制")
            return
        try:
            _backlight_service.set_percent(default_pct, min_pct=5)
        except BacklightError as e:
            self._screen_brightness_hint.setText(str(e))
            return
        self._screen_brightness_slider.setValue(default_pct)
        self._screen_brightness_label.setText(f"{default_pct}%")
        cfg.display.brightness_percent = default_pct
        if self._save_config_fn(cfg):
            self._screen_brightness_hint.setText(f"已恢复默认亮度：{default_pct}%")
            self._screen_brightness_saved_timer.stop()
            self._screen_brightness_saved_timer.start(2500)
        else:
            self._show_save_error_dialog()

    def _load_from_config(self) -> None:
        """从 config 加载到控件（进入页面时调用）；进入设置页时应用一次保存的亮度（防抖在 backlight 内）。"""
        cfg = self._config
        bp = max(0, min(100, getattr(cfg.display, "brightness_percent", 60)))
        self._screen_brightness_slider.setValue(bp)
        self._screen_brightness_label.setText(f"{bp}%")
        if self._backlight_available and _backlight_service is not None:
            _backlight_service.apply_percent_from_config(cfg)
        theme = getattr(cfg.ui, "theme_mode", "light")
        self._theme_combo.setCurrentText(theme.capitalize() if theme else "Light")
        self._language_combo.setCurrentText(cfg.ui.language)
        self._timezone_combo.setCurrentText(cfg.system.timezone)
        self._port_edit.setText(cfg.modbus.port)
        self._baudrate_combo.setCurrentText(str(cfg.modbus.baudrate))
        self._parity_combo.setCurrentText(cfg.modbus.parity)
        self._timeout_edit.setText(str(cfg.modbus.timeout))
        at = cfg.alarm_thresholds
        self._co_warn_edit.setText(str(at.co_warn))
        self._co_crit_edit.setText(str(at.co_crit))
        self._lpg_warn_edit.setText(f"{at.lpg_warn_lel_x10 / 10:.1f}")
        self._lpg_crit_edit.setText(f"{at.lpg_crit_lel_x10 / 10:.1f}")
        self._dev_mode_row.set_checked(cfg.dev_mode)

    def _apply_to_config(self) -> None:
        """从控件写回 config（保存时调用，不落盘）"""
        cfg = self._config
        cfg.display.brightness_percent = max(0, min(100, self._screen_brightness_slider.value()))
        cfg.ui.theme_mode = self._theme_combo.currentText().lower()
        cfg.ui.language = self._language_combo.currentText()
        cfg.system.timezone = self._timezone_combo.currentText()
        cfg.modbus.port = self._port_edit.text().strip() or "/dev/ttyUSB0"
        cfg.modbus.baudrate = int(self._baudrate_combo.currentText())
        cfg.modbus.parity = self._parity_combo.currentText()
        try:
            t = float(self._timeout_edit.text().strip())
            cfg.modbus.timeout = max(0.1, min(1.0, t))
        except (ValueError, TypeError):
            cfg.modbus.timeout = 0.2
        try:
            cfg.alarm_thresholds.co_warn = int(self._co_warn_edit.text().strip())
        except (ValueError, TypeError):
            pass
        try:
            cfg.alarm_thresholds.co_crit = int(self._co_crit_edit.text().strip())
        except (ValueError, TypeError):
            pass
        try:
            cfg.alarm_thresholds.lpg_warn_lel_x10 = int(float(self._lpg_warn_edit.text().strip()) * 10)
        except (ValueError, TypeError):
            pass
        try:
            cfg.alarm_thresholds.lpg_crit_lel_x10 = int(float(self._lpg_crit_edit.text().strip()) * 10)
        except (ValueError, TypeError):
            pass
        cfg.dev_mode = self._dev_mode_row.is_checked()

    def _start_time_timer(self) -> None:
        def tick():
            try:
                now = datetime.datetime.now()
                self._time_label.setText(now.strftime("%Y-%m-%d %H:%M:%S"))
            except Exception:
                pass
        tick()
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(tick)
        self._time_timer.start(1000)

    def _refresh_comm_status(self) -> None:
        try:
            mm = self._modbus_master_getter()
            if mm:
                s = mm.get_link_summary()
                self._comm_status_label.setText(f"在线 {s['online_slaves']} 从站，错误计数 {s['total_errors']}")
                return
        except Exception:
            pass
        if self._app_state:
            snap = self._app_state.get_snapshot()
            comm = snap.comm if snap else {}
            online = sum(1 for c in comm.values() if getattr(c, "online", False))
            total = sum(getattr(c, "error_count", 0) for c in comm.values())
            self._comm_status_label.setText(f"在线 {online} 从站，错误计数 {total}")
        else:
            self._comm_status_label.setText("--")

    def _on_comm_changed(self, _) -> None:
        self._refresh_comm_status()

    def _on_service_header_clicked(self) -> None:
        """维护与调试：展开前先验证 PIN，通过后进入维护会话。"""
        sec = self._section_service
        if not sec:
            return
        if sec._expanded:
            sec.set_expanded(False)
            return
        cfg = self._config_getter()
        pin = getattr(cfg.security, "maintenance_pin", "1234") or "1234"
        if not ask_maintenance_pin(pin, tokens=self._tokens, parent=self):
            return
        self._maintenance_verified = True
        sec.set_expanded(True)
        self._start_maintenance_session()
        self._update_maintenance_buttons()

    def _start_maintenance_session(self) -> None:
        """启动维护会话计时，到期自动退出并提示。"""
        if self._maintenance_session_timer:
            self._maintenance_session_timer.stop()
            self._maintenance_session_timer = None
        cfg = self._config_getter()
        timeout_s = getattr(getattr(cfg, "security", None), "session_timeout_s", 900) or 900
        self._maintenance_session_timer = QTimer(self)
        self._maintenance_session_timer.setSingleShot(True)

        def _on_timeout() -> None:
            self._maintenance_verified = False
            self._maintenance_session_timer = None
            self._update_maintenance_buttons()
            if self._section_service and self._section_service._expanded:
                self._section_service.set_expanded(False)
            QMessageBox.information(
                self,
                "维护会话已过期",
                "维护会话已到期，请重新输入 PIN 后继续操作。",
                QMessageBox.StandardButton.Ok,
            )

        self._maintenance_session_timer.timeout.connect(_on_timeout)
        self._maintenance_session_timer.start(timeout_s * 1000)

    def _update_maintenance_buttons(self) -> None:
        """根据维护验证状态启用/禁用危险操作按钮并设置提示。"""
        enabled = self._maintenance_verified
        hint = "需要维护 PIN" if not enabled else ""
        for btn in (
            getattr(self, "_reconnect_btn", None),
            getattr(self, "_save_thresholds_btn", None),
            getattr(self, "_export_logs_btn", None),
            getattr(self, "_export_config_btn", None),
            getattr(self, "_reset_btn", None),
        ):
            if btn is not None:
                btn.setEnabled(enabled)
                btn.setToolTip(hint)

    def _on_apply_restart(self) -> None:
        r = QMessageBox.question(
            self,
            "应用并重启",
            "将保存当前设置。部分设置需重启应用后生效，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        self._apply_to_config()
        if self._save_config_fn(self._config):
            QMessageBox.information(self, "保存成功", "配置已保存。请手动重启应用使部分设置生效。")
        else:
            self._show_save_error_dialog()

    def _on_ntp_sync(self) -> None:
        QMessageBox.information(self, "同步时间", "已触发同步请求（TODO）")

    def _on_reconnect(self) -> None:
        if not self._maintenance_verified:
            return
        self._apply_to_config()
        self._config.modbus.use_mock = False
        if self._save_config_fn(self._config):
            try:
                mm = self._modbus_master_getter()
                if mm and hasattr(mm, "restart_with_config"):
                    mm.restart_with_config(self._config)
                    QMessageBox.information(self, "重新连接", "配置已保存，Modbus 正在后台重新连接。")
                else:
                    QMessageBox.information(self, "重新连接", "配置已保存。Modbus 未就绪或需手动重启应用。")
            except Exception as e:
                QMessageBox.warning(self, "重新连接", f"配置已保存，但重启连接失败：{e}")
        else:
            self._show_save_error_dialog()

    def _on_save_thresholds(self) -> None:
        if not self._maintenance_verified:
            return
        self._apply_to_config()
        if self._save_config_fn(self._config):
            QMessageBox.information(self, "保存成功", "告警阈值已保存，AlarmEngine 将读取最新阈值生效。")
        else:
            self._show_save_error_dialog()

    def _on_export_logs(self) -> None:
        if not self._maintenance_verified:
            return
        if not _LOGS_DIR.exists():
            QMessageBox.information(self, "导出日志", "暂无日志")
            return
        log_files = [f for f in _LOGS_DIR.iterdir() if f.is_file()]
        if not log_files:
            QMessageBox.information(self, "导出日志", "暂无日志")
            return
        _EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = _EXPORTS_DIR / f"logs_{ts}.zip"
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in log_files:
                    zf.write(f, f"logs/{f.name}")
            QMessageBox.information(self, "导出日志", f"日志已导出至：\n{zip_path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"无法导出日志：{e}")

    def _on_export_config(self) -> None:
        if not self._maintenance_verified:
            return
        _EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = _EXPORTS_DIR / f"config_{ts}.yaml"
        try:
            if _CONFIG_PATH.exists():
                shutil.copy2(_CONFIG_PATH, dest)
                QMessageBox.information(self, "导出配置", f"配置已导出至：\n{dest}")
            else:
                QMessageBox.warning(self, "导出失败", "config.yaml 不存在")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"无法导出配置：{e}")

    def _on_reset_defaults(self) -> None:
        if not self._maintenance_verified:
            return
        r = QMessageBox.question(
            self,
            "恢复默认设置",
            "将备份现有配置并恢复默认设置。需手动重启应用生效。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            _EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = _EXPORTS_DIR / f"config_backup_{ts}.yaml"
            if _CONFIG_PATH.exists():
                shutil.copy2(_CONFIG_PATH, backup)
            default_cfg = AppConfig()
            if self._save_config_fn(default_cfg):
                from app.core.config import set_config
                set_config(default_cfg)
                self._config = default_cfg
                self._load_from_config()
                QMessageBox.information(self, "恢复默认", f"已备份至 {backup}\n默认设置已应用，请手动重启应用。")
            else:
                self._show_save_error_dialog()
        except Exception as e:
            QMessageBox.warning(self, "失败", f"恢复默认失败：{e}")
