"""
Playwright storageState 导出与登录校验
- 通过 CDP 连接共享浏览器，导出 storage_state
- 使用 storage_state 请求 AUTH_CHECK_URL 校验登录有效性
"""
import json
import httpx
from playwright.async_api import async_playwright

from ..config import BROWSER_CDP_URL, AUTH_CHECK_URL
from ..services.credential import encrypt_storage_state


async def export_and_validate_storage_state() -> tuple[dict | None, str]:
    """
    连接共享浏览器，导出 storage_state，并校验登录有效性。
    返回 (storage_state_dict, message)。
    校验失败时 storage_state_dict 为 None。
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(BROWSER_CDP_URL)
            contexts = browser.contexts
            if not contexts:
                return None, "No browser context found"
            ctx = contexts[0]
            state = await ctx.storage_state()
            await browser.close()

        # 使用 storage_state 请求校验接口
        cookies = state.get("cookies", [])
        cookies_dict = {c["name"]: c["value"] for c in cookies}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                AUTH_CHECK_URL,
                cookies=cookies_dict,
                timeout=10.0,
            )
        if resp.status_code != 200:
            return None, f"Login check failed: {resp.status_code} (must be 200)"

        return state, "OK"
    except Exception as e:
        return None, str(e)


async def save_credential_from_storage(state: dict, db) -> None:
    """加密 storage_state 并入库 app_credential"""
    from ..models import AppCredential
    from datetime import datetime, timezone

    encrypted = encrypt_storage_state(state)
    now = datetime.now(timezone.utc)
    row = AppCredential(
        status="ACTIVE",
        encrypted_state=encrypted,
        last_check=now,
        message="Saved from noVNC session",
        created_at=now,
    )
    db.add(row)
    await db.commit()
