from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..services import get_runs_list, get_run_by_id
from ..schemas import RunResponse, RunsListResponse

router = APIRouter(prefix="/runs", tags=["runs"])


def _run_to_dict(r):
    return RunResponse(
        run_id=r.run_id,
        dt=r.dt,
        status=r.status,
        started_at=r.started_at,
        finished_at=r.finished_at,
        message=r.message,
    )


@router.get("")
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await get_runs_list(db, page=page, page_size=page_size)
    return {
        "ok": True,
        "data": {
            "items": [_run_to_dict(r).model_dump(mode="json") for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await get_run_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "ok": True,
        "data": _run_to_dict(run).model_dump(mode="json"),
    }
