"""
BrowserSessionManager：管理 noVNC 会话
- 优先：Docker SDK 动态启动短生命周期容器（TODO 待实现）
- 当前：共享 browser-session 服务(6080) 模式，生成 session_id/token
"""
import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import (
    BROWSER_NOVNC_URL,
    BROWSER_CDP_URL,
    SESSION_EXPIRE_MINUTES,
)
from ..models import AppBrowserSession

# 内存中 session -> token 映射（用于 finish 时校验）
_session_tokens: dict[str, str] = {}


def _make_session_id() -> str:
    return f"sess_{secrets.token_hex(16)}"


def _make_token() -> str:
    return secrets.token_urlsafe(32)


async def start_session(db: AsyncSession) -> dict:
    """创建授权会话，返回 session_id, novnc_url, expires_at"""
    session_id = _make_session_id()
    token = _make_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=SESSION_EXPIRE_MINUTES)

    row = AppBrowserSession(
        session_id=session_id,
        token=token,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(row)
    await db.commit()

    _session_tokens[session_id] = token

    # novnc_url 携带 token，便于后端校验
    base = BROWSER_NOVNC_URL.rstrip("/")
    novnc_url = f"{base}/vnc.html?autoconnect=1&token={token}&session={session_id}"

    return {
        "session_id": session_id,
        "token": token,
        "novnc_url": novnc_url,
        "expires_at": expires_at.isoformat(),
    }


def verify_session_token(session_id: str, token: str) -> bool:
    """校验 session_id 与 token 匹配"""
    return _session_tokens.get(session_id) == token


def clear_session_token(session_id: str) -> None:
    """finish 或超时后清除"""
    _session_tokens.pop(session_id, None)


async def stop_session(db: AsyncSession, session_id: str) -> bool:
    """停止会话（逻辑关闭，共享模式下不销毁容器）"""
    clear_session_token(session_id)
    # TODO: 若使用 Docker SDK 独立容器，此处应 stop/rm 容器
    return True


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """定时任务：清理过期 session"""
    now = datetime.now(timezone.utc)
    q = select(AppBrowserSession).where(AppBrowserSession.expires_at < now)
    result = await db.execute(q)
    rows = result.scalars().all()
    for r in rows:
        clear_session_token(r.session_id)
        await db.delete(r)
    await db.commit()
    return len(rows)


def get_cdp_url() -> str:
    """获取 Playwright 连接 CDP 的 URL（共享模式）"""
    return BROWSER_CDP_URL
