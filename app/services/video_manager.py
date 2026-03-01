"""
视频管理：GStreamer RTSP 播放到 Qt Widget overlay。
树莓派 X11/Wayland 会话检测，支持 config 强制 sink；嵌入失败时降级占位并提示切换 X11。
所有异常捕获，不导致 UI 崩溃。
"""

import logging
import os
import re
import queue
import threading
import time
from typing import Callable

from app.core.sanitize import mask_url, validate_rtsp_url

logger = logging.getLogger(__name__)


def _redact_urls_in_message(text: str) -> str:
    """脱敏消息中的 RTSP URL，避免泄露密码。"""
    if not text or not isinstance(text, str):
        return text or ""
    out = text
    for m in re.finditer(r"rtsp[s]?://[^\s\'\")\]]+", text):
        out = out.replace(m.group(0), mask_url(m.group(0), keep_path=False))
    return out

_GST_AVAILABLE = False
_Gst = None
_GstVideo = None
_GLib = None


def _try_import_gst() -> bool:
    global _GST_AVAILABLE, _Gst, _GstVideo, _GLib
    if _GST_AVAILABLE:
        return True
    try:
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst, GLib
        _Gst = Gst
        _GLib = GLib
        Gst.init(None)
        try:
            from gi.repository import GstVideo
            _GstVideo = GstVideo
        except ImportError:
            _GstVideo = None
        _GST_AVAILABLE = True
        logger.info("GStreamer 已加载")
        return True
    except Exception as e:
        logger.warning("GStreamer/gi 不可用，降级为占位模式: %s", e)
        _GST_AVAILABLE = False
        return False


def is_gst_available() -> bool:
    return _try_import_gst() and _GST_AVAILABLE


def is_gi_available() -> bool:
    """gi (PyGObject) 是否可用。"""
    try:
        import gi  # noqa: F401
        return True
    except Exception:
        return False


def is_overlay_supported() -> bool:
    """GstVideoOverlay 是否可用（窗口嵌入依赖）。"""
    _try_import_gst()
    return _GstVideo is not None and hasattr(_GstVideo, "VideoOverlay")


def _get_session_type() -> str:
    """读取 XDG_SESSION_TYPE（wayland/x11），未设置或空则视为 x11 兼容。"""
    st = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()
    if not st:
        st = "unknown"
    logger.info("[VideoManager] 会话类型: XDG_SESSION_TYPE=%s", st)
    return st


def _resolve_sink(session_type: str, prefer_backend: str, sink_config: str) -> str:
    """
    根据会话类型与 config 解析实际使用的 GStreamer sink 名称。
    返回: ximagesink | glimagesink | waylandsink | xvimagesink | autovideosink
    """
    if sink_config and sink_config != "auto":
        return sink_config
    # prefer_backend: auto | x11 | wayland
    use_wayland = (session_type == "wayland") or (prefer_backend == "wayland")
    use_x11 = (session_type == "x11") or (prefer_backend == "x11") or (session_type == "unknown")

    if use_wayland:
        for name in ("waylandsink", "glimagesink", "autovideosink"):
            try:
                if _Gst and _Gst.ElementFactory.make(name, "sink"):
                    return name
            except Exception:
                continue
        return "autovideosink"
    # X11 优先
    for name in ("xvimagesink", "ximagesink", "glimagesink", "autovideosink"):
        try:
            if _Gst and _Gst.ElementFactory.make(name, "sink"):
                return name
        except Exception:
            continue
    return "autovideosink"


