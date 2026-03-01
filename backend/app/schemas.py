from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class HealthResponse(BaseModel):
    service: str
    version: str
    time: str


class RunResponse(BaseModel):
    run_id: str
    dt: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: Optional[str] = None


class RunsListResponse(BaseModel):
    items: list[RunResponse]
    total: int
    page: int
    page_size: int
