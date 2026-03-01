import os

# 版本号
VERSION = os.getenv("API_VERSION", "0.1.0")

# 数据库（未设置时用 SQLite 便于本地无 Docker 运行）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./crawler.db"
)

# 报表存储路径
REPORTS_DIR = os.getenv("REPORTS_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports"))