class VideoManager:
    """RTSP 播放到 Qt Widget overlay，自动重连；支持 start_embedded(rtsp_url, win_id) -> bool。"""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._main_loop = None
        self._pipeline = None
        self._current_url: str | None = None
        self._current_win_id: int | None = None
        self._stop_requested = False
        self._reconnect_timer_src = None
        self._reconnect_delay_s = 2.0
        self._placeholders: list = []
        self._status_callbacks: list = []
        self._cmd_queue: queue.Queue = queue.Queue()
        self._session_type = ""
        self._last_error: str = ""
        self._embed_result: bool | None = None  # 工作线程设置，start_embedded 轮询
        self._selected_sink: str = ""
        self._backend: str = "auto"

    def _get_config(self):
        try:
            from app.core.config import get_config
            return get_config()
        except Exception:
            return None

    def on_status_change(self, callback: Callable[[str], None]) -> None:
        self._status_callbacks.append(callback)

    def _emit_status(self, status: str) -> None:
        for cb in self._status_callbacks:
            try:
                cb(status)
            except Exception as e:
                logger.debug("status callback error: %s", e)

    def _set_last_error(self, msg: str) -> None:
        self._last_error = (msg or "")[:200]

    @property
    def last_error(self) -> str:
        """最近一次嵌入/播放失败原因（已脱敏，可展示给用户）。"""
        return self._last_error

    def start_embedded(self, rtsp_url: str, win_id: int) -> bool:
        """
        启动 RTSP 嵌入到指定窗口。成功返回 True，失败返回 False 并设置 last_error。
        不抛异常。
        """
        self._last_error = ""
        if not rtsp_url or not rtsp_url.strip():
            self._set_last_error("未配置 RTSP 地址")
            return False
        ok, err = validate_rtsp_url(rtsp_url)
        if not ok:
            self._set_last_error("RTSP 地址不合法")
            return False
        cfg = self._get_config()
        if cfg and getattr(getattr(cfg, "video", None), "force_no_embed", False):
            self._set_last_error("当前配置已禁用嵌入（force_no_embed），建议切换到 X11 会话后重试")
            logger.info("[VideoManager] force_no_embed=true，跳过嵌入")
            return False
        if not _try_import_gst() or not _GST_AVAILABLE:
            self._set_last_error("GStreamer 不可用")
            return False
        self._session_type = _get_session_type()
        self._current_url = rtsp_url
        self._current_win_id = win_id if win_id else None
        self._stop_requested = False
        self._embed_result = None
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run_glib_loop, daemon=True)
            self._thread.start()
            time.sleep(0.2)
        self._cmd_queue.put(("start_embedded",))
        for _ in range(60):
            time.sleep(0.05)
            if self._embed_result is False:
                return False
            if self._embed_result is True:
                return True
        return False

    def start(self, url: str, win_id: int | None) -> None:
        """兼容旧接口：启动或切换到指定 RTSP 流。内部调用 start_embedded 若 win_id 有效。"""
        logger.debug("[VideoManager] start url=%s win_id=%s", mask_url(url, keep_path=False), win_id)
        if win_id and win_id != 0:
            ok = self.start_embedded(url, win_id)
            if not ok:
                self._emit_placeholder(self._last_error or "嵌入失败")
            return
        if not _try_import_gst() or not _GST_AVAILABLE:
            self._emit_placeholder("GStreamer 不可用")
            return
        self._current_url = url
        self._current_win_id = win_id
        self._stop_requested = False
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run_glib_loop, daemon=True)
            self._thread.start()
            time.sleep(0.15)
        self._cmd_queue.put(("start",))

    def stop(self) -> None:
        self._stop_requested = True
        self._cmd_queue.put(("stop",))

    def switch(self, url: str) -> None:
        logger.debug("[VideoManager] switch url=%s", mask_url(url, keep_path=False))
        self._current_url = url
        self._stop_requested = False
        self._cmd_queue.put(("switch",))

    def _emit_placeholder(self, msg: str) -> None:
        self._emit_status("failed")
        for cb in self._placeholders:
            try:
                cb(msg)
            except Exception as e:
                logger.debug("placeholder callback error: %s", e)

    def on_placeholder_hint(self, callback: Callable[[str], None]) -> None:
        self._placeholders.append(callback)

    def _process_cmd_start(self) -> None:
        self._unschedule_reconnect()
        self._do_stop_pipeline()
        self._do_start_pipeline()

    def _unschedule_reconnect(self) -> None:
        if self._reconnect_timer_src:
            try:
                _GLib.source_remove(self._reconnect_timer_src)
            except Exception:
                pass
            self._reconnect_timer_src = None

    def _schedule_reconnect(self) -> None:
        self._emit_status("reconnecting")
        def on_timer():
            self._reconnect_timer_src = None
            if not self._stop_requested and self._current_url:
                logger.info("自动重连 RTSP: %s", mask_url(self._current_url, keep_path=False))
                self._do_start_pipeline()
            return False
        self._reconnect_timer_src = _GLib.timeout_add(
            int(self._reconnect_delay_s * 1000), on_timer
        )

    def _run_glib_loop(self) -> None:
        if not _GLib:
            return
        self._main_loop = _GLib.MainLoop()
        def poll_queue():
            try:
                while True:
                    cmd = self._cmd_queue.get_nowait()
                    if cmd[0] == "stop":
                        self._unschedule_reconnect()
                        self._do_stop_pipeline()
                        self._emit_status("stopped")
                        self._main_loop.quit()
                        return False
                    if cmd[0] in ("start", "start_embedded", "switch"):
                        self._process_cmd_start()
            except queue.Empty:
                pass
            return True
        _GLib.timeout_add(50, poll_queue)
        try:
            self._main_loop.run()
        except Exception as e:
            logger.debug("MainLoop run: %s", e)
        self._main_loop = None
        self._do_stop_pipeline()

    def _do_stop_pipeline(self) -> None:
        if self._pipeline:
            try:
                self._pipeline.set_state(_Gst.State.NULL)
            except Exception as e:
                logger.debug("pipeline set NULL: %s", e)
            self._pipeline = None

    def _do_start_pipeline(self) -> None:
        self._embed_result = None
        if not _Gst or self._stop_requested or not self._current_url:
            self._embed_result = False
            return
        ok, _ = validate_rtsp_url(self._current_url)
        if not ok:
            self._set_last_error("RTSP 地址不合法")
            self._emit_placeholder(self._last_error)
            self._embed_result = False
            return
        cfg = self._get_config()
        video_cfg = getattr(cfg, "video", None) if cfg else None
        force_no_embed = getattr(video_cfg, "force_no_embed", False) if video_cfg else False
        if force_no_embed:
            self._set_last_error("已禁用嵌入，建议切换到 X11 会话")
            self._emit_placeholder(self._last_error)
            self._embed_result = False
            return
        self._do_stop_pipeline()
        st = self._session_type or _get_session_type()
        prefer_backend = getattr(video_cfg, "prefer_backend", "auto") if video_cfg else "auto"
        sink_config = getattr(video_cfg, "sink", "auto") if video_cfg else "auto"
        sink_name = _resolve_sink(st, prefer_backend, sink_config)
        self._backend = prefer_backend
        self._selected_sink = sink_name
        try:
            sink = _Gst.ElementFactory.make(sink_name, "sink")
        except Exception as e:
            logger.debug("make %s: %s", sink_name, e)
            sink = None
        if sink is None:
            for fallback in ("ximagesink", "xvimagesink", "autovideosink"):
                try:
                    sink = _Gst.ElementFactory.make(fallback, "sink")
                    if sink:
                        sink_name = fallback
                        self._selected_sink = sink_name
                        break
                except Exception:
                    continue
        if sink is None:
            self._set_last_error("无可用视频输出")
            self._emit_placeholder(self._last_error)
            if st == "wayland":
                logger.warning("Wayland 下嵌入失败，建议切换到 X11 会话以获得稳定内嵌显示")
            self._embed_result = False
            return
        logger.debug("[VideoManager] 使用 sink: %s", sink_name)
        url_escaped = self._current_url.replace("\\", "\\\\").replace("'", "\\'")
        pipeline_desc = (
            f"rtspsrc location='{url_escaped}' latency=100 ! "
            "decodebin ! videoconvert ! videoscale ! "
            "video/x-raw,width=640,height=360 ! "
            f"{sink_name} name=sink sync=false async=false"
        )
        try:
            self._pipeline = _Gst.parse_launch(pipeline_desc)
        except Exception as e:
            logger.debug("parse_launch 失败，尝试简化: %s", e)
            pipeline_desc = (
                f"rtspsrc location='{url_escaped}' latency=100 ! "
                "decodebin ! videoconvert ! "
                f"{sink_name} name=sink sync=false async=false"
            )
            try:
                self._pipeline = _Gst.parse_launch(pipeline_desc)
            except Exception as e2:
                self._set_last_error("创建 pipeline 失败")
                self._emit_placeholder(self._last_error)
                self._embed_result = False
                return
        sink_el = self._pipeline.get_by_name("sink")
        if sink_el and self._current_win_id and self._current_win_id != 0:
            try:
                sink_el.set_property("force-aspect-ratio", True)
                if hasattr(sink_el.props, "draw_borders"):
                    sink_el.set_property("draw-borders", False)
                if _GstVideo and hasattr(_GstVideo, "VideoOverlay"):
                    _GstVideo.VideoOverlay.set_window_handle(sink_el, self._current_win_id)
                elif hasattr(sink_el, "set_window_handle"):
                    sink_el.set_window_handle(self._current_win_id)
                elif hasattr(sink_el, "set_property") and hasattr(sink_el.props, "window_handle"):
                    sink_el.set_property("window-handle", self._current_win_id)
            except Exception as e:
                logger.warning("[VideoManager] 设置窗口句柄失败（可能当前会话不支持嵌入）: %s", e)
                self._set_last_error("当前会话不支持嵌入视频，建议切换到 X11")
                if st == "wayland":
                    logger.warning("Wayland 下 overlay 可能不可用，建议切换到 X11 会话")
                self._do_stop_pipeline()
                self._emit_placeholder(self._last_error)
                self._embed_result = False
                return
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_bus_error)
        bus.connect("message::eos", self._on_bus_eos)
        bus.connect("message::warning", self._on_bus_warning)
        try:
            self._pipeline.set_state(_Gst.State.PLAYING)
        except Exception as e:
            self._set_last_error("启动播放失败")
            self._do_stop_pipeline()
            self._emit_placeholder(self._last_error)
            self._embed_result = False
            return
        self._embed_result = True
        self._emit_status("playing")
        logger.info("RTSP 播放已启动: %s", mask_url(self._current_url, keep_path=False))

    def _on_bus_error(self, bus, msg) -> None:
        err, dbg = msg.parse_error()
        logger.warning("GStreamer ERROR: %s | %s", err, dbg)
        self._set_last_error("播放错误，请检查网络或 RTSP 地址")
        self._schedule_reconnect()

    def _on_bus_eos(self, bus, msg) -> None:
        logger.info("GStreamer EOS，将自动重连")
        self._schedule_reconnect()

    def _on_bus_warning(self, bus, msg) -> None:
        warn, dbg = msg.parse_warning()
        logger.debug("GStreamer WARNING: %s | %s", warn, dbg)


    def get_diagnostics(self) -> dict:
        """
        返回视频依赖与运行状态，供 Camera/诊断页展示。
        last_error 已脱敏，不包含 RTSP 密码。
        """
        st = self._session_type or _get_session_type()
        cfg = self._get_config()
        video_cfg = getattr(cfg, "video", None) if cfg else None
        backend = getattr(video_cfg, "prefer_backend", "auto") if video_cfg else "auto"
        sink = self._selected_sink or getattr(video_cfg, "sink", "auto") or "auto"
        if sink == "auto" and not self._selected_sink:
            sink = _resolve_sink(st, backend, "auto")
        return {
            "session_type": st,
            "gi_available": is_gi_available(),
            "gst_available": is_gst_available(),
            "overlay_supported": is_overlay_supported(),
            "selected_sink": sink,
            "backend": backend,
            "last_error": _redact_urls_in_message(self._last_error),
        }


_default_manager: VideoManager | None = None


def get_diagnostics() -> dict:
    """返回默认 VideoManager 的诊断信息（供 UI 调用）。"""
    return get_video_manager().get_diagnostics()


def get_video_manager() -> VideoManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = VideoManager()
    return _default_manager
