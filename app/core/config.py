"""应用配置 - 支持 config.yaml，不存在则使用默认值"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 项目根目录（app 的上级）
_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"

# 最近一次保存失败时的错误信息与路径（供 UI 弹窗展示）
_last_save_error: str | None = None


def _default_rtsp_urls() -> dict[str, str]:
    return {
        "cam1": "",
        "cam2": "",
        "cam3": "",
        "cam4": "",
        "cam5": "",
        "cam6": "",
        "bird": "",
    }


@dataclass
class ModbusConfig:
    """Modbus 串口配置"""
    use_mock: bool = True
    port: str = "/dev/ttyUSB0"
    baudrate: int = 19200
    parity: str = "N"
    stopbits: int = 1
    timeout: float = 0.2


@dataclass
class PollConfig:
    """轮询间隔配置（毫秒）"""
    FAST_MS: int = 300
    SLOW_MS: int = 1000
    VERY_SLOW_MS: int = 5000


@dataclass
class CameraConfig:
    """摄像头 RTSP 配置"""
    rtsp_urls: dict[str, str] = field(default_factory=_default_rtsp_urls)


@dataclass
class UiConfig:
    """UI 配置"""
    language: str = "zh_CN"
    brightness: int = 80
    theme_mode: str = "light"
    force_resolution: list[int] | None = None  # 开发预览用，如 [800, 480]；未配置则按真实屏幕


@dataclass
class DisplayConfig:
    """显示与触控配置（默认 800×480 适配树莓派显示屏）"""
    width: int = 800
    height: int = 480
    nav_button_min_size: int = 40
    fullscreen: bool = True  # 树莓派桌面默认全屏，无边框
    brightness_percent: int = 60  # 硬件背光亮度 0~100（树莓派 7 寸 DSI）
    default_brightness_percent: int = 60  # 恢复默认亮度时的目标值


@dataclass
class SystemConfig:
    """系统配置"""
    timezone: str = "Asia/Shanghai"


@dataclass
class AlarmThresholdsConfig:
    """告警阈值配置"""
    co_warn: int = 35
    co_crit: int = 100
    lpg_warn_lel_x10: int = 200
    lpg_crit_lel_x10: int = 400


@dataclass
class VideoConfig:
    """视频嵌入配置（树莓派 X11/Wayland 等）"""
    prefer_backend: str = "auto"   # auto | x11 | wayland
    sink: str = "auto"             # auto | ximagesink | glimagesink | waylandsink | autovideosink
    force_no_embed: bool = False   # true 时仅占位，不尝试嵌入


@dataclass
class SecurityConfig:
    """维护 PIN 与会话（默认可运行，后续可做 PIN hash）"""
    maintenance_pin: str = "1234"
    session_timeout_s: int = 900


@dataclass
class AppConfig:
    """应用全局配置"""
    modbus: ModbusConfig = field(default_factory=ModbusConfig)
    poll: PollConfig = field(default_factory=PollConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    system: SystemConfig = field(default_factory=SystemConfig)
    alarm_thresholds: AlarmThresholdsConfig = field(default_factory=AlarmThresholdsConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    dev_mode: bool = False
    theme_path: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "ui" / "theme.qss")


_config: AppConfig | None = None


def _load_yaml(path: Path) -> dict[str, Any] | None:
    """加载 YAML 文件，失败返回 None"""
    try:
        import yaml
    except ImportError:
        logger.warning("未安装 PyYAML，无法读取 config.yaml，使用默认配置")
        return None

    if not path.exists():
        logger.info("config.yaml 不存在 (%s)，使用默认配置", path)
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.warning("读取 config.yaml 失败: %s，使用默认配置", e)
        return None


def _merge(config: AppConfig, data: dict[str, Any]) -> None:
    """将 YAML 数据深度合并到配置对象（缺项用默认，仅覆盖已有项）"""
    if not data:
        return

    if "modbus" in data and isinstance(data["modbus"], dict):
        m = data["modbus"]
        if "use_mock" in m:
            config.modbus.use_mock = bool(m["use_mock"])
        if "port" in m:
            config.modbus.port = str(m["port"])
        if "baudrate" in m:
            config.modbus.baudrate = int(m["baudrate"])
        if "parity" in m:
            config.modbus.parity = str(m["parity"])
        if "stopbits" in m:
            config.modbus.stopbits = int(m["stopbits"])
        if "timeout" in m:
            config.modbus.timeout = float(m["timeout"])

    if "poll" in data and isinstance(data["poll"], dict):
        p = data["poll"]
        if "FAST_MS" in p:
            config.poll.FAST_MS = int(p["FAST_MS"])
        if "SLOW_MS" in p:
            config.poll.SLOW_MS = int(p["SLOW_MS"])
        if "VERY_SLOW_MS" in p:
            config.poll.VERY_SLOW_MS = int(p["VERY_SLOW_MS"])

    if "camera" in data and isinstance(data["camera"], dict) and "rtsp_urls" in data["camera"]:
        urls = data["camera"]["rtsp_urls"]
        if isinstance(urls, dict):
            for k, v in urls.items():
                config.camera.rtsp_urls[str(k)] = str(v) if v else ""

    if "ui" in data and isinstance(data["ui"], dict):
        u = data["ui"]
        if "language" in u:
            config.ui.language = str(u["language"])
        if "brightness" in u:
            config.ui.brightness = int(u["brightness"])
        if "theme_mode" in u:
            config.ui.theme_mode = str(u["theme_mode"])
        if "force_resolution" in u and isinstance(u["force_resolution"], (list, tuple)) and len(u["force_resolution"]) >= 2:
            config.ui.force_resolution = [int(u["force_resolution"][0]), int(u["force_resolution"][1])]

    if "display" in data and isinstance(data["display"], dict):
        d = data["display"]
        if "width" in d:
            config.display.width = int(d["width"])
        if "height" in d:
            config.display.height = int(d["height"])
        if "nav_button_min_size" in d:
            config.display.nav_button_min_size = int(d["nav_button_min_size"])
        if "fullscreen" in d:
            config.display.fullscreen = bool(d["fullscreen"])
        if "brightness_percent" in d:
            config.display.brightness_percent = max(0, min(100, int(d["brightness_percent"])))
        if "default_brightness_percent" in d:
            config.display.default_brightness_percent = max(0, min(100, int(d["default_brightness_percent"])))

    if "system" in data and isinstance(data["system"], dict) and "timezone" in data["system"]:
        config.system.timezone = str(data["system"]["timezone"])

    if "alarm_thresholds" in data and isinstance(data["alarm_thresholds"], dict):
        at = data["alarm_thresholds"]
        if "co_warn" in at:
            config.alarm_thresholds.co_warn = int(at["co_warn"])
        if "co_crit" in at:
            config.alarm_thresholds.co_crit = int(at["co_crit"])
        if "lpg_warn_lel_x10" in at:
            config.alarm_thresholds.lpg_warn_lel_x10 = int(at["lpg_warn_lel_x10"])
        if "lpg_crit_lel_x10" in at:
            config.alarm_thresholds.lpg_crit_lel_x10 = int(at["lpg_crit_lel_x10"])

    if "video" in data and isinstance(data["video"], dict):
        v = data["video"]
        if "prefer_backend" in v:
            config.video.prefer_backend = str(v["prefer_backend"]).strip().lower() or "auto"
        if "sink" in v:
            config.video.sink = str(v["sink"]).strip().lower() or "auto"
        if "force_no_embed" in v:
            config.video.force_no_embed = bool(v["force_no_embed"])

    if "security" in data and isinstance(data["security"], dict):
        s = data["security"]
        if "maintenance_pin" in s:
            config.security.maintenance_pin = str(s["maintenance_pin"]).strip() or "1234"
        if "session_timeout_s" in s:
            config.security.session_timeout_s = max(60, int(s["session_timeout_s"]))

    if "dev_mode" in data:
        config.dev_mode = bool(data["dev_mode"])


def load_config() -> AppConfig:
    """读取 config.yaml 并与默认配置深度合并（缺项用默认，不覆盖已有项）。无 config.yaml 也能运行。"""
    config = AppConfig()
    data = _load_yaml(_CONFIG_PATH)
    _merge(config, data or {})
    return config


def get_config() -> AppConfig:
    """单例获取配置，首次调用时从 config.yaml 加载（不存在则用默认值）"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: AppConfig) -> None:
    """设置当前配置（用于恢复默认等场景）"""
    global _config
    _config = config


