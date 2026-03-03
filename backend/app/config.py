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

# noVNC 授权
BROWSER_NOVNC_URL = os.getenv("BROWSER_NOVNC_URL", "http://localhost:6080")
BROWSER_CDP_URL = os.getenv("BROWSER_CDP_URL", "http://localhost:9222")
AUTH_CHECK_URL = os.getenv("AUTH_CHECK_URL", "https://httpbin.org/cookies")
CREDENTIAL_ENCRYPT_KEY = os.getenv("CREDENTIAL_ENCRYPT_KEY", "dev-key-32-bytes-base64encoded!")[:32]
SESSION_EXPIRE_MINUTES = int(os.getenv("SESSION_EXPIRE_MINUTES", "15"))
