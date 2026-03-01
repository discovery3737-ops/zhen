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
