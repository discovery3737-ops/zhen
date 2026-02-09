"""
设备解析层：按 spec 名称解析 Modbus raw -> Snapshot 子域。
每个 Slave 对应一个 Adapter 类，parse(raw) 返回可传给 app_state.update(**ret) 的字典。
"""

from typing import Any

from app.devices.hvac import Slave01Adapter
from app.devices.webasto import Slave02Adapter
from app.devices.lighting import Slave03Adapter
from app.devices.power_gateway import Slave04Adapter
from app.devices.auxfuel import Slave05Adapter
from app.devices.cabin_th import Slave06Adapter
from app.devices.gas import Slave07Adapter
from app.devices.pdu import Slave08Adapter
from app.devices.outdoor_th import Slave09Adapter

_ADAPTER_CLS: dict[str, type] = {
    "1": Slave01Adapter,
    "2": Slave02Adapter,
    "3": Slave03Adapter,
    "4": Slave04Adapter,
    "5": Slave05Adapter,
    "6": Slave06Adapter,
    "7": Slave07Adapter,
    "8": Slave08Adapter,
    "9": Slave09Adapter,
}

# 缓存每个 slave 的 adapter 实例（由 spec 构建，不写死地址）
_adapter_cache: dict[str, Any] = {}


def get_adapter(slave_id: str, spec: dict) -> Any | None:
    """按 slave_id 和 spec 返回对应 Adapter 实例；无 spec 或未知 slave 返回 None。"""
    if slave_id in _adapter_cache:
        return _adapter_cache[slave_id]
    spec_slave = spec.get(slave_id)
    if not spec_slave or slave_id not in _ADAPTER_CLS:
        return None
    cls = _ADAPTER_CLS[slave_id]
    _adapter_cache[slave_id] = cls(spec_slave)
    return _adapter_cache[slave_id]


def apply_device_parsers(slave_id: str, raw: dict, spec: dict) -> dict[str, Any]:
    """
    对单个 slave 的 raw 调用对应 Adapter.parse(raw)，返回可传给 app_state.update(**ret) 的字典。
    地址与缩放均从 spec 按 name 解析，不写死。
    """
    adapter = get_adapter(slave_id, spec)
    if adapter is None:
        return {}
    return adapter.parse(raw)


__all__ = [
    "apply_device_parsers",
    "get_adapter",
    "Slave01Adapter",
    "Slave02Adapter",
    "Slave03Adapter",
    "Slave04Adapter",
    "Slave05Adapter",
    "Slave06Adapter",
    "Slave07Adapter",
    "Slave08Adapter",
    "Slave09Adapter",
]
