"""告警控制器：连接 AppState 与 AlarmEngine，评估在后台线程执行避免阻塞主线程"""

import logging

from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt

from app.core.state import AppState, Snapshot
from app.core.alarm_engine import AlarmEngine
from app.core.config import get_config

logger = logging.getLogger(__name__)


def _make_get_thresholds():
    """返回从 config.alarm_thresholds 读取的回调，每次 evaluate 动态获取，Settings 保存后无需重启"""
    def _get() -> dict:
        cfg = get_config()
        at = cfg.alarm_thresholds
        return {
            "co_warn": at.co_warn,
            "co_crit": at.co_crit,
            "lpg_warn_lel_x10": at.lpg_warn_lel_x10,
            "lpg_crit_lel_x10": at.lpg_crit_lel_x10,
        }
    return _get


class AlarmEvalWorker(QObject):
    """在独立线程中执行 evaluate(snapshot)，结果通过信号回传主线程"""

    alarms_ready = pyqtSignal(object)  # list[Alarm]

    def __init__(self, engine: AlarmEngine):
        super().__init__()
        self._engine = engine

    def run_eval(self, snapshot: Snapshot) -> None:
        logger.debug("AlarmEvalWorker.run_eval 开始 evaluate")
        alarms = self._engine.evaluate(snapshot)
        logger.debug("AlarmEvalWorker.run_eval 完成 emit alarms_ready len=%s", len(alarms))
        self.alarms_ready.emit(alarms)


class AlarmController(QObject):
    """state.changed 后在后台线程调用 evaluate，结果回主线程后 update(alarms=...)"""

    _eval_requested = pyqtSignal(object)

    def __init__(self, app_state: AppState):
        super().__init__()
        self._app_state = app_state
        self._engine = AlarmEngine(get_thresholds=_make_get_thresholds())
        self._thread = QThread()
        self._worker = AlarmEvalWorker(self._engine)
        self._worker.moveToThread(self._thread)
        self._thread.start()

        # QueuedConnection：不在 AppState.update 的 emit 链里同步执行，避免主线程卡死/长链
        app_state.changed.connect(self._on_state_changed, Qt.ConnectionType.QueuedConnection)
        self._worker.alarms_ready.connect(self._apply_alarms, Qt.ConnectionType.QueuedConnection)
        self._eval_requested.connect(self._worker.run_eval, Qt.ConnectionType.QueuedConnection)

    def _on_state_changed(self, snapshot: Snapshot) -> None:
        """主线程：仅发出评估请求，不阻塞。"""
        logger.debug("AlarmController._on_state_changed 主线程发出 eval 请求")
        self._eval_requested.emit(snapshot)

    def _apply_alarms(self, alarms: list) -> None:
        """主线程：收到评估结果后更新 AppState。"""
        logger.debug("AlarmController._apply_alarms 主线程更新 alarms len=%s", len(alarms) if alarms else 0)
        self._app_state.update(alarms=alarms)
        logger.debug("AlarmController._apply_alarms 完成")

    def ack(self, alarm_id: str) -> None:
        """主线程调用；engine.ack 与 evaluate 在单线程顺序执行，无竞态。"""
        self._engine.ack(alarm_id)
        alarms = self._engine.evaluate(self._app_state.get_snapshot())
        self._app_state.update(alarms=alarms)

    def ack_all_warn(self) -> None:
        """主线程调用；一键 Ack 当前所有 WARN 级别告警（不包含 CRITICAL）。"""
        from app.core.alarm_engine import Severity

        snapshot = self._app_state.get_snapshot()
        alarms = self._engine.evaluate(snapshot)
        for a in alarms:
            if a.severity == Severity.WARN and not a.ack:
                self._engine.ack(a.id)
        alarms = self._engine.evaluate(snapshot)
        self._app_state.update(alarms=alarms)
