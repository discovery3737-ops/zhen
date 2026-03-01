"""Slave06: 舱内温湿度"""

from typing import Any

from app.devices.spec_utils import build_name_map, get_val


class Slave06Adapter:
    """
    Slave06 寄存器 -> EnvState（舱内温湿度）。
    地址与缩放从 spec 按 name 解析，不写死；输出字段与 Snapshot 一致。
    关键：CABIN_TEMP_x10、CABIN_RH_x10。
    """

    def __init__(self, spec_slave: dict):
        self._name_map = build_name_map(spec_slave)

    def parse(self, raw: dict) -> dict[str, Any]:
        out: dict[str, Any] = {}
        cabin_temp = get_val(self._name_map, raw, "CABIN_TEMP_x10")
        cabin_rh = get_val(self._name_map, raw, "CABIN_RH_x10")
        if cabin_temp is not None:
            out.setdefault("env", {})["cabin_temp_x10"] = cabin_temp
        if cabin_rh is not None:
            out.setdefault("env", {})["cabin_rh_x10"] = cabin_rh
        return out
