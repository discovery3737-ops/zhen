from fastapi import APIRouter
from datetime import datetime, timezone
from ..config import VERSION

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "ok": True,
        "data": {
            "service": "api",
            "version": VERSION,
            "time": datetime.now(timezone.utc).isoformat(),
        },
    }
