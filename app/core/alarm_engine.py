"""告警引擎 - v1.0 AlarmRules 实现

CO/LPG 阈值来源：config.alarm_thresholds（co_warn, co_crit, lpg_warn_lel_x10, lpg_crit_lel_x10）
通过 get_thresholds 回调每次 evaluate 时动态读取，Settings 保存后无需重启即可生效。
debounce/回差规则保持 v1.0（10s/3s debounce，固定回差）。
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from app.core.state import Snapshot

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


@dataclass
class Alarm:
    """告警项"""
    id: str
    severity: Severity
    title: str
    message: str
    source_slave: int | None = None
    active: bool = True
    ack: bool = False
    first_seen_ts: float = 0.0
    last_seen_ts: float = 0.0


# --- 阈值默认值（当 get_thresholds 未提供或返回不全时使用）---
_DEFAULT_CO_WARN = 35
_DEFAULT_CO_CRIT = 100
_DEFAULT_LPG_WARN_LEL_X10 = 200  # 20%
_DEFAULT_LPG_CRIT_LEL_X10 = 400  # 40%
# 回差 v1.0：CO 10/30 ppm，LPG 5%/10%
_CO_HYSTERESIS_WARN = 10
_CO_HYSTERESIS_CRIT = 30
_LPG_HYSTERESIS_WARN_X10 = 50   # 5%
_LPG_HYSTERESIS_CRIT_X10 = 100  # 10%
ENV_OFFLINE_CONSECUTIVE = 3


def _default_get_thresholds() -> dict[str, int]:
    """无回调时的默认阈值"""
    return {
        "co_warn": _DEFAULT_CO_WARN,
        "co_crit": _DEFAULT_CO_CRIT,
        "lpg_warn_lel_x10": _DEFAULT_LPG_WARN_LEL_X10,
        "lpg_crit_lel_x10": _DEFAULT_LPG_CRIT_LEL_X10,
    }


class AlarmEngine:
    """告警引擎：根据 Snapshot 计算告警列表。CO/LPG 阈值从 get_thresholds 动态读取。"""

    def __init__(
        self,
        get_thresholds: Callable[[], dict[str, int]] | Any | None = None,
    ):
        """
        Args:
            get_thresholds: 回调 () -> {co_warn, co_crit, lpg_warn_lel_x10, lpg_crit_lel_x10}，
                或 Config 对象（取其 alarm_thresholds）。
                每次 evaluate 时调用，确保 Settings 保存后无需重启即可生效。
        """
        self._get_thresholds = self._resolve_get_thresholds(get_thresholds)
        self._active: dict[str, Alarm] = {}
        self._ack_ids: set[str] = set()
        # debounce: {rule_id: first_true_ts}
        self._debounce: dict[str, float] = {}
        # 回差：当前已触发的告警，需低于 clear 阈值才消
        self._triggered: set[str] = set()
        # 连续失败计数：{rule_id: count}
        self._consecutive_fail: dict[str, int] = {}
        self._last_eval_ts = 0.0

    def _resolve_get_thresholds(self, arg: Callable[[], dict[str, int]] | Any | None) -> Callable[[], dict[str, int]]:
        """将 Config 或回调转为统一的 get_thresholds 可调用"""
        if arg is None:
            return _default_get_thresholds
        if callable(arg):
            return arg
        # Config 对象：取 alarm_thresholds
        if hasattr(arg, "alarm_thresholds"):
            def _from_config() -> dict[str, int]:
                at = arg.alarm_thresholds
                return {
                    "co_warn": getattr(at, "co_warn", _DEFAULT_CO_WARN),
                    "co_crit": getattr(at, "co_crit", _DEFAULT_CO_CRIT),
                    "lpg_warn_lel_x10": getattr(at, "lpg_warn_lel_x10", _DEFAULT_LPG_WARN_LEL_X10),
                    "lpg_crit_lel_x10": getattr(at, "lpg_crit_lel_x10", _DEFAULT_LPG_CRIT_LEL_X10),
                }
            return _from_config
        return _default_get_thresholds

    def _get_gas_thresholds(self) -> tuple[int, int, int, int, int, int, int, int]:
        """从 config.alarm_thresholds 读取 CO/LPG 阈值及回差 clear 值。"""
        t = self._get_thresholds()
        co_warn = int(t.get("co_warn", _DEFAULT_CO_WARN))
        co_crit = int(t.get("co_crit", _DEFAULT_CO_CRIT))
        lpg_warn_x10 = int(t.get("lpg_warn_lel_x10", _DEFAULT_LPG_WARN_LEL_X10))
        lpg_crit_x10 = int(t.get("lpg_crit_lel_x10", _DEFAULT_LPG_CRIT_LEL_X10))
        co_warn_clear = max(0, co_warn - _CO_HYSTERESIS_WARN)
        co_crit_clear = max(0, co_crit - _CO_HYSTERESIS_CRIT)
        lpg_warn_clear_x10 = max(0, lpg_warn_x10 - _LPG_HYSTERESIS_WARN_X10)
        lpg_crit_clear_x10 = max(0, lpg_crit_x10 - _LPG_HYSTERESIS_CRIT_X10)
        return co_warn, co_warn_clear, co_crit, co_crit_clear, lpg_warn_x10, lpg_warn_clear_x10, lpg_crit_x10, lpg_crit_clear_x10

    def ack(self, alarm_id: str) -> None:
        """确认告警"""
        self._ack_ids.add(alarm_id)
        if alarm_id in self._active:
            a = self._active[alarm_id]
            self._active[alarm_id] = Alarm(
                id=a.id,
                severity=a.severity,
                title=a.title,
                message=a.message,
                source_slave=a.source_slave,
                active=a.active,
                ack=True,
                first_seen_ts=a.first_seen_ts,
                last_seen_ts=a.last_seen_ts,
            )

    def evaluate(self, snapshot: Snapshot) -> list[Alarm]:
        """根据快照计算告警列表。CO/LPG 阈值每次从 get_thresholds 读取，Settings 保存后无需重启生效。"""
        now = time.time()
        self._last_eval_ts = now
        results: list[Alarm] = []

        self._eval_hvac(snapshot, now, results)
        self._eval_webasto(snapshot, now, results)
        self._eval_gas(snapshot, now, results)
        self._eval_pdu(snapshot, now, results)
        self._eval_env(snapshot, now, results)

        self._active = {a.id: a for a in results}
        return results

    def _eval_hvac(self, snap: Snapshot, now: float, out: list[Alarm]) -> None:
        h = snap.hvac
        if h.hp_ok is False:
            out.append(self._make_alarm("HVAC_HP_TRIP", Severity.CRITICAL, "空调高压保护", "高压开关动作", now, now))
        if h.lp_ok is False:
            out.append(self._make_alarm("HVAC_LP_TRIP", Severity.CRITICAL, "空调低压保护", "低压开关动作", now, now))
        if h.refrig_ok is False:
            out.append(self._make_alarm("HVAC_REFRIG_SW", Severity.CRITICAL, "空调制冷开关", "制冷开关异常", now, now))

    def _eval_gas(self, snap: Snapshot, now: float, out: list[Alarm]) -> None:
        # 阈值来源：config.alarm_thresholds，每次 evaluate 动态读取，Settings 保存后无需重启
        (
            co_warn, co_warn_clear, co_crit, co_crit_clear,
            lpg_warn_x10, lpg_warn_clear_x10, lpg_crit_x10, lpg_crit_clear_x10,
        ) = self._get_gas_thresholds()

        g = snap.gas
        if g.warmup:
            return
        co = g.co_ppm if g.co_ppm is not None else 0
        lpg_x10 = g.lpg_lel_x10 if g.lpg_lel_x10 is not None else 0

        # GAS_CO_WARN: 10s debounce, 回差 co_warn/co_warn_clear
        if co >= co_warn:
            if "GAS_CO_WARN" not in self._debounce:
                self._debounce["GAS_CO_WARN"] = now
            if now - self._debounce["GAS_CO_WARN"] >= 10.0:
                self._triggered.add("GAS_CO_WARN")
        if co < co_warn_clear:
            self._debounce.pop("GAS_CO_WARN", None)
            self._triggered.discard("GAS_CO_WARN")
        if "GAS_CO_WARN" in self._triggered:
            out.append(self._make_alarm("GAS_CO_WARN", Severity.WARN, "CO 预警", f"CO {co} ppm", now, now))

        # GAS_CO_CRIT: 3s debounce, 回差 co_crit/co_crit_clear
        if co >= co_crit:
            if "GAS_CO_CRIT" not in self._debounce:
                self._debounce["GAS_CO_CRIT"] = now
            if now - self._debounce["GAS_CO_CRIT"] >= 3.0:
                self._triggered.add("GAS_CO_CRIT")
        if co < co_crit_clear:
            self._debounce.pop("GAS_CO_CRIT", None)
            self._triggered.discard("GAS_CO_CRIT")
        if "GAS_CO_CRIT" in self._triggered:
            out.append(self._make_alarm("GAS_CO_CRIT", Severity.CRITICAL, "CO 严重", f"CO {co} ppm", now, now))

        # GAS_LPG_WARN: 10s debounce, 回差 lpg_warn_lel_x10 / lpg_warn_clear_lel_x10
        if lpg_x10 >= lpg_warn_x10:
            if "GAS_LPG_WARN" not in self._debounce:
                self._debounce["GAS_LPG_WARN"] = now
            if now - self._debounce["GAS_LPG_WARN"] >= 10.0:
                self._triggered.add("GAS_LPG_WARN")
        if lpg_x10 < lpg_warn_clear_x10:
            self._debounce.pop("GAS_LPG_WARN", None)
            self._triggered.discard("GAS_LPG_WARN")
        if "GAS_LPG_WARN" in self._triggered:
            out.append(self._make_alarm("GAS_LPG_WARN", Severity.WARN, "LPG 预警", f"LPG {lpg_x10/10:.1f}% LEL", now, now))

        # GAS_LPG_CRIT: 3s debounce, 回差 lpg_crit_lel_x10 / lpg_crit_clear_lel_x10
        if lpg_x10 >= lpg_crit_x10:
            if "GAS_LPG_CRIT" not in self._debounce:
                self._debounce["GAS_LPG_CRIT"] = now
            if now - self._debounce["GAS_LPG_CRIT"] >= 3.0:
                self._triggered.add("GAS_LPG_CRIT")
        if lpg_x10 < lpg_crit_clear_x10:
            self._debounce.pop("GAS_LPG_CRIT", None)
            self._triggered.discard("GAS_LPG_CRIT")
        if "GAS_LPG_CRIT" in self._triggered:
            out.append(self._make_alarm("GAS_LPG_CRIT", Severity.CRITICAL, "LPG 严重", f"LPG {lpg_x10/10:.1f}% LEL", now, now))

    def _eval_webasto(self, snap: Snapshot, now: float, out: list[Alarm]) -> None:
        w = snap.webasto
        if w.web_fault_code is not None and w.web_fault_code != 0:
            out.append(self._make_alarm(
                "WEBASTO_FAULT",
                Severity.WARN,
                "Webasto 故障",
                f"故障码: {w.web_fault_code}",
                now, now,
                slave=2,
            ))

    def _eval_pdu(self, snap: Snapshot, now: float, out: list[Alarm]) -> None:
        p = snap.pdu
        if p.e_stop is True:
            out.append(self._make_alarm("PDU_ESTOP", Severity.CRITICAL, "急停", "PDU 急停按下", now, now))

        if p.inv_ac_out_on is not None and p.inv_ac_out_fb is not None and p.inv_ac_out_on != p.inv_ac_out_fb:
            if "PDU_AC_CONTACTOR_MISMATCH" not in self._debounce:
                self._debounce["PDU_AC_CONTACTOR_MISMATCH"] = now
            if now - self._debounce["PDU_AC_CONTACTOR_MISMATCH"] >= 2.0:
                out.append(self._make_alarm(
                    "PDU_AC_CONTACTOR_MISMATCH",
                    Severity.CRITICAL,
                    "交流接触器不一致",
                    "逆变器 AC 输出与反馈不符",
                    now, now,
                ))
        else:
            self._debounce.pop("PDU_AC_CONTACTOR_MISMATCH", None)

    def _eval_env(self, snap: Snapshot, now: float, out: list[Alarm]) -> None:
        e = snap.env
        cabin_off = e.cabin_temp_x10 is None
        if cabin_off:
            self._consecutive_fail["ENV_CABIN_TH_OFFLINE"] = self._consecutive_fail.get("ENV_CABIN_TH_OFFLINE", 0) + 1
        else:
            self._consecutive_fail["ENV_CABIN_TH_OFFLINE"] = 0
        if self._consecutive_fail.get("ENV_CABIN_TH_OFFLINE", 0) >= ENV_OFFLINE_CONSECUTIVE:
            out.append(self._make_alarm("ENV_CABIN_TH_OFFLINE", Severity.WARN, "舱内温湿度离线", "舱内传感器无数据", now, now))

        out_off = e.out_temp_x10 is None
        if out_off:
            self._consecutive_fail["ENV_OUT_TH_OFFLINE"] = self._consecutive_fail.get("ENV_OUT_TH_OFFLINE", 0) + 1
        else:
            self._consecutive_fail["ENV_OUT_TH_OFFLINE"] = 0
        if self._consecutive_fail.get("ENV_OUT_TH_OFFLINE", 0) >= ENV_OFFLINE_CONSECUTIVE:
            out.append(self._make_alarm("ENV_OUT_TH_OFFLINE", Severity.WARN, "舱外温湿度离线", "舱外传感器无数据", now, now))

    def _make_alarm(
        self,
        aid: str,
        sev: Severity,
        title: str,
        message: str,
        first: float,
        last: float,
        slave: int | None = None,
    ) -> Alarm:
        return Alarm(
            id=aid,
            severity=sev,
            title=title,
            message=message,
            source_slave=slave,
            active=True,
            ack=aid in self._ack_ids,
            first_seen_ts=first,
            last_seen_ts=last,
        )
