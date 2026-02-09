"""车载 HMI 入口 - 可直接运行: python -m app.main"""

import os
import sys
import logging
import threading

# 树莓派/X11 触控：必须在 QApplication 前设置，启用 XInput2 以支持触摸屏
if sys.platform == "linux" and "QT_XCB_NO_XI2" not in os.environ:
    os.environ["QT_XCB_NO_XI2"] = "0"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal

from app.core.logging import setup_logging
from app.core.config import get_config
from app.core.state import AppState
from app.core.alarm_controller import AlarmController
from app.ui.main_window import MainWindow
from app.services.modbus_master import ModbusMaster, MockTransport, load_spec, create_transport_from_config
from app.services.video_manager import get_video_manager
from app.devices import apply_device_parsers
from app.devices.hvac import register_hvac_controller
from app.devices.webasto import register_webasto_controller
from app.devices.pdu import register_pdu_controller
from app.devices.lighting import register_lighting_controller

# 开启 DEBUG 便于排查主界面卡死：日志输出到控制台与 logs/app.log
setup_logging(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# GStreamer 调试：设置 GST_DEBUG 输出到 stderr（2=LOG, 3=DEBUG, 4=TRACE）
if "GST_DEBUG" not in os.environ:
    os.environ["GST_DEBUG"] = "2"


class StateUpdateBridge(QObject):
    """供 ModbusMaster 工作线程发出状态更新，由主线程执行 app_state.update，避免持锁卡死主界面。"""
    state_updates_ready = pyqtSignal(object)  # dict，即 update(**d) 的 kwargs

    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        self._app_state = app_state
        self._log = logging.getLogger(__name__)

    def _on_updates_ready(self, d):
        self._log.debug("StateUpdateBridge: 主线程执行 update(%s)", list(d.keys()))
        self._app_state.update(**d)
        self._log.debug("StateUpdateBridge: update 完成")


def _log_config_summary() -> None:
    """打印配置摘要（不含敏感信息：RTSP URL 等）"""
    cfg = get_config()
    urls = cfg.camera.rtsp_urls or {}
    configured = sum(1 for v in urls.values() if v and str(v).strip())
    logger.info(
        "配置摘要: modbus.port=%s baudrate=%d | poll FAST=%dms SLOW=%dms VERY_SLOW=%dms | "
        "camera 共 %d 路（已配置 %d）| ui.language=%s | display %dx%d",
        cfg.modbus.port,
        cfg.modbus.baudrate,
        cfg.poll.FAST_MS,
        cfg.poll.SLOW_MS,
        cfg.poll.VERY_SLOW_MS,
        len(urls),
        configured,
        cfg.ui.language,
        cfg.display.width,
        cfg.display.height,
    )


def _seed_mock_transport(transport: MockTransport) -> None:
    """为 Mock 预填数据，使首轮轮询后 UI 有显示；并可在后续用 inject_failure 模拟掉线。"""
    # Slave01 HVAC: 高压/低压/制冷 OK，舱温 23.5℃
    transport.set_discrete_input(1, 0, 1)   # HP_OK
    transport.set_discrete_input(1, 1, 1)   # LP_OK
    transport.set_discrete_input(1, 2, 1)   # REFRIG_OK
    transport.set_input_register(1, 0, 235) # CABIN_TEMP_x10
    transport.set_coil(1, 0, 0)             # AC_ENABLE off
    transport.set_coil(1, 1, 0)             # COMP_ENABLE off
    transport.set_holding_register(1, 0, 0) # MODE Off
    transport.set_holding_register(1, 1, 240)  # TARGET_TEMP 24.0°C
    transport.set_holding_register(1, 2, 0) # EVAP_FAN_LEVEL 0
    transport.set_holding_register(1, 3, 0) # COND_FAN_LEVEL 0
    transport.set_input_register(1, 3, 0)  # COMP_PWM_ACT_x10
    transport.set_input_register(1, 4, 0)
    transport.set_input_register(1, 5, 0)
    # Slave04 Power: SOC 85%、电池、逆变器
    transport.set_input_register(4, 0, 5200)   # BATT_V_x100 52.0V
    transport.set_input_register(4, 1, 500)    # BATT_I_x100 5.0A
    transport.set_input_register(4, 2, 260)    # BATT_P_W
    transport.set_input_register(4, 3, 850)    # SOC_x10 85%
    transport.set_input_register(4, 5, 2200)   # INV_AC_V_x10 220V
    transport.set_input_register(4, 7, 0)      # INV_AC_P_W
    transport.set_input_register(4, 8, 1)      # INV_STATE 1=On
    transport.set_discrete_input(4, 1, 0)      # INVERTER_FAULT
    # Slave06 Env: 舱温、湿度
    transport.set_input_register(6, 0, 235)
    transport.set_input_register(6, 1, 500)
    # Slave07 Gas: CO 正常，非 warmup
    transport.set_input_register(7, 0, 20)  # CO_PPM
    transport.set_discrete_input(7, 1, 0)  # WARMUP_ACTIVE
    # Slave03 灯光: 全部关、灯带亮度 500
    transport.set_coil(3, 0, 0)  # LIGHT_MAIN_CEILING
    transport.set_coil(3, 1, 0)  # LIGHT_SIDE_STRIP_ON
    transport.set_coil(3, 2, 0)  # LIGHT_NIGHT
    transport.set_coil(3, 3, 0)  # LIGHT_READING
    transport.set_holding_register(3, 0, 500)  # STRIP_BRIGHTNESS_0_1000
    # Slave02 Webasto: 加热器关、水循环泵关、目标水温 60°C
    transport.set_coil(2, 0, 0)  # HEATER_ON
    transport.set_coil(2, 1, 0)  # HYDRONIC_PUMP_ON
    transport.set_holding_register(2, 0, 600)  # TARGET_WATER_TEMP_x10 60.0°C
    # Slave08 PDU: 无急停、220V 分闸、冰箱关、外部照明关
    transport.set_coil(8, 6, 0)              # EXT_LIGHT_ON
    transport.set_coil(8, 7, 0)              # FRIDGE_24V_ON
    transport.set_coil(8, 8, 0)              # INV_AC_OUT_ON
    transport.set_discrete_input(8, 0, 1)    # LEG_UP_LIMIT 已收回
    transport.set_discrete_input(8, 1, 0)    # LEG_DOWN_LIMIT
    transport.set_discrete_input(8, 2, 1)    # AWNING_IN_LIMIT 已收回
    transport.set_discrete_input(8, 3, 0)    # AWNING_OUT_LIMIT
    transport.set_discrete_input(8, 4, 0)    # E_STOP
    transport.set_discrete_input(8, 7, 0)    # INV_AC_OUT_FB
    transport.set_input_register(8, 0, 0)    # LEG_MOTOR_I_x100
    transport.set_input_register(8, 1, 0)    # AWNING_MOTOR_I_x100
    transport.set_input_register(8, 3, 0)    # FAULT_CODE
    transport.set_input_register(8, 4, 0)    # STATE Idle
    logger.debug("MockTransport 已预填 Slave01/04/06/07/08 初始值")
    # 可选：若干秒后注入故障以演示告警
    # transport.inject_failure(1)  # 或设置 E_STOP=1 / HP_OK=0


def main() -> int:
    get_config()
    _log_config_summary()

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("车载 HMI")
    app.setApplicationDisplayName("车载 HMI")

    app_state = AppState()
    alarm_controller = AlarmController(app_state)
    # 在 show() 前预加载 spec，避免在事件循环或 QTimer 回调里读大 JSON 导致主界面卡死
    preloaded_spec = load_spec()
    if preloaded_spec is None:
        preloaded_spec = {}

    video_manager = get_video_manager()
    win = MainWindow(app_state, alarm_controller, video_manager)
    cfg = get_config()
    if getattr(cfg.ui, "force_resolution", None) and len(cfg.ui.force_resolution) >= 2:
        win.setFixedSize(cfg.ui.force_resolution[0], cfg.ui.force_resolution[1])
        win.show()
    elif cfg.display.fullscreen:
        win.showFullScreen()
    else:
        win.show()

    bridge = StateUpdateBridge(app_state)
    bridge.state_updates_ready.connect(bridge._on_updates_ready)

    def start_modbus():
        """主线程仅负责启动后台线程，不在此做 transport/ModbusMaster 创建，避免卡死。"""
        def run_in_thread():
            try:
                logger.debug("Modbus 初始化线程: 开始")
                cfg = get_config()
                transport = create_transport_from_config(cfg)
                if cfg.modbus.use_mock:
                    _seed_mock_transport(transport)
                modbus_master = ModbusMaster(
                    transport=transport,
                    app_state=app_state,
                    poll_ms={
                        "FAST_MS": cfg.poll.FAST_MS,
                        "SLOW_MS": cfg.poll.SLOW_MS,
                        "VERY_SLOW_MS": cfg.poll.VERY_SLOW_MS,
                    },
                    device_parser=apply_device_parsers,
                    update_bridge=bridge,
                    spec=preloaded_spec,
                )
                modbus_master.start()
                from app.services.modbus_master import register_modbus_master
                register_modbus_master(modbus_master)
                register_hvac_controller(modbus_master, preloaded_spec)
                register_webasto_controller(modbus_master, preloaded_spec)
                register_pdu_controller(modbus_master, preloaded_spec)
                register_lighting_controller(modbus_master, preloaded_spec)
                logger.debug("Modbus 初始化线程: ModbusMaster 已启动")
            except Exception as e:
                logger.exception("Modbus 初始化线程 异常: %s", e)

        threading.Thread(target=run_in_thread, daemon=True).start()

    # 延迟 100ms 再启动，给窗口首帧绘制留时间
    QTimer.singleShot(100, start_modbus)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
