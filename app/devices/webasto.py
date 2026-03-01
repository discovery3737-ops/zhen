"""Slave02: Webasto 燃油加热器"""

from typing import Any

from app.devices.spec_utils import build_name_map, get_bool, get_val

_webasto_controller: "WebastoWriteController | None" = None


def register_webasto_controller(modbus_master: Any, spec: dict) -> None:
    """注册 Webasto 写入控制器"""
    global _webasto_controller
    _webasto_controller = WebastoWriteController(modbus_master, spec)


def get_webasto_controller() -> "WebastoWriteController | None":
    return _webasto_controller


class WebastoWriteController:
    """Webasto 写操作高层封装"""

    _SLAVE = 2

    def __init__(self, modbus_master: Any, spec: dict):
        self._mm = modbus_master
        self._name_map = self._build_write_map(spec.get("2", {}))

    def _build_write_map(self, spec_slave: dict) -> dict[str, tuple[str, int]]:
        out: dict[str, tuple[str, int]] = {}
        for block, kind in [("coils", "coil"), ("holding_regs", "holding")]:
            for p in spec_slave.get(block, []):
                rw = (p.get("rw") or "").upper()
                if "W" in rw:
                    name = (p.get("name") or "").strip()
                    if name:
                        out[name] = (kind, int(p.get("addr0", 0)))
        return out

    def _coil(self, name: str, value: bool | int) -> None:
        t = self._name_map.get(name)
        if t:
            kind, addr = t
            if kind == "coil":
                self._mm.write_coil(self._SLAVE, addr, value)

    def _holding(self, name: str, value: int) -> None:
        t = self._name_map.get(name)
        if t:
            kind, addr = t
            if kind == "holding":
                self._mm.write_holding(self._SLAVE, addr, value)

    def set_heater_on(self, on: bool) -> None:
        self._coil("HEATER_ON", on)

    def set_target_water_temp_x10(self, value: int) -> None:
        """目标水温 ×10 ℃"""
        self._holding("TARGET_WATER_TEMP_x10", value)

    def set_hydronic_pump_on(self, on: bool) -> None:
        self._coil("HYDRONIC_PUMP_ON", on)

    def fault_reset_pulse(self) -> None:
        self._coil("FAULT_RESET_PULSE", 1)


class Slave02Adapter:
    """
    Slave02 寄存器 -> WebastoState。
    地址与缩放从 spec 按 name 解析，不写死；输出字段与 Snapshot 一致。
    关键：HEATER_ON、WATER_TEMP_x10、HEATER_STATE、FAULT_CODE、TC3_ACTIVE。
    """

    def __init__(self, spec_slave: dict):
        self._name_map = build_name_map(spec_slave)

    def parse(self, raw: dict) -> dict[str, Any]:
        out: dict[str, Any] = {}
        heater_on = get_bool(self._name_map, raw, "HEATER_ON")
        if heater_on is not None:
            out.setdefault("webasto", {})["heater_on"] = heater_on
        water_temp = get_val(self._name_map, raw, "WATER_TEMP_x10")
        if water_temp is not None:
            out.setdefault("webasto", {})["water_temp_x10"] = water_temp
        heater_state = get_val(self._name_map, raw, "HEATER_STATE")
        if heater_state is not None:
            out.setdefault("webasto", {})["heater_state"] = heater_state
        fault = get_val(self._name_map, raw, "FAULT_CODE")
        if fault is not None:
            out.setdefault("webasto", {})["web_fault_code"] = fault
        tc3 = get_bool(self._name_map, raw, "TC3_ACTIVE")
        if tc3 is not None:
            out.setdefault("webasto", {})["tc3_active"] = tc3
        target_wt = get_val(self._name_map, raw, "TARGET_WATER_TEMP_x10")
        if target_wt is not None:
            out.setdefault("webasto", {})["target_water_temp_x10"] = target_wt
        pump_on = get_bool(self._name_map, raw, "HYDRONIC_PUMP_ON")
        if pump_on is not None:
            out.setdefault("webasto", {})["hydronic_pump_on"] = pump_on
        return out
