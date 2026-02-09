"""
按 spec 从 raw 中按名称取值，并应用 scale。不写死地址，全部从 spec_slave 解析。
"""

from typing import Any

# spec 中 block 键 -> raw 中键
BLOCK_TO_RAW: dict[str, str] = {
    "coils": "coils",
    "discrete_inputs": "di",
    "holding_regs": "hr",
    "input_regs": "ir",
}


def build_name_map(spec_slave: dict) -> dict[str, tuple[str, int, str]]:
    """
    从 spec_slave（单个 slave 的 spec）构建 name -> (raw_key, addr0, scale)。
    raw_key in ("coils", "di", "hr", "ir")。
    """
    name_map: dict[str, tuple[str, int, str]] = {}
    for block_spec, raw_key in BLOCK_TO_RAW.items():
        for point in spec_slave.get(block_spec, []):
            name = (point.get("name") or "").strip()
            if not name:
                continue
            addr0 = int(point.get("addr0", 0))
            scale = (point.get("scale") or "").strip()
            name_map[name] = (raw_key, addr0, scale)
    return name_map


def _apply_scale(raw_val: int, scale: str) -> int | float:
    """
    按 spec.scale 将寄存器原始值转换为状态用值。
    x0.1 / x0.01：寄存器已是 ×10 或 ×100，直接返回整型；
    空：返回原值。
    """
    if not scale:
        return raw_val
    scale = scale.strip().lower()
    if scale == "x0.1":
        return raw_val  # 已是 ×10
    if scale == "x0.01":
        return raw_val  # 已是 ×100
    if scale in ("0.1", "0,1"):
        return int(round(raw_val * 10))  # 物理值×0.1 -> 存 ×10
    if scale in ("0.01", "0,01"):
        return int(round(raw_val * 100))
    return raw_val


def get_raw(raw: dict, raw_key: str, addr0: int) -> int | None:
    """从 raw 中取单个值；不存在返回 None。"""
    block = raw.get(raw_key, {})
    if addr0 not in block:
        return None
    return block[addr0]


def get_val(
    name_map: dict[str, tuple[str, int, str]],
    raw: dict,
    name: str,
    apply_scale: bool = True,
) -> int | None:
    """
    按名称从 raw 取值；若 apply_scale 则按 name_map 中的 scale 转换。
    返回 None 表示无此点位或未读到。
    """
    if name not in name_map:
        return None
    raw_key, addr0, scale = name_map[name]
    v = get_raw(raw, raw_key, addr0)
    if v is None:
        return None
    if apply_scale:
        return int(_apply_scale(v, scale))  # type: ignore[return-value]
    return v


def get_bool(name_map: dict[str, tuple[str, int, str]], raw: dict, name: str) -> bool | None:
    """按名称取布尔（coil/di）；未读到为 None。"""
    v = get_val(name_map, raw, name, apply_scale=False)
    if v is None:
        return None
    return bool(v)
