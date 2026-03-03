"""M2 add config tables

Revision ID: m2_config
Revises:
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "m2_config"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "global_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("track_retention_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("other_retention_days", sa.Integer(), nullable=False, server_default="730"),
        sa.Column("geocode_precision", sa.String(32), nullable=False, server_default="geohash6"),
        sa.Column("amap_key", sa.String(256), nullable=True),
        sa.Column("daily_start_time", sa.String(16), nullable=False, server_default="00:10"),
        sa.Column("admins", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "dataset_def",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "dataset_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("dataset_code", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "schedule_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("time", sa.String(16), nullable=False, server_default="00:10"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "delivery_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("mode", sa.String(32), nullable=False, server_default="user"),
        sa.Column("target", sa.String(256), nullable=True),
        sa.Column("notify_admins", sa.Boolean(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dataset_def_code", "dataset_def", ["code"])
    op.create_index("ix_dataset_config_tenant_id", "dataset_config", ["tenant_id"])
    op.create_index("ix_dataset_config_dataset_code", "dataset_config", ["dataset_code"])
    op.create_index("ix_schedule_config_tenant_id", "schedule_config", ["tenant_id"])
    op.create_index("ix_delivery_config_tenant_id", "delivery_config", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("delivery_config")
    op.drop_table("schedule_config")
    op.drop_table("dataset_config")
    op.drop_table("dataset_def")
    op.drop_table("global_config")
