"""M2 配置表 seed：预置 dataset_def、global_config、默认 schedule/delivery"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, Base
from app.models import (
    GlobalConfig, DatasetDef, DatasetConfig, ScheduleConfig, DeliveryConfig,
    DEFAULT_TENANT,
)


DATASET_DEFS = [
    ("risk", "风险数据", "风险相关数据集"),
    ("checkpost", "检查点数据", "检查点采集"),
    ("qualification", "资质数据", "资质信息"),
    ("position_snapshot", "岗位快照", "岗位快照数据"),
    ("track", "轨迹数据", "轨迹采集"),
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        r = (await db.execute(select(DatasetDef).limit(1))).scalar_one_or_none()
        if r:
            print("已有数据，跳过 seed")
            return

        for code, name, desc in DATASET_DEFS:
            db.add(DatasetDef(code=code, name=name, description=desc))

        r = (await db.execute(select(GlobalConfig).limit(1))).scalar_one_or_none()
        if not r:
            db.add(GlobalConfig(
                track_retention_days=365,
                other_retention_days=730,
                geocode_precision="geohash6",
                daily_start_time="00:10",
                admins=["admin", "audit", "operate"],
            ))

        for code, _, _ in DATASET_DEFS:
            db.add(DatasetConfig(tenant_id=DEFAULT_TENANT, dataset_code=code, enabled=True))

        r = (await db.execute(select(ScheduleConfig).where(ScheduleConfig.tenant_id == DEFAULT_TENANT).limit(1))).scalar_one_or_none()
        if not r:
            db.add(ScheduleConfig(tenant_id=DEFAULT_TENANT, enabled=True, time="00:10"))

        r = (await db.execute(select(DeliveryConfig).where(DeliveryConfig.tenant_id == DEFAULT_TENANT).limit(1))).scalar_one_or_none()
        if not r:
            db.add(DeliveryConfig(tenant_id=DEFAULT_TENANT, mode="user", notify_admins=True))

        await db.commit()
        print("M2 config seed 完成")


if __name__ == "__main__":
    asyncio.run(seed())
