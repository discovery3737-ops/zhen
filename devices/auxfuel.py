"""Slave05: 辅助燃油"""

from typing import Any

from app.devices.spec_utils import build_name_map, get_val


class Slave05Adapter:
    """
    Slave05 寄存器 -> AuxFuelState。
    地址与缩放从 spec 按 name 解析，不写死；输出字段与 Snapshot 一致。
    关键：AUX_FUEL_LEVEL_x10。
    """

    def __init__(self, spec_slave: dict):
        self._name_map = build_name_map(spec_slave)

    def parse(self, raw: dict) -> dict[str, Any]:
        out: dict[str, Any] = {}
        level = get_val(self._name_map, raw, "AUX_FUEL_LEVEL_x10")
        if level is not None:
            out.setdefault("auxfuel", {})["aux_fuel_level_x10"] = level
        return out
