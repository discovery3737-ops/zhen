from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON
from .database import Base

DEFAULT_TENANT = "default"


class AppJobRun(Base):
    __tablename__ = "app_job_run"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    dt = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    status = Column(String(32), nullable=False, default="pending")  # pending/running/success/failed
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    message = Column(Text, nullable=True)
<<<<<<< HEAD
=======


class AppCredential(Base):
    """加密入库的 storageState"""
    __tablename__ = "app_credential"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)  # ACTIVE/EXPIRED
    encrypted_state = Column(Text, nullable=False)  # 加密后的 storageState JSON
    last_check = Column(DateTime(timezone=True), nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class AppBrowserSession(Base):
    """noVNC 会话（短期，超时回收）"""
    __tablename__ = "app_browser_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    token = Column(String(128), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


# --- M2 配置表 ---

class GlobalConfig(Base):
    """全局配置（单行）"""
    __tablename__ = "global_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_retention_days = Column(Integer, nullable=False, default=365)
    other_retention_days = Column(Integer, nullable=False, default=730)
    geocode_precision = Column(String(32), nullable=False, default="geohash6")
    amap_key = Column(String(256), nullable=True)
    daily_start_time = Column(String(16), nullable=False, default="00:10")
    admins = Column(JSON, nullable=False, default=lambda: ["admin", "audit", "operate"])


class DatasetDef(Base):
    """数据集定义（预置）"""
    __tablename__ = "dataset_def"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)


class DatasetConfig(Base):
    """租户数据集配置"""
    __tablename__ = "dataset_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, default=DEFAULT_TENANT, index=True)
    dataset_code = Column(String(64), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    filters = Column(JSON, nullable=True)


class ScheduleConfig(Base):
    """调度配置"""
    __tablename__ = "schedule_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, default=DEFAULT_TENANT, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    time = Column(String(16), nullable=False, default="00:10")


class DeliveryConfig(Base):
    """发送配置"""
    __tablename__ = "delivery_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, default=DEFAULT_TENANT, index=True)
    mode = Column(String(32), nullable=False, default="user")  # user/group
    target = Column(String(256), nullable=True)
    notify_admins = Column(Boolean, nullable=False, default=True)
>>>>>>> edfd4a2 (M2: config in DB + web-configurable settings)
