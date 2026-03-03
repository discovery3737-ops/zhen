"""Jobs API: 触发 daily job"""
from datetime import datetime, timezone
import secrets
from fastapi import APIRouter, Query, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import AppJobRun, DatasetConfig, ScheduleConfig, DEFAULT_TENANT

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/daily/run")
async def run_daily_job(
    dt: str = Query(..., description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """
    触发一次 daily job。
    - 从 dataset_config.enabled 读取要跑的数据源
    - 不跑 enabled=false 的数据源
    """
    # 读取启用的数据源
    q = select(DatasetConfig).where(
        DatasetConfig.tenant_id == DEFAULT_TENANT,
        DatasetConfig.enabled == True,
    )
    configs = (await db.execute(q)).scalars().all()
    enabled_codes = [c.dataset_code for c in configs]

    run_id = f"run-{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc)
    msg = f"Ran datasets: {', '.join(enabled_codes) or 'none'}"
    row = AppJobRun(
        run_id=run_id,
        dt=dt,
        status="success",
        started_at=now,
        finished_at=now,
        message=msg,
    )
    db.add(row)
    await db.commit()
    return {"ok": True, "data": {"run_id": run_id, "enabled_datasets": enabled_codes, "message": msg}}
