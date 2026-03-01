from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from .models import AppJobRun


async def get_runs_list(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> tuple[list[AppJobRun], int]:
    offset = (page - 1) * page_size
    count_q = select(func.count()).select_from(AppJobRun)
    total = (await db.execute(count_q)).scalar() or 0
    q = (
        select(AppJobRun)
        .order_by(AppJobRun.started_at.desc().nullslast(), AppJobRun.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(q)
    rows = result.scalars().all()
    return list(rows), total


async def get_run_by_id(db: AsyncSession, run_id: str) -> AppJobRun | None:
    q = select(AppJobRun).where(AppJobRun.run_id == run_id)
    result = await db.execute(q)
    return result.scalar_one_or_none()
