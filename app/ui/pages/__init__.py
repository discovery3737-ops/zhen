"""页面模块"""

from app.ui.pages.base import PageBase
from app.ui.pages.dashboard import DashboardPage
from app.ui.pages.hvac import HvacPage
from app.ui.pages.lighting import LightingPage
from app.ui.pages.power import PowerPage
from app.ui.pages.exterior import ExteriorPage
from app.ui.pages.camera import CameraPage
from app.ui.pages.environment import EnvironmentPage
from app.ui.pages.diagnostics import DiagnosticsPage
from app.ui.pages.settings import SettingsPage
from app.ui.pages.more import MorePage

__all__ = [
    "PageBase",
    "DashboardPage",
    "HvacPage",
    "LightingPage",
    "PowerPage",
    "ExteriorPage",
    "CameraPage",
    "EnvironmentPage",
    "DiagnosticsPage",
    "SettingsPage",
    "MorePage",
]
