"""
视频管理：GStreamer RTSP 播放到 Qt Widget overlay。
若 GStreamer/gi 缺失则降级为占位模式，不崩溃。
"""

import logging
import queue
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

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


class VideoManager:
    """RTSP 播放到 Qt Widget overlay，自动重连，不阻塞 UI"""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._loop = None
        self._main_loop = None
        self._pipeline = None
        self._current_url: str | None = None
        self._current_win_id: int | None = None
        self._stop_requested = False
        self._reconnect_timer_src = None
        self._reconnect_delay_s = 2.0
        self._placeholders: list = []  # callbacks to show placeholder hint
        self._status_callbacks: list = []  # Callable[[str], None]  # status: playing|reconnecting|failed|stopped
        self._cmd_queue: queue.Queue = queue.Queue()

    def on_status_change(self, callback: Callable[[str], None]) -> None:
        """注册状态回调：callback(status) 其中 status 为 playing|reconnecting|failed|stopped"""
        self._status_callbacks.append(callback)

    def _emit_status(self, status: str) -> None:
        for cb in self._status_callbacks:
            try:
                cb(status)
            except Exception as e:
                logger.debug("status callback error: %s", e)

    def start(self, url: str, win_id: int | None) -> None:
        """启动或切换到指定 RTSP 流，渲染到 win_id（Qt 的 winId()）"""
        logger.debug("[VideoManager] start url=%s win_id=%s", url[:80] if url else "", win_id)
        if not _try_import_gst() or not _GST_AVAILABLE:
            logger.warning("[VideoManager] GStreamer 不可用，降级占位")
            self._emit_placeholder("GStreamer 不可用")
            return
        self._current_url = url
        self._current_win_id = win_id
        self._stop_requested = False
        if self._thread is None or not self._thread.is_alive():
            logger.debug("[VideoManager] 启动 GLib 工作线程")
            self._thread = threading.Thread(target=self._run_glib_loop, daemon=True)
            self._thread.start()
            time.sleep(0.15)  # 等待线程与主循环启动
        self._cmd_queue.put(("start",))

    def stop(self) -> None:
        """停止播放"""
        self._stop_requested = True
        self._cmd_queue.put(("stop",))

    def switch(self, url: str) -> None:
        """切换 URL（保持当前 win_id）"""
        logger.debug("[VideoManager] switch url=%s", url[:80] if url else "")
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
        """注册占位提示回调：callback(msg: str)"""
        self._placeholders.append(callback)

    def _process_cmd_start(self) -> None:
        """在工作线程中执行 start（停止旧 pipeline 并启动新 pipeline）"""
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
                logger.info("自动重连 RTSP: %s", self._current_url[:60])
                self._do_start_pipeline()
            return False

        self._reconnect_timer_src = _GLib.timeout_add(
            int(self._reconnect_delay_s * 1000), on_timer
        )

    def _run_glib_loop(self) -> None:
        if not _GLib:
            return
        self._main_loop = _GLib.MainLoop()
        # 定时检查命令队列（避免跨线程 GLib context 问题）
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
                    if cmd[0] == "start" or cmd[0] == "switch":
                        self._process_cmd_start()
            except queue.Empty:
                pass
            return True  # 继续轮询

        _GLib.timeout_add(50, poll_queue)
        self._main_loop.run()
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
        if not _Gst or self._stop_requested or not self._current_url:
            logger.debug("[VideoManager] _do_start_pipeline 跳过: gst=%s stop=%s url=%s",
                         bool(_Gst), self._stop_requested, bool(self._current_url))
            return

        self._do_stop_pipeline()
        logger.debug("[VideoManager] 创建 pipeline url=%s win_id=%s",
                     self._current_url[:60], self._current_win_id)

        # rtspsrc ! decodebin ! videoconvert ! xvimagesink (X11 overlay)
        # 备选: ximagesink 或 autovideosink（无 overlay）
        sink_name = "xvimagesink"
        try:
            sink = _Gst.ElementFactory.make(sink_name, "sink")
        except Exception:
            sink = None
        if sink is None:
            sink_name = "ximagesink"
            sink = _Gst.ElementFactory.make(sink_name, "sink")
        if sink is None:
            sink_name = "autovideosink"
            sink = _Gst.ElementFactory.make(sink_name, "sink")
        if sink is None:
            logger.error("[VideoManager] 无可用 video sink (xvimagesink/ximagesink/autovideosink)")
            self._emit_placeholder("无可用视频输出")
            return
        logger.debug("[VideoManager] 使用 sink: %s", sink_name)

        url_escaped = self._current_url.replace("\\", "\\\\").replace("'", "\\'")
        pipeline_desc = (
            f"rtspsrc location='{url_escaped}' latency=100 ! "
            "decodebin ! videoconvert ! videoscale ! "
            "video/x-raw,width=640,height=360 ! "
            f"{sink_name} name=sink"
        )
        try:
            self._pipeline = _Gst.parse_launch(pipeline_desc)
        except Exception as e:
            logger.warning("parse_launch 失败，尝试简化 pipeline: %s", e)
            pipeline_desc = (
                f"rtspsrc location='{url_escaped}' latency=100 ! "
                "decodebin ! videoconvert ! "
                f"{sink_name} name=sink"
            )
            try:
                self._pipeline = _Gst.parse_launch(pipeline_desc)
            except Exception as e2:
                logger.error("创建 pipeline 失败: %s", e2)
                self._emit_placeholder("创建 pipeline 失败")
                return

        sink_el = self._pipeline.get_by_name("sink")
        if sink_el and self._current_win_id and self._current_win_id != 0:
            try:
                sink_el.set_property("force-aspect-ratio", True)
                if hasattr(sink_el.props, "draw_borders"):
                    sink_el.set_property("draw-borders", False)
                # VideoOverlay 接口设置窗口句柄（Qt winId）
                if _GstVideo and hasattr(_GstVideo, "VideoOverlay"):
                    _GstVideo.VideoOverlay.set_window_handle(sink_el, self._current_win_id)
                elif hasattr(sink_el, "set_window_handle"):
                    sink_el.set_window_handle(self._current_win_id)
                elif hasattr(sink_el, "set_property") and hasattr(sink_el.props, "window_handle"):
                    sink_el.set_property("window-handle", self._current_win_id)
            except Exception as e:
                logger.debug("[VideoManager] set overlay 失败: %s", e)

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_bus_error)
        bus.connect("message::eos", self._on_bus_eos)
        bus.connect("message::warning", self._on_bus_warning)

        self._pipeline.set_state(_Gst.State.PLAYING)
        self._emit_status("playing")
        logger.info("RTSP 播放已启动: %s", self._current_url[:60])

    def _on_bus_error(self, bus, msg) -> None:
        err, dbg = msg.parse_error()
        logger.warning("GStreamer ERROR: %s | %s", err, dbg)
        self._schedule_reconnect()

    def _on_bus_eos(self, bus, msg) -> None:
        logger.info("GStreamer EOS，将自动重连")
        self._schedule_reconnect()

    def _on_bus_warning(self, bus, msg) -> None:
        warn, dbg = msg.parse_warning()
        logger.debug("GStreamer WARNING: %s | %s", warn, dbg)


# 便捷实例（可选单例）
_default_manager: VideoManager | None = None


def get_video_manager() -> VideoManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = VideoManager()
    return _default_manager
