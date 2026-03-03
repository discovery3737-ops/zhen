"""
Auth API: noVNC 授权闭环
- POST /auth/session/start -> novnc_url
- POST /auth/session/finish -> storageState 导出、校验、加密入库
- GET /auth/credential/status -> 当前凭证状态
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import AppCredential
from ..services.browser_session import (
    start_session as _start_session,
    stop_session,
    verify_session_token,
    clear_session_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class FinishBody(BaseModel):
    session_id: str
    token: str | None = None  # 可选，若传则严格校验


@router.post("/session/start")
async def session_start(db: AsyncSession = Depends(get_db)):
    """创建授权会话，返回 novnc_url"""
    data = await _start_session(db)
    return {"ok": True, "data": data}


@router.post("/session/finish")
async def session_finish(body: FinishBody, db: AsyncSession = Depends(get_db)):
    """
    完成授权：
    a) 校验 session_id 与 token（从 body 或 header）
    b) 导出 storageState（Playwright CDP）
    c) 校验登录有效性（请求 AUTH_CHECK_URL）
    d) 校验通过则加密入库 app_credential(status=ACTIVE)
    e) 校验失败返回 {ok:false, message:'Login not completed'}
    f) 成功后 stop_session
    """
    session_id = body.session_id
    from ..services.browser_session import _session_tokens
    stored_token = _session_tokens.get(session_id)
    if not stored_token:
        raise HTTPException(status_code=400, detail="Session expired or invalid")
    if body.token and body.token != stored_token:
        raise HTTPException(status_code=400, detail="Token mismatch")

    # 导出并校验
    from ..services.storage_export import export_and_validate_storage_state, save_credential_from_storage

    state, msg = await export_and_validate_storage_state()
    if state is None:
        await stop_session(db, session_id)
        return {"ok": False, "message": "Login not completed", "detail": msg}

    await save_credential_from_storage(state, db)
    await stop_session(db, session_id)
    return {"ok": True, "data": {"message": "Credential saved", "status": "ACTIVE"}}


@router.get("/credential/status")
async def credential_status(db: AsyncSession = Depends(get_db)):
    """当前凭证状态"""
    q = (
        select(AppCredential)
        .where(AppCredential.status == "ACTIVE")
        .order_by(AppCredential.created_at.desc())
        .limit(1)
    )
    result = await db.execute(q)
    row = result.scalar_one_or_none()
    if not row:
        return {
            "ok": True,
            "data": {
                "status": "EXPIRED",
                "last_check": None,
                "message": "No active credential",
            },
        }
    return {
        "ok": True,
        "data": {
            "status": row.status,
            "last_check": row.last_check.isoformat() if row.last_check else None,
            "message": row.message,
        },
    }
