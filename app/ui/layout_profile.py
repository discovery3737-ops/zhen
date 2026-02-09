"""布局 Profile：根据主屏分辨率选择 WVGA(800×480) / WXGA(1280×800)，提供 LayoutTokens 供 UI 使用。
   WVGA 适当压缩 tab_bar_h/status_bar_h/pad_page/gap 以兼顾 480 可视高度与触控（按钮>=44）。"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication


def detect_profile(screen_w: int, screen_h: int) -> str:
    """根据分辨率返回 "WVGA" 或 "WXGA"。WVGA = 800×480 及以下，其余为 WXGA。"""
    if screen_w <= 800 and screen_h <= 480:
        return "WVGA"
    return "WXGA"


@dataclass
class LayoutTokens:
    """布局/字体/间距等 token，由 profile 决定数值。"""

    profile: str
    font_base: int      # 默认正文 px
    font_title: int     # 页面标题 px
    font_big: int       # 卡片大数字 px
    font_small: int     # 小字/单位/备注 px
    pad_page: int       # 页面 padding px
    pad_card: int       # 卡片内 padding px
    gap: int            # 卡片间距 / 通用 gap px
    btn_h: int          # 普通按钮最小高度 px
    btn_h_key: int      # 关键按钮最小高度 px
    icon_btn_h: int     # IconButton 最小高度/宽 px
    status_bar_h: int   # 状态栏高度 px
    tab_bar_h: int      # 底部 TabBar 高度 px
    scroll_handle_min: int  # 滚动条 handle 最小高度 px


# WVGA: 800×480 可视高度紧张，适当下调以不牺牲触控（btn_h>=44, btn_h_key>=52）为前提
_WVGA = LayoutTokens(
    profile="WVGA",
    font_base=14,
    font_title=18,
    font_big=28,
    font_small=12,
    pad_page=8,
    pad_card=8,
    gap=6,
    btn_h=44,
    btn_h_key=52,
    icon_btn_h=56,
    status_bar_h=36,
    tab_bar_h=60,
    scroll_handle_min=28,
)

# WXGA: 更舒展
_WXGA = LayoutTokens(
    profile="WXGA",
    font_base=18,
    font_title=22,
    font_big=44,
    font_small=14,
    pad_page=24,
    pad_card=16,
    gap=12,
    btn_h=52,
    btn_h_key=60,
    icon_btn_h=72,
    status_bar_h=36,
    tab_bar_h=60,
    scroll_handle_min=40,
)


def get_tokens(app: "QApplication | None" = None) -> LayoutTokens:
    """根据主屏分辨率获取 LayoutTokens。app 可为 None，内部用 QApplication.instance()。"""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QGuiApplication

    qapp = app if app is not None else QApplication.instance()
    if qapp is None:
        return _WVGA
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return _WVGA
    size = screen.size()
    w, h = size.width(), size.height()
    profile = detect_profile(w, h)
    return _WXGA if profile == "WXGA" else _WVGA
