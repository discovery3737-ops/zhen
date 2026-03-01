"""Slave03: 灯光"""

from typing import Any

from app.devices.spec_utils import build_name_map, get_bool, get_val

_lighting_controller: "LightingWriteController | None" = None


def register_lighting_controller(modbus_master: Any, spec: dict) -> None:
    """注册灯光写入控制器"""
    global _lighting_controller
    _lighting_controller = LightingWriteController(modbus_master, spec)


def get_lighting_controller() -> "LightingWriteController | None":
    return _lighting_controller


class LightingWriteController:
    """灯光写操作高层封装"""

    _SLAVE = 3

    def __init__(self, modbus_master: Any, spec: dict):
        self._mm = modbus_master
        self._name_map = self._build_write_map(spec.get("3", {}))

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

    def set_main(self, on: bool) -> None:
        self._coil("LIGHT_MAIN_CEILING", on)

    def set_night(self, on: bool) -> None:
        self._coil("LIGHT_NIGHT", on)

    def set_reading(self, on: bool) -> None:
        self._coil("LIGHT_READING", on)

    def set_strip_on(self, on: bool) -> None:
        self._coil("LIGHT_SIDE_STRIP_ON", on)

    def set_strip_brightness(self, value: int) -> None:
        """灯带亮度 0~1000"""
        self._holding("STRIP_BRIGHTNESS_0_1000", max(0, min(1000, value)))

    def scene_sleep_pulse(self) -> None:
        self._coil("SCENE_SLEEP_PULSE", 1)

    def scene_reading_pulse(self) -> None:
        self._coil("SCENE_READING_PULSE", 1)


class Slave03Adapter:
    """
    Slave03 寄存器 -> LightingState。
    地址从 spec 按 name 解析，不写死；输出字段与 Snapshot 一致。
    """

    def __init__(self, spec_slave: dict):
        self._name_map = build_name_map(spec_slave)

    def parse(self, raw: dict) -> dict[str, Any]:
        out: dict[str, Any] = {}
        main = get_bool(self._name_map, raw, "LIGHT_MAIN_CEILING")
        strip = get_bool(self._name_map, raw, "LIGHT_SIDE_STRIP_ON")
        night = get_bool(self._name_map, raw, "LIGHT_NIGHT")
        reading = get_bool(self._name_map, raw, "LIGHT_READING")
        brightness = get_val(self._name_map, raw, "STRIP_BRIGHTNESS_0_1000")
        if main is not None:
            out.setdefault("lighting", {})["main"] = main
        if strip is not None:
            out.setdefault("lighting", {})["strip"] = strip
        if night is not None:
            out.setdefault("lighting", {})["night"] = night
        if reading is not None:
            out.setdefault("lighting", {})["reading"] = reading
        if brightness is not None:
            out.setdefault("lighting", {})["strip_brightness"] = brightness
        return out
