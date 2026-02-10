"""
URL 脱敏与 RTSP 校验：日志不输出明文凭证，仅允许合法 rtsp/rtsps。
"""

from urllib.parse import urlparse, urlunparse


# 禁止出现在 URL 中的字符（防注入/换行等）
_FORBIDDEN_CHARS = ('"', "'", "\n", "\r", "\t")


def mask_url(url: str, keep_path: bool = True) -> str:
    """脱敏 URL 中的 user:pass@，保留协议与 host（可选 path）。"""
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc
        if "@" in netloc:
            _, hostport = netloc.split("@", 1)
            netloc = "***@" + hostport
        path = parsed.path if keep_path else ""
        # 重建：(scheme, netloc, path, params, query, fragment)
        return urlunparse((parsed.scheme, netloc, path or "", "", "", ""))
    except Exception:
        return "***"


def validate_rtsp_url(url: str) -> tuple[bool, str]:
    """
    校验 RTSP URL：仅允许 rtsp/rtsps，禁止 \" ' \\n \\r \\t，必须有 host。
    返回 (是否合法, 错误信息；合法时为空字符串)。
    """
    if not url or not isinstance(url, str):
        return False, "缺少 URL"
    if not url.strip():
        return False, "缺少 URL"
    for ch in _FORBIDDEN_CHARS:
        if ch in url:
            return False, "URL 中不允许包含 \" ' \\n \\r \\t"
    try:
        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("rtsp", "rtsps"):
            return False, "仅允许 rtsp/rtsps 协议"
        netloc = parsed.netloc or ""
        if "@" in netloc:
            _, hostport = netloc.split("@", 1)
            hostpart = (hostport.split(":")[0] or "").strip()
        else:
            hostpart = (netloc.split(":")[0] or "").strip()
        if not hostpart:
            return False, "必须有 host"
        return True, ""
    except Exception as e:
        return False, str(e)
