"""Slave09: 舱外温湿度"""

from typing import Any

from app.devices.spec_utils import build_name_map, get_val


class Slave09Adapter:
    """
    Slave09 寄存器 -> EnvState（舱外温湿度）。
    地址与缩放从 spec 按 name 解析，不写死；输出字段与 Snapshot 一致。
    关键：OUT_TEMP_x10、OUT_RH_x10。
    """

    def __init__(self, spec_slave: dict):
        self._name_map = build_name_map(spec_slave)

    def parse(self, raw: dict) -> dict[str, Any]:
        out: dict[str, Any] = {}
        out_temp = get_val(self._name_map, raw, "OUT_TEMP_x10")
        out_rh = get_val(self._name_map, raw, "OUT_RH_x10")
        if out_temp is not None:
            out.setdefault("env", {})["out_temp_x10"] = out_temp
        if out_rh is not None:
            out.setdefault("env", {})["out_rh_x10"] = out_rh
        return out
