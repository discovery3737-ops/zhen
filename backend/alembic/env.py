import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import Base and models for autogenerate
from app.database import Base
from app.models import (  # noqa: F401
    AppJobRun, AppCredential, AppBrowserSession,
    GlobalConfig, DatasetDef, DatasetConfig, ScheduleConfig, DeliveryConfig,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./crawler.db")
if db_url.startswith("postgresql"):
    db_url = db_url.replace("postgresql+asyncpg", "postgresql")
elif db_url.startswith("sqlite+aiosqlite"):
    db_url = db_url.replace("sqlite+aiosqlite", "sqlite")
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    if "sqlite" in db_url:
        connectable = context.config.attributes.get("connection")
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    if "sqlite" in db_url:
        from sqlalchemy import create_engine
        sync_url = db_url
        connectable = create_engine(sync_url)
        with connectable.connect() as connection:
            do_run_migrations(connection)
    else:
        import sqlalchemy
        sync_url = db_url.replace("+asyncpg", "")
        connectable = sqlalchemy.create_engine(sync_url)
        with connectable.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
