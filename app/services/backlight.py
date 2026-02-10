"""
树莓派官方 7 寸 DSI 背光亮度控制：/sys/class/backlight/rpi_backlight。
通过 sudo -n 脚本或直接写 sysfs 设置 brightness；提供 apply_percent_from_config 供启动/进入设置页应用保存值（防抖/只执行一次）。
"""

import logging
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SCRIPT_PATH = "/usr/local/bin/rpi_set_backlight"

# 启动/进入设置页时 apply 防抖：上次应用过的 percent，避免重复写
_last_applied_percent: int | None = None
_last_apply_time: float = 0.0
_APPLY_DEBOUNCE_S = 2.0


class BacklightError(Exception):
    """背光设置失败，供 UI 提示用。message 可直接展示给用户。"""
    pass


class BacklightService:
    """Raspberry Pi rpi_backlight 亮度读写。"""

    def __init__(self, backlight_path: str = "/sys/class/backlight/rpi_backlight"):
        self._path = Path(backlight_path)
        self._brightness_file = self._path / "brightness"
        self._max_brightness_file = self._path / "max_brightness"

    def is_available(self) -> bool:
        """检查 brightness 与 max_brightness 是否存在。"""
        return self._brightness_file.exists() and self._max_brightness_file.exists()

    def get_max_raw(self) -> int:
        """读取 max_brightness 原始值。不可用时返回 0。"""
        return self.get_max()

    def get_max(self) -> int:
        """读取 max_brightness。不可用时返回 0。"""
        if not self.is_available():
            return 0
        try:
            return int(self._max_brightness_file.read_text().strip())
        except (OSError, ValueError):
            return 0

    def get_raw(self) -> int:
        """读取当前 brightness 原始值。"""
        if not self.is_available():
            return 0
        try:
            return int(self._brightness_file.read_text().strip())
        except (OSError, ValueError):
            return 0

    def set_raw(self, raw: int) -> None:
        """写入 brightness 原始值。失败抛出 BacklightError。"""
        if not self.is_available():
            raise BacklightError("当前屏幕不支持硬件亮度控制")
        mx = self.get_max()
        raw = max(1, min(mx, int(raw)))

        script = Path(SCRIPT_PATH)
        if script.exists():
            try:
                subprocess.run(
                    ["sudo", "-n", SCRIPT_PATH, str(raw)],
                    check=True,
                    capture_output=True,
                    timeout=5,
                )
                return
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.warning("rpi_set_backlight 执行失败，尝试直接写 sysfs: %s", e)
        try:
            self._brightness_file.write_text(str(raw))
            return
        except OSError as e:
            logger.warning("直接写 sysfs 失败: %s", e)
            raise BacklightError(
                "无法设置亮度（需要 root 或 sudoers 放行）。"
                "请创建 /usr/local/bin/rpi_set_backlight 并配置 /etc/sudoers.d/rv-hmi-backlight 放行无密码执行。"
            ) from e

    def get_percent(self) -> int:
        """返回 0~100 的当前亮度百分比。"""
        mx = self.get_max()
        if mx <= 0:
            return 0
        raw = self.get_raw()
        return max(0, min(100, round(100 * raw / mx)))

    def set_percent(
        self,
        pct: int,
        min_pct: int = 5,
        immediate: bool = True,
    ) -> None:
        """
        设置亮度百分比。pct 限制在 0..100，实际不低于 min_pct（默认 5）避免全黑。
        immediate 仅保留接口兼容，始终立即写入。
        """
        pct = max(0, min(100, int(pct)))
        effective = max(min_pct, pct) if min_pct is not None and min_pct > 0 else pct
        mx = self.get_max()
        if mx <= 0:
            raise BacklightError("当前屏幕不支持硬件亮度控制")
        raw = max(1, min(mx, round(effective * mx / 100)))
        self.set_raw(raw)

    def apply_percent_from_config(self, cfg) -> None:
        """
        从 config 应用保存的亮度（启动/进入设置页时调用）。防抖：短时间内不重复写入同一值。
        """
        global _last_applied_percent, _last_apply_time
        if not self.is_available():
            return
        pct = getattr(getattr(cfg, "display", None), "brightness_percent", 60)
        pct = max(5, min(100, int(pct)))
        now = time.time()
        if _last_applied_percent == pct and (now - _last_apply_time) < _APPLY_DEBOUNCE_S:
            return
        try:
            self.set_percent(pct, min_pct=5)
            _last_applied_percent = pct
            _last_apply_time = now
        except BacklightError:
            pass
