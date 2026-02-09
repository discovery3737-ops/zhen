"""Slave07: 燃气（CO/LPG）"""

from typing import Any

from app.devices.spec_utils import build_name_map, get_bool, get_val


class Slave07Adapter:
    """
    Slave07 寄存器 -> GasState。
    地址与缩放从 spec 按 name 解析，不写死；输出字段与 Snapshot 一致。
    关键：CO_PPM、LPG_LEL_x10、WARMUP_ACTIVE、ALARM_ACTIVE、FAULT_ACTIVE。
    """

    def __init__(self, spec_slave: dict):
        self._name_map = build_name_map(spec_slave)

    def parse(self, raw: dict) -> dict[str, Any]:
        out: dict[str, Any] = {}
        co_ppm = get_val(self._name_map, raw, "CO_PPM")
        if co_ppm is not None:
            out.setdefault("gas", {})["co_ppm"] = co_ppm
        lpg = get_val(self._name_map, raw, "LPG_LEL_x10")
        if lpg is not None:
            out.setdefault("gas", {})["lpg_lel_x10"] = lpg
        warmup = get_bool(self._name_map, raw, "WARMUP_ACTIVE")
        if warmup is not None:
            out.setdefault("gas", {})["warmup"] = warmup
        alarm = get_bool(self._name_map, raw, "ALARM_ACTIVE")
        if alarm is not None:
            out.setdefault("gas", {})["gas_alarm"] = alarm
        fault = get_bool(self._name_map, raw, "FAULT_ACTIVE")
        if fault is not None:
            out.setdefault("gas", {})["gas_fault"] = fault
        return out
