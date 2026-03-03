"""M2 配置 CRUD API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import (
    GlobalConfig, DatasetDef, DatasetConfig, ScheduleConfig, DeliveryConfig,
    DEFAULT_TENANT,
)

router = APIRouter(tags=["config"])

TENANT = DEFAULT_TENANT


# --- Schemas ---

class GlobalConfigBody(BaseModel):
    track_retention_days: int | None = None
    other_retention_days: int | None = None
    geocode_precision: str | None = None
    amap_key: str | None = None
    daily_start_time: str | None = None
    admins: list[str] | None = None


class DatasetConfigItem(BaseModel):
    dataset_code: str
    enabled: bool
    filters: dict | None = None


class DatasetsConfigBody(BaseModel):
    items: list[DatasetConfigItem]


class ScheduleBody(BaseModel):
    enabled: bool | None = None
    time: str | None = None


class DeliveryBody(BaseModel):
    mode: str | None = None
    target: str | None = None
    notify_admins: bool | None = None


# --- GET/PUT /config/global ---

@router.get("/config/global")
async def get_global_config(db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(GlobalConfig).limit(1))).scalar_one_or_none()
    if not r:
        return {"ok": True, "data": {
            "track_retention_days": 365,
            "other_retention_days": 730,
            "geocode_precision": "geohash6",
            "amap_key": None,
            "daily_start_time": "00:10",
            "admins": ["admin", "audit", "operate"],
        }}
    return {"ok": True, "data": {
        "track_retention_days": r.track_retention_days,
        "other_retention_days": r.other_retention_days,
        "geocode_precision": r.geocode_precision,
        "amap_key": r.amap_key,
        "daily_start_time": r.daily_start_time,
        "admins": r.admins or ["admin", "audit", "operate"],
    }}


@router.put("/config/global")
async def put_global_config(body: GlobalConfigBody, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(GlobalConfig).limit(1))).scalar_one_or_none()
    if not r:
        r = GlobalConfig()
        db.add(r)
        await db.flush()
    if body.track_retention_days is not None:
        r.track_retention_days = body.track_retention_days
    if body.other_retention_days is not None:
        r.other_retention_days = body.other_retention_days
    if body.geocode_precision is not None:
        r.geocode_precision = body.geocode_precision
    if body.amap_key is not None:
        r.amap_key = body.amap_key
    if body.daily_start_time is not None:
        r.daily_start_time = body.daily_start_time
    if body.admins is not None:
        r.admins = body.admins
    await db.commit()
    return {"ok": True, "data": {"message": "saved"}}


# --- GET/PUT /datasets/config ---

@router.get("/datasets/config")
async def get_datasets_config(db: AsyncSession = Depends(get_db)):
    defs_q = select(DatasetDef).order_by(DatasetDef.code)
    defs = (await db.execute(defs_q)).scalars().all()
    config_q = select(DatasetConfig).where(DatasetConfig.tenant_id == TENANT)
    configs = {c.dataset_code: c for c in (await db.execute(config_q)).scalars().all()}
    items = []
    for d in defs:
        c = configs.get(d.code)
        items.append({
            "dataset_code": d.code,
            "name": d.name,
            "enabled": c.enabled if c else True,
            "filters": c.filters if c else None,
        })
    return {"ok": True, "data": {"items": items}}


@router.put("/datasets/config")
async def put_datasets_config(body: DatasetsConfigBody, db: AsyncSession = Depends(get_db)):
    for item in body.items:
        c = (await db.execute(
            select(DatasetConfig).where(
                DatasetConfig.tenant_id == TENANT,
                DatasetConfig.dataset_code == item.dataset_code,
            )
        )).scalar_one_or_none()
        if not c:
            c = DatasetConfig(tenant_id=TENANT, dataset_code=item.dataset_code)
            db.add(c)
        c.enabled = item.enabled
        c.filters = item.filters
    await db.commit()
    return {"ok": True, "data": {"message": "saved"}}


# --- GET/PUT /schedule/daily ---

@router.get("/schedule/daily")
async def get_schedule_daily(db: AsyncSession = Depends(get_db)):
    r = (await db.execute(
        select(ScheduleConfig).where(ScheduleConfig.tenant_id == TENANT).limit(1)
    )).scalar_one_or_none()
    if not r:
        return {"ok": True, "data": {"enabled": True, "time": "00:10"}}
    return {"ok": True, "data": {"enabled": r.enabled, "time": r.time}}


@router.put("/schedule/daily")
async def put_schedule_daily(body: ScheduleBody, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(
        select(ScheduleConfig).where(ScheduleConfig.tenant_id == TENANT).limit(1)
    )).scalar_one_or_none()
    if not r:
        r = ScheduleConfig(tenant_id=TENANT)
        db.add(r)
    if body.enabled is not None:
        r.enabled = body.enabled
    if body.time is not None:
        r.time = body.time
    await db.commit()
    return {"ok": True, "data": {"message": "saved"}}


# --- GET/PUT /delivery ---

@router.get("/delivery")
async def get_delivery(db: AsyncSession = Depends(get_db)):
    r = (await db.execute(
        select(DeliveryConfig).where(DeliveryConfig.tenant_id == TENANT).limit(1)
    )).scalar_one_or_none()
    if not r:
        return {"ok": True, "data": {"mode": "user", "target": None, "notify_admins": True}}
    return {"ok": True, "data": {"mode": r.mode, "target": r.target, "notify_admins": r.notify_admins}}


@router.put("/delivery")
async def put_delivery(body: DeliveryBody, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(
        select(DeliveryConfig).where(DeliveryConfig.tenant_id == TENANT).limit(1)
    )).scalar_one_or_none()
    if not r:
        r = DeliveryConfig(tenant_id=TENANT)
        db.add(r)
    if body.mode is not None:
        r.mode = body.mode
    if body.target is not None:
        r.target = body.target
    if body.notify_admins is not None:
        r.notify_admins = body.notify_admins
    await db.commit()
    return {"ok": True, "data": {"message": "saved"}}
