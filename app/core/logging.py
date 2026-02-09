"""日志配置 - 控制台 + logs/app.log（按大小轮转）"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 项目根目录
_ROOT = Path(__file__).resolve().parent.parent.parent
_LOG_PATH = _ROOT / "logs" / "app.log"

# 格式：时间|级别|线程|模块|消息
_FORMAT = "%(asctime)s|%(levelname)s|%(threadName)s|%(name)s|%(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """配置应用日志：输出到控制台 + logs/app.log（5MB 轮转，保留 5 个）"""
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FMT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        _LOG_PATH,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)
