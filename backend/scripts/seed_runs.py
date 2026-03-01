"""插入示例 run 记录供联调使用"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone
from app.database import engine, AsyncSessionLocal, Base
from app.models import AppJobRun


async def seed():
    # 确保表已创建
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        r = await session.execute(select(AppJobRun).limit(1))
        if r.scalar_one_or_none():
            print("已有数据，跳过 seed")
            return
        now = datetime.now(timezone.utc)
        runs = [
            AppJobRun(
                run_id="run-001",
                dt="2025-02-28",
                status="success",
                started_at=now,
                finished_at=now,
                message="Daily job completed",
            ),
            AppJobRun(
                run_id="run-002",
                dt="2025-02-27",
                status="success",
                started_at=now,
                finished_at=now,
                message="OK",
            ),
        ]
        for r in runs:
            session.add(r)
        await session.commit()
        print("Seed 完成")


if __name__ == "__main__":
    asyncio.run(seed())