def _config_to_dict(cfg: AppConfig) -> dict[str, Any]:
    """将 AppConfig 转为可写回 YAML 的字典（保留结构与可读性）"""
    return {
        "modbus": {
            "use_mock": cfg.modbus.use_mock,
            "port": cfg.modbus.port,
            "baudrate": cfg.modbus.baudrate,
            "parity": cfg.modbus.parity,
            "stopbits": cfg.modbus.stopbits,
            "timeout": cfg.modbus.timeout,
        },
        "poll": {
            "FAST_MS": cfg.poll.FAST_MS,
            "SLOW_MS": cfg.poll.SLOW_MS,
            "VERY_SLOW_MS": cfg.poll.VERY_SLOW_MS,
        },
        "camera": {
            "rtsp_urls": dict(cfg.camera.rtsp_urls),
        },
        "ui": {
            "language": cfg.ui.language,
            "brightness": cfg.ui.brightness,
            "theme_mode": cfg.ui.theme_mode,
            **({"force_resolution": cfg.ui.force_resolution} if cfg.ui.force_resolution else {}),
        },
        "display": {
            "width": cfg.display.width,
            "height": cfg.display.height,
            "nav_button_min_size": cfg.display.nav_button_min_size,
            "fullscreen": cfg.display.fullscreen,
            "brightness_percent": cfg.display.brightness_percent,
            "default_brightness_percent": cfg.display.default_brightness_percent,
        },
        "system": {
            "timezone": cfg.system.timezone,
        },
        "alarm_thresholds": {
            "co_warn": cfg.alarm_thresholds.co_warn,
            "co_crit": cfg.alarm_thresholds.co_crit,
            "lpg_warn_lel_x10": cfg.alarm_thresholds.lpg_warn_lel_x10,
            "lpg_crit_lel_x10": cfg.alarm_thresholds.lpg_crit_lel_x10,
        },
        "video": {
            "prefer_backend": cfg.video.prefer_backend,
            "sink": cfg.video.sink,
            "force_no_embed": cfg.video.force_no_embed,
        },
        "security": {
            "maintenance_pin": cfg.security.maintenance_pin,
            "session_timeout_s": cfg.security.session_timeout_s,
        },
        "dev_mode": cfg.dev_mode,
    }


def get_config_path() -> str:
    """返回 config.yaml 的绝对路径（供保存失败时提示用）。"""
    return str(_CONFIG_PATH.resolve())


def get_last_save_error() -> str | None:
    """返回最近一次 save_config 失败时的错误摘要，成功或无失败记录时为 None。"""
    return _last_save_error


def save_config(config: AppConfig) -> bool:
    """把当前配置写回 config.yaml，保留结构与可读性。失败记录路径与异常并返回 False。"""
    global _last_save_error
    path_str = get_config_path()
    try:
        import yaml
    except ImportError:
        _last_save_error = "未安装 PyYAML，无法保存配置"
        logger.error("未安装 PyYAML，无法保存 config.yaml，路径: %s", path_str)
        return False

    try:
        data = _config_to_dict(config)
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(
                data,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
        _last_save_error = None
        logger.info("配置已保存至 %s", path_str)
        return True
    except Exception as e:
        err_msg = str(e).strip() or type(e).__name__
        _last_save_error = err_msg
        logger.exception("保存 config.yaml 失败，路径: %s，异常: %s", path_str, e)
        return False
