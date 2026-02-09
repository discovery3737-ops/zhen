"""Slave04: 动力/电池/逆变网关"""

from typing import Any

from app.devices.spec_utils import build_name_map, get_bool, get_val


class Slave04Adapter:
    """
    Slave04 寄存器 -> PowerState。
    地址与缩放从 spec 按 name 解析，不写死；输出字段与 Snapshot 一致。
    关键：SOC_x10、BATT_V_x100/BATT_I_x100/BATT_P_W、INV_STATE、INVERTER_FAULT、INV_AC_V_x10/INV_AC_P_W。
    """

    def __init__(self, spec_slave: dict):
        self._name_map = build_name_map(spec_slave)

    def parse(self, raw: dict) -> dict[str, Any]:
        out: dict[str, Any] = {}
        soc = get_val(self._name_map, raw, "SOC_x10")
        if soc is not None:
            out.setdefault("power", {})["soc_x10"] = soc
        batt_v = get_val(self._name_map, raw, "BATT_V_x100")
        batt_i = get_val(self._name_map, raw, "BATT_I_x100")
        batt_p = get_val(self._name_map, raw, "BATT_P_W")
        if batt_v is not None:
            out.setdefault("power", {})["batt_v_x100"] = batt_v
        if batt_i is not None:
            out.setdefault("power", {})["batt_i_x100"] = batt_i
        if batt_p is not None:
            out.setdefault("power", {})["batt_p_w"] = batt_p
        inv_state = get_val(self._name_map, raw, "INV_STATE")
        inv_fault = get_bool(self._name_map, raw, "INVERTER_FAULT")
        inv_ac_v = get_val(self._name_map, raw, "INV_AC_V_x10")
        inv_ac_p = get_val(self._name_map, raw, "INV_AC_P_W")
        if inv_state is not None:
            out.setdefault("power", {})["inv_state"] = inv_state
        if inv_fault is not None:
            out.setdefault("power", {})["inv_fault"] = inv_fault
        if inv_ac_v is not None:
            out.setdefault("power", {})["inv_ac_v_x10"] = inv_ac_v
        if inv_ac_p is not None:
            out.setdefault("power", {})["inv_ac_p_w"] = inv_ac_p
        return out
