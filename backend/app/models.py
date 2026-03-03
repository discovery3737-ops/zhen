from sqlalchemy import Column, Integer, String, DateTime, Text
from .database import Base


class AppJobRun(Base):
    __tablename__ = "app_job_run"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    dt = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    status = Column(String(32), nullable=False, default="pending")  # pending/running/success/failed
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    message = Column(Text, nullable=True)


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
