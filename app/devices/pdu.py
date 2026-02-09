"""Slave08: PDU"""

from typing import Any

from app.devices.spec_utils import build_name_map, get_bool, get_val

_pdu_controller: "PduWriteController | None" = None


def register_pdu_controller(modbus_master: Any, spec: dict) -> None:
    """注册 PDU 写入控制器"""
    global _pdu_controller
    _pdu_controller = PduWriteController(modbus_master, spec)


def get_pdu_controller() -> "PduWriteController | None":
    return _pdu_controller


class PduWriteController:
    """PDU 写操作高层封装"""

    _SLAVE = 8

    def __init__(self, modbus_master: Any, spec: dict):
        self._mm = modbus_master
        self._name_map = self._build_write_map(spec.get("8", {}))

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

    def set_inv_ac_out_on(self, on: bool) -> None:
        """220V 输出接触器合闸/分闸"""
        self._coil("INV_AC_OUT_ON", on)

    def set_fridge_24v_on(self, on: bool) -> None:
        """冰箱 24V 供电"""
        self._coil("FRIDGE_24V_ON", on)

    def leg_extend(self) -> None:
        """支腿伸出（脉冲）"""
        self._coil("LEG_EXTEND", 1)

    def leg_retract(self) -> None:
        """支腿收回（脉冲）"""
        self._coil("LEG_RETRACT", 1)

    def leg_stop(self) -> None:
        """支腿停止（脉冲）"""
        self._coil("LEG_STOP", 1)

    def awning_extend(self) -> None:
        """遮阳棚伸出（脉冲）"""
        self._coil("AWNING_EXTEND", 1)

    def awning_retract(self) -> None:
        """遮阳棚收回（脉冲）"""
        self._coil("AWNING_RETRACT", 1)

    def awning_stop(self) -> None:
        """遮阳棚停止（脉冲）"""
        self._coil("AWNING_STOP", 1)

    def set_ext_light_on(self, on: bool) -> None:
        """外部照明"""
        self._coil("EXT_LIGHT_ON", on)


class Slave08Adapter:
    """
    Slave08 寄存器 -> PduState。
    地址从 spec 按 name 解析，不写死；输出字段与 Snapshot 一致。
    关键：E_STOP、接触器反馈 INV_AC_OUT_FB、FAULT_ACTIVE -> pdu_fault_code。
    """

    def __init__(self, spec_slave: dict):
        self._name_map = build_name_map(spec_slave)

    def parse(self, raw: dict) -> dict[str, Any]:
        out: dict[str, Any] = {}
        e_stop = get_bool(self._name_map, raw, "E_STOP")
        if e_stop is not None:
            out.setdefault("pdu", {})["e_stop"] = e_stop
        inv_fb = get_bool(self._name_map, raw, "INV_AC_OUT_FB")
        if inv_fb is not None:
            out.setdefault("pdu", {})["inv_ac_out_fb"] = inv_fb
        inv_on = get_bool(self._name_map, raw, "INV_AC_OUT_ON")
        if inv_on is not None:
            out.setdefault("pdu", {})["inv_ac_out_on"] = inv_on
        fridge = get_bool(self._name_map, raw, "FRIDGE_24V_ON")
        if fridge is not None:
            out.setdefault("pdu", {})["fridge_24v_on"] = fridge
        ext_light = get_bool(self._name_map, raw, "EXT_LIGHT_ON")
        if ext_light is not None:
            out.setdefault("pdu", {})["ext_light_on"] = ext_light
        fault_code = get_val(self._name_map, raw, "FAULT_CODE", apply_scale=False)
        if fault_code is not None:
            out.setdefault("pdu", {})["pdu_fault_code"] = fault_code
        elif (fault := get_bool(self._name_map, raw, "FAULT_ACTIVE")) is not None:
            out.setdefault("pdu", {})["pdu_fault_code"] = 1 if fault else 0
        leg_up = get_bool(self._name_map, raw, "LEG_UP_LIMIT")
        leg_down = get_bool(self._name_map, raw, "LEG_DOWN_LIMIT")
        if leg_up is not None and leg_down is not None:
            out.setdefault("pdu", {})["leg_limits"] = (1 if leg_up else 0, 1 if leg_down else 0)
        awning_in = get_bool(self._name_map, raw, "AWNING_IN_LIMIT")
        awning_out = get_bool(self._name_map, raw, "AWNING_OUT_LIMIT")
        if awning_in is not None and awning_out is not None:
            out.setdefault("pdu", {})["awning_limits"] = (1 if awning_in else 0, 1 if awning_out else 0)
        state = get_val(self._name_map, raw, "STATE", apply_scale=False)
        if state is not None:
            out.setdefault("pdu", {})["pdu_state"] = state
        leg_i = get_val(self._name_map, raw, "LEG_MOTOR_I_x100")
        if leg_i is not None:
            out.setdefault("pdu", {})["leg_motor_i_x100"] = leg_i
        awning_i = get_val(self._name_map, raw, "AWNING_MOTOR_I_x100")
        if awning_i is not None:
            out.setdefault("pdu", {})["awning_motor_i_x100"] = awning_i
        return out
