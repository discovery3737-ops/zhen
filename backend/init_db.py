"""初始化数据库脚本，创建 app_job_run 表（若使用同步方式初始化可选）"""
import asyncio
from app.database import engine
from app.models import Base


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_db())
