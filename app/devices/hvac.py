"""Slave01: HVAC + 舱温（CABIN_TEMP 来自本从站时）"""

import logging
from typing import Any

from app.devices.spec_utils import build_name_map, get_bool, get_val

logger = logging.getLogger(__name__)

# 设备层合法范围（超出时 clamp 并写 debug 日志）
MODE_MIN, MODE_MAX = 0, 3   # 0=Off, 1=Cool, 2=Vent, 3=Auto
TARGET_TEMP_X10_MIN, TARGET_TEMP_X10_MAX = 160, 300  # 16.0~30.0 °C

# Slave01 HVAC 写入控制器：高层方法，内部走 modbus_master 写队列
_hvac_controller: "HvacWriteController | None" = None


def register_hvac_controller(modbus_master: Any, spec: dict) -> None:
    """注册 HVAC 写入控制器（main 在 ModbusMaster 启动后调用）"""
    global _hvac_controller
    _hvac_controller = HvacWriteController(modbus_master, spec)


def get_hvac_controller() -> "HvacWriteController | None":
    """获取 HVAC 写入控制器，未注册时返回 None"""
    return _hvac_controller


class HvacWriteController:
    """HVAC 写操作高层封装：内部调用 modbus_master.write_coil / write_holding"""

    _SLAVE = 1

    def __init__(self, modbus_master: Any, spec: dict):
        self._mm = modbus_master
        self._name_map = self._build_write_map(spec.get("1", {}))

    def _build_write_map(self, spec_slave: dict) -> dict[str, tuple[str, int]]:
        """name -> (kind, addr0)，kind in ('coil', 'holding')"""
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

    def set_mode(self, mode: int) -> None:
        """MODE: 0=Off, 1=Cool, 2=Vent, 3=Auto；超出范围时钳制到 [0,3] 后写入。"""
        clamped = max(MODE_MIN, min(MODE_MAX, mode))
        if clamped != mode:
            logger.debug("HVAC set_mode clamped %s -> %s", mode, clamped)
        self._holding("MODE", clamped)

    def set_target_temp_x10(self, value: int) -> None:
        """目标温度 ×10 ℃；超出 [160,300]（16~30℃）时钳制后写入。"""
        clamped = max(TARGET_TEMP_X10_MIN, min(TARGET_TEMP_X10_MAX, value))
        if clamped != value:
            logger.debug("HVAC set_target_temp_x10 clamped %s -> %s", value, clamped)
        self._holding("TARGET_TEMP_x10", clamped)

    def set_evap_fan_level(self, level: int) -> None:
        """蒸发风机档位 0~3"""
        self._holding("EVAP_FAN_LEVEL", max(0, min(3, level)))

    def set_cond_fan_level(self, level: int) -> None:
        """冷凝风机档位 0~3"""
        self._holding("COND_FAN_LEVEL", max(0, min(3, level)))

    def set_ac_enable(self, on: bool) -> None:
        """AC 总使能"""
        self._coil("AC_ENABLE", on)

    def set_comp_enable(self, on: bool) -> None:
        """压缩机使能（危险，需长按确认）"""
        self._coil("COMP_ENABLE", on)

    def fault_reset_pulse(self) -> None:
        """故障复位脉冲"""
        self._coil("FAULT_RESET_PULSE", 1)


class Slave01Adapter:
    """
    Slave01 寄存器 -> HvacState / EnvState。
    地址与缩放从 modbus_spec 按 name 解析，不写死；parse(raw) 输出字段与 Snapshot 一致。
    关键：HP_OK/LP_OK/REFRIG_OK、CABIN_TEMP_x10、MODE、TARGET_TEMP_x10、*_PWM_ACT_x10、FAULT_CODE。
    """

    def __init__(self, spec_slave: dict):
        self._name_map = build_name_map(spec_slave)

    def parse(self, raw: dict) -> dict[str, Any]:
        out: dict[str, Any] = {}
        # 关键：HP/LP/冷媒 OK
        hp = get_bool(self._name_map, raw, "HP_OK")
        lp = get_bool(self._name_map, raw, "LP_OK")
        refrig = get_bool(self._name_map, raw, "REFRIG_OK")
        if hp is not None:
            out.setdefault("hvac", {})["hp_ok"] = hp
        if lp is not None:
            out.setdefault("hvac", {})["lp_ok"] = lp
        if refrig is not None:
            out.setdefault("hvac", {})["refrig_ok"] = refrig
        # 舱温（若 Slave01 带 CABIN_TEMP）
        cabin = get_val(self._name_map, raw, "CABIN_TEMP_x10")
        if cabin is not None:
            out.setdefault("env", {})["cabin_temp_x10"] = cabin
        # 模式、目标温度
        mode = get_val(self._name_map, raw, "MODE")
        target_temp = get_val(self._name_map, raw, "TARGET_TEMP_x10")
        evap_level = get_val(self._name_map, raw, "EVAP_FAN_LEVEL", apply_scale=False)
        cond_level = get_val(self._name_map, raw, "COND_FAN_LEVEL", apply_scale=False)
        ac_en = get_bool(self._name_map, raw, "AC_ENABLE")
        comp_en = get_bool(self._name_map, raw, "COMP_ENABLE")
        if mode is not None:
            out.setdefault("hvac", {})["mode"] = mode
        if target_temp is not None:
            out.setdefault("hvac", {})["target_temp_x10"] = target_temp
        if evap_level is not None:
            out.setdefault("hvac", {})["evap_fan_level"] = evap_level
        if cond_level is not None:
            out.setdefault("hvac", {})["cond_fan_level"] = cond_level
        if ac_en is not None:
            out.setdefault("hvac", {})["ac_enable"] = ac_en
        if comp_en is not None:
            out.setdefault("hvac", {})["comp_enable"] = comp_en
        # 实际 PWM
        comp_pwm = get_val(self._name_map, raw, "COMP_PWM_ACT_x10")
        evap_pwm = get_val(self._name_map, raw, "EVAP_FAN_PWM_ACT_x10")
        cond_pwm = get_val(self._name_map, raw, "COND_FAN_PWM_ACT_x10")
        if comp_pwm is not None:
            out.setdefault("hvac", {})["comp_pwm_act_x10"] = comp_pwm
        if evap_pwm is not None:
            out.setdefault("hvac", {})["evap_pwm_act_x10"] = evap_pwm
        if cond_pwm is not None:
            out.setdefault("hvac", {})["cond_pwm_act_x10"] = cond_pwm
        fault = get_val(self._name_map, raw, "FAULT_CODE")
        if fault is not None:
            out.setdefault("hvac", {})["hvac_fault_code"] = fault
        return out
