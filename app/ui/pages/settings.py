"""设置页面 - 显示/语言、时间、通讯、告警阈值、维护调试。适配 800×480/1280×800 触控。"""

import datetime
import shutil
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
)
from PyQt6.QtCore import Qt, QTimer

from app.ui.pages.base import PageBase
from app.core.config import get_config, save_config, load_config, AppConfig
from app.ui.layout_profile import LayoutTokens, get_tokens
from app.ui.widgets.long_press_button import LongPressButton
from app.ui.widgets import CompactToggleRow, TwoColumnFormRow

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

        # Display：显示与语言 + 时间与日期（默认展开）
        section_display = _CollapsibleSection("Display", t, self)
        section_display.set_expanded(True)
        display_content = QWidget()
        display_ly = QVBoxLayout(display_content)
        display_ly.setSpacing(g)
        card_a = _make_card("显示与语言", t, self)
        self._brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self._brightness_slider.setRange(0, 100)
        card_a.layout().addWidget(TwoColumnFormRow("亮度", self._brightness_slider, tokens=t))
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

        # Service：维护与调试（默认折叠），危险操作 LongPress + 倒计时
        section_service = _CollapsibleSection("Service", t, self)
        section_service.set_expanded(False)
        card_e = _make_card("维护与调试", t, self)
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

        ly.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        if self._app_state:
            self._app_state.changed.connect(self._on_comm_changed, Qt.ConnectionType.QueuedConnection)
        QTimer.singleShot(0, self._refresh_comm_status)

    def _load_from_config(self) -> None:
        """从 config 加载到控件（进入页面时调用）"""
        cfg = self._config
        self._brightness_slider.setValue(getattr(cfg.ui, "brightness", 80))
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
        cfg.ui.brightness = self._brightness_slider.value()
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
            QMessageBox.warning(self, "保存失败", "无法写入 config.yaml，请检查权限。")

    def _on_ntp_sync(self) -> None:
        QMessageBox.information(self, "同步时间", "已触发同步请求（TODO）")

    def _on_reconnect(self) -> None:
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
            QMessageBox.warning(self, "保存失败", "无法写入 config.yaml")

    def _on_save_thresholds(self) -> None:
        self._apply_to_config()
        if self._save_config_fn(self._config):
            QMessageBox.information(self, "保存成功", "告警阈值已保存，AlarmEngine 将读取最新阈值生效。")
        else:
            QMessageBox.warning(self, "保存失败", "无法写入 config.yaml")

    def _on_export_logs(self) -> None:
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
                QMessageBox.warning(self, "失败", "无法写入 config.yaml")
        except Exception as e:
            QMessageBox.warning(self, "失败", f"恢复默认失败：{e}")
