"""
Modbus 主站：后台线程轮询，按 spec 批量读/写，掉线判断，原始数据交给 devices 解析后更新 AppState。
支持 MockTransport / RealSerialTransport（use_mock 配置切换）。
RealSerialTransport：pymodbus 串口，自动重连退避（1s,2s,5s…上限 10s）。
"""

import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SPEC_PATH = Path(__file__).resolve().parent.parent / "spec" / "modbus_spec.json"

POLL_FAST = "FAST"
POLL_SLOW = "SLOW"
POLL_VERY_SLOW = "VERY_SLOW"
POLL_GROUPS = (POLL_FAST, POLL_SLOW, POLL_VERY_SLOW)

OFFLINE_THRESHOLD = 3

# 重连退避序列（秒），上限 10s
RECONNECT_BACKOFF = (1, 2, 5, 10)


# ---------- Transport 接口 ----------

class TransportError(Exception):
    """读写失败（含掉线、超时、重连退避中）"""
    pass


class ModbusTransport:
    """Modbus 传输层抽象"""

    def read_coils(self, slave: int, addr0: int, count: int) -> list[int]:
        raise NotImplementedError

    def read_discrete_inputs(self, slave: int, addr0: int, count: int) -> list[int]:
        raise NotImplementedError

    def read_input_registers(self, slave: int, addr0: int, count: int) -> list[int]:
        raise NotImplementedError

    def read_holding_registers(self, slave: int, addr0: int, count: int) -> list[int]:
        raise NotImplementedError

    def write_coil(self, slave: int, addr0: int, value: bool | int) -> None:
        raise NotImplementedError

    def write_holding_register(self, slave: int, addr0: int, value: int) -> None:
        raise NotImplementedError


# ---------- RealSerialTransport ----------

class RealSerialTransport(ModbusTransport):
    """pymodbus 串口传输，支持自动重连退避"""

    def __init__(self, port: str, baudrate: int = 19200, parity: str = "N", stopbits: int = 1, timeout: float = 0.2):
        self._port = port
        self._baudrate = baudrate
        self._parity = parity
        self._stopbits = stopbits
        self._timeout = timeout
        self._lock = threading.Lock()
        self._client: Any = None
        self._backoff_idx = 0
        self._backoff_until = 0.0

    def _create_client(self) -> Any:
        try:
            from pymodbus.client import ModbusSerialClient
        except ImportError:
            raise TransportError("pymodbus 未安装，请运行: pip install pymodbus[serial]")

        parity_map = {"N": "N", "E": "E", "O": "O"}
        return ModbusSerialClient(
            port=self._port,
            baudrate=self._baudrate,
            parity=parity_map.get(self._parity.upper(), "N"),
            stopbits=self._stopbits,
            bytesize=8,
            timeout=self._timeout,
        )

    def _ensure_connected(self) -> None:
        now = time.time()
        if now < self._backoff_until:
            raise TransportError("重连退避中")
        with self._lock:
            if self._client is None:
                self._client = self._create_client()
            if self._client.connected:
                return
            if self._client.connect():
                self._backoff_idx = 0
                logger.info("Modbus 串口已连接: %s", self._port)
                return
        self._on_disconnect()

    def _on_disconnect(self) -> None:
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
            delay = RECONNECT_BACKOFF[min(self._backoff_idx, len(RECONNECT_BACKOFF) - 1)]
            self._backoff_idx += 1
            self._backoff_until = time.time() + delay
            logger.warning("Modbus 断线，%ds 后重连 (第 %d 次)", delay, self._backoff_idx)
        raise TransportError("串口断线")

    def read_coils(self, slave: int, addr0: int, count: int) -> list[int]:
        self._ensure_connected()
        with self._lock:
            r = self._client.read_coils(addr0, count, slave=slave)
        if r.isError():
            self._on_disconnect()
        bits = getattr(r, "bits", None) or []
        return [1 if b else 0 for b in bits[:count]]

    def read_discrete_inputs(self, slave: int, addr0: int, count: int) -> list[int]:
        self._ensure_connected()
        with self._lock:
            r = self._client.read_discrete_inputs(addr0, count, slave=slave)
        if r.isError():
            self._on_disconnect()
        bits = getattr(r, "bits", None) or []
        return [1 if b else 0 for b in bits[:count]]

    def read_input_registers(self, slave: int, addr0: int, count: int) -> list[int]:
        self._ensure_connected()
        with self._lock:
            r = self._client.read_input_registers(addr0, count, slave=slave)
        if r.isError():
            self._on_disconnect()
        regs = getattr(r, "registers", None) or []
        return list(regs[:count])

    def read_holding_registers(self, slave: int, addr0: int, count: int) -> list[int]:
        self._ensure_connected()
        with self._lock:
            r = self._client.read_holding_registers(addr0, count, slave=slave)
        if r.isError():
            self._on_disconnect()
        regs = getattr(r, "registers", None) or []
        return list(regs[:count])

    def write_coil(self, slave: int, addr0: int, value: bool | int) -> None:
        self._ensure_connected()
        with self._lock:
            r = self._client.write_coil(addr0, bool(value), slave=slave)
        if r.isError():
            self._on_disconnect()

    def write_holding_register(self, slave: int, addr0: int, value: int) -> None:
        self._ensure_connected()
        with self._lock:
            r = self._client.write_register(addr0, value, slave=slave)
        if r.isError():
            self._on_disconnect()

    def close(self) -> None:
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None


# ---------- MockTransport ----------

class MockTransport(ModbusTransport):
    """内存模拟，可 inject_failure 模拟掉线"""

    def __init__(self):
        self._data: dict[int, dict[str, dict[int, int]]] = {}
        self._lock = threading.Lock()
        self._fail_slaves: set[int] = set()

    def _ensure_slave(self, slave: int) -> dict[str, dict[int, int]]:
        with self._lock:
            if slave not in self._data:
                self._data[slave] = {"coils": {}, "di": {}, "ir": {}, "hr": {}}
            return self._data[slave]

    def _check_fail(self, slave: int) -> None:
        if slave in self._fail_slaves:
            raise TransportError(f"MockTransport: slave {slave} injected failure")

    def inject_failure(self, slave: int) -> None:
        self._fail_slaves.add(slave)

    def clear_failure(self, slave: int) -> None:
        self._fail_slaves.discard(slave)

    def _read_bits(self, slave: int, key: str, addr0: int, count: int) -> list[int]:
        self._check_fail(slave)
        d = self._ensure_slave(slave)[key]
        return [1 if d.get(addr0 + i) else 0 for i in range(count)]

    def _read_regs(self, slave: int, key: str, addr0: int, count: int) -> list[int]:
        self._check_fail(slave)
        d = self._ensure_slave(slave)[key]
        return [d.get(addr0 + i, 0) for i in range(count)]

    def read_coils(self, slave: int, addr0: int, count: int) -> list[int]:
        return self._read_bits(slave, "coils", addr0, count)

    def read_discrete_inputs(self, slave: int, addr0: int, count: int) -> list[int]:
        return self._read_bits(slave, "di", addr0, count)

    def read_input_registers(self, slave: int, addr0: int, count: int) -> list[int]:
        return self._read_regs(slave, "ir", addr0, count)

    def read_holding_registers(self, slave: int, addr0: int, count: int) -> list[int]:
        return self._read_regs(slave, "hr", addr0, count)

    def write_coil(self, slave: int, addr0: int, value: bool | int) -> None:
        self._check_fail(slave)
        with self._lock:
            self._ensure_slave(slave)["coils"][addr0] = 1 if value else 0

    def write_holding_register(self, slave: int, addr0: int, value: int) -> None:
        self._check_fail(slave)
        with self._lock:
            self._ensure_slave(slave)["hr"][addr0] = value

    def set_input_register(self, slave: int, addr0: int, value: int) -> None:
        with self._lock:
            self._ensure_slave(slave)["ir"][addr0] = value

    def set_discrete_input(self, slave: int, addr0: int, value: bool | int) -> None:
        with self._lock:
            self._ensure_slave(slave)["di"][addr0] = 1 if value else 0

    def set_coil(self, slave: int, addr0: int, value: bool | int) -> None:
        with self._lock:
            self._ensure_slave(slave)["coils"][addr0] = 1 if value else 0

    def set_holding_register(self, slave: int, addr0: int, value: int) -> None:
        with self._lock:
            self._ensure_slave(slave)["hr"][addr0] = value


# ---------- Spec 加载 ----------

def load_spec(spec_path: Path | None = None) -> dict[str, Any] | None:
    path = spec_path or _SPEC_PATH
    if not path.exists():
        logger.error("Modbus 规格文件不存在: %s", path)
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("加载 modbus_spec.json 失败: %s", e)
        return None


def _ranges(items: list[dict], key_addr: str = "addr0") -> list[tuple[int, int]]:
    if not items:
        return []
    addrs = sorted(set(p[key_addr] for p in items))
    ranges_: list[tuple[int, int]] = []
    start, count = addrs[0], 1
    for i in range(1, len(addrs)):
        if addrs[i] == addrs[i - 1] + 1:
            count += 1
        else:
            ranges_.append((start, count))
            start, count = addrs[i], 1
    ranges_.append((start, count))
    return ranges_


def _points_by_poll(spec: dict[str, Any]) -> dict[str, list[tuple[str, str, int, dict]]]:
    out: dict[str, list[tuple[str, str, int, dict]]] = {
        POLL_FAST: [], POLL_SLOW: [], POLL_VERY_SLOW: [],
    }
    block_keys = ("coils", "discrete_inputs", "holding_regs", "input_regs")
    for sid, blocks in spec.items():
        for block_key in block_keys:
            for p in blocks.get(block_key, []):
                poll = (p.get("poll") or "").strip().upper()
                if poll not in out or poll == "N/A":
                    continue
                out[poll].append((sid, block_key, int(p.get("addr0", 0)), p))
    return out


def _build_read_plan(spec: dict, poll_group: str) -> list[tuple[str, str, int, int]]:
    by_poll = _points_by_poll(spec)
    points = by_poll.get(poll_group, [])
    by_slave_block: dict[tuple[str, str], list[int]] = {}
    for sid, block_key, addr0, _ in points:
        k = (sid, block_key)
        if k not in by_slave_block:
            by_slave_block[k] = []
        by_slave_block[k].append(addr0)
    plan = []
    for (sid, block), addrs in by_slave_block.items():
        addrs = sorted(set(addrs))
        for start, count in _ranges([{"addr0": a} for a in addrs]):
            plan.append((sid, block, start, count))
    return plan


# ---------- 写队列与写后回读确认 ----------

class WriteRequest:
    __slots__ = ("slave", "kind", "addr0", "value", "verify_timeout_s", "verify_user_data")

    def __init__(
        self,
        slave: int,
        kind: str,
        addr0: int,
        value: Any,
        verify_timeout_s: float = 0,
        verify_user_data: Any = None,
    ):
        self.slave = slave
        self.kind = kind
        self.addr0 = addr0
        self.value = value
        self.verify_timeout_s = verify_timeout_s
        self.verify_user_data = verify_user_data


# 写后回读待确认项：slave/point/expected/deadline/user_data
class _PendingVerify:
    __slots__ = ("slave", "kind", "addr0", "expected", "deadline_ts", "user_data")

    def __init__(self, slave: int, kind: str, addr0: int, expected: Any, deadline_ts: float, user_data: Any):
        self.slave = slave
        self.kind = kind
        self.addr0 = addr0
        self.expected = expected
        self.deadline_ts = deadline_ts
        self.user_data = user_data


# ---------- ModbusMaster ----------

class ModbusMaster:
    """后台线程：轮询、写队列、掉线计数、重连、每 slave 统计。所有 IO 在后台，UI 仅收 state 更新。"""

    def __init__(
        self,
        transport: ModbusTransport,
        app_state: Any,
        poll_ms: dict[str, int] | None = None,
        spec_path: Path | None = None,
        device_parser: Any = None,
        update_bridge: Any = None,
        spec: dict[str, Any] | None = None,
    ):
        self._transport = transport
        self._app_state = app_state
        self._poll_ms = poll_ms or {}
        self._spec_path = spec_path or _SPEC_PATH
        self._device_parser = device_parser
        self._update_bridge = update_bridge
        self._write_queue: queue.Queue[WriteRequest] = queue.Queue()
        self._spec = spec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stats_lock = threading.Lock()
        # 每 slave 统计：预初始化 1..9，避免运行中插入新 key 导致 "dictionary changed size during iteration"
        _default_stat = {"success_count": 0, "fail_count": 0, "last_rtt_ms": None, "last_ok_ts": 0.0}
        self._slave_stats = {sid: dict(_default_stat) for sid in range(1, 10)}
        self._last_comm: dict[int, dict[str, Any]] = {}
        # 写后回读待确认列表（主循环内检查，不阻塞 UI）
        self._pending_verifies: list[_PendingVerify] = []
        self._pending_lock = threading.Lock()

    def _slave_stat(self, sid: int) -> dict[str, Any]:
        """返回已有 dict，不插入新 key；若 key 不存在则返回默认结构但不写入。"""
        if sid in self._slave_stats:
            return self._slave_stats[sid]
        return {"success_count": 0, "fail_count": 0, "last_rtt_ms": None, "last_ok_ts": 0.0}

    def _apply_update(self, **kwargs: Any) -> None:
        if self._update_bridge is not None and hasattr(self._update_bridge, "state_updates_ready"):
            self._update_bridge.state_updates_ready.emit(kwargs)
        else:
            self._app_state.update(**kwargs)

    def _load_spec(self) -> bool:
        self._spec = load_spec(self._spec_path)
        if self._spec is None:
            self._spec = {}
            return False
        return True

    def write_coil(
        self,
        slave: int,
        addr0: int,
        value: bool | int,
        verify_timeout_s: float = 0,
        verify_user_data: Any = None,
    ) -> None:
        self._write_queue.put(
            WriteRequest(slave, "coil", addr0, value, verify_timeout_s, verify_user_data)
        )

    def write_holding(
        self,
        slave: int,
        addr0: int,
        value: int,
        verify_timeout_s: float = 0,
        verify_user_data: Any = None,
    ) -> None:
        self._write_queue.put(
            WriteRequest(slave, "holding", addr0, value, verify_timeout_s, verify_user_data)
        )

    def _drain_writes(self) -> None:
        while True:
            try:
                req = self._write_queue.get_nowait()
            except queue.Empty:
                break
            try:
                t0 = time.perf_counter()
                if req.kind == "coil":
                    self._transport.write_coil(req.slave, req.addr0, req.value)
                else:
                    self._transport.write_holding_register(req.slave, req.addr0, req.value)
                rtt = (time.perf_counter() - t0) * 1000
                s = self._slave_stat(req.slave)
                s["success_count"] = s.get("success_count", 0) + 1
                s["last_rtt_ms"] = rtt
                s["last_ok_ts"] = time.time()
                # 写后回读确认：记录 pending，由轮询后检查
                timeout_s = getattr(req, "verify_timeout_s", 0) or 0
                user_data = getattr(req, "verify_user_data", None)
                if timeout_s > 0 and user_data is not None:
                    expected = (1 if req.value else 0) if req.kind == "coil" else req.value
                    with self._pending_lock:
                        self._pending_verifies.append(
                            _PendingVerify(
                                req.slave,
                                req.kind,
                                req.addr0,
                                expected,
                                time.time() + timeout_s,
                                user_data,
                            )
                        )
            except TransportError as e:
                logger.debug("写失败 slave=%s addr=%s: %s", req.slave, req.addr0, e)
                s = self._slave_stat(req.slave)
                s["fail_count"] = s.get("fail_count", 0) + 1

    def _read_batch(
        self, slave_id: str, block: str, start: int, count: int,
    ) -> tuple[list[int] | None, float | None]:
        """返回 (vals, rtt_ms)，失败返回 (None, None)"""
        slave = int(slave_id)
        try:
            t0 = time.perf_counter()
            if block == "coils":
                vals = self._transport.read_coils(slave, start, count)
            elif block == "discrete_inputs":
                vals = self._transport.read_discrete_inputs(slave, start, count)
            elif block == "input_regs":
                vals = self._transport.read_input_registers(slave, start, count)
            elif block == "holding_regs":
                vals = self._transport.read_holding_registers(slave, start, count)
            else:
                return None, None
            rtt = (time.perf_counter() - t0) * 1000
            s = self._slave_stat(slave)
            s["success_count"] = s.get("success_count", 0) + 1
            s["fail_count"] = 0  # 成功则清零连续失败
            s["last_rtt_ms"] = rtt
            s["last_ok_ts"] = time.time()
            return vals, rtt
        except TransportError as e:
            logger.debug("读失败 slave=%s %s @%s: %s", slave_id, block, start, e)
            s = self._slave_stat(slave)
            s["fail_count"] = s.get("fail_count", 0) + 1
            return None, None

    def _poll_group(self, spec: dict, poll_group: str) -> dict[str, dict[str, dict[int, int]]]:
        plan = _build_read_plan(spec, poll_group)
        result: dict[str, dict[str, dict[int, int]]] = {}
        for slave_id, block, start, count in plan:
            if slave_id not in result:
                result[slave_id] = {"coils": {}, "di": {}, "ir": {}, "hr": {}}
            raw_key = "di" if block == "discrete_inputs" else "ir" if block == "input_regs" else "hr" if block == "holding_regs" else "coils"
            vals, _ = self._read_batch(slave_id, block, start, count)
            if vals is None:
                continue
            for i, v in enumerate(vals):
                result[slave_id][raw_key][start + i] = v
        return result

    def _merge_poll_into(self, acc: dict, group_result: dict) -> None:
        for sid, data in group_result.items():
            if sid not in acc:
                acc[sid] = {"coils": {}, "di": {}, "ir": {}, "hr": {}}
            for k in ("coils", "di", "ir", "hr"):
                acc[sid][k].update(data[k])

    def _check_pending_verifies(self, accumulated: dict[str, dict[str, dict[int, int]]]) -> None:
        """轮询更新 snapshot 后检查待确认项：达到 expected 则成功回调，超时则失败回调。主线程通过 bridge.verify_done 收结果。"""
        now = time.time()
        done: list[tuple[bool, Any]] = []
        with self._pending_lock:
            remaining = []
            for p in self._pending_verifies:
                sid = str(p.slave)
                raw_key = "coils" if p.kind == "coil" else "hr"
                current = (accumulated.get(sid) or {}).get(raw_key, {}).get(p.addr0)
                if current is not None and current == p.expected:
                    done.append((True, p.user_data))
                    continue
                if now >= p.deadline_ts:
                    done.append((False, p.user_data))
                    continue
                remaining.append(p)
            self._pending_verifies = remaining
        bridge = self._update_bridge
        if bridge is not None and hasattr(bridge, "verify_done"):
            for success, user_data in done:
                bridge.verify_done.emit(success, user_data)

    def _update_comm_status(self) -> None:
        comm: dict[int, dict[str, Any]] = {}
        for sid in range(1, 10):
            s = self._slave_stats.get(sid, {})
            fail_count = s.get("fail_count", 0)
            success_count = s.get("success_count", 0)
            # 从未成功通信不算 online；且连续失败次数须低于阈值
            online = success_count > 0 and fail_count < OFFLINE_THRESHOLD
            last_rtt = s.get("last_rtt_ms")
            last_ok_ts = s.get("last_ok_ts", 0.0)
            comm[sid] = {
                "online": online,
                "error_count": fail_count,
                "success_count": success_count,
                "fail_count": fail_count,
                "last_rtt_ms": last_rtt,
                "last_ok_ts": last_ok_ts,
            }
        if comm != self._last_comm:
            self._last_comm = dict(comm)
            self._apply_update(comm=comm)

    def _run_loop(self) -> None:
        spec = self._spec or {}
        accumulated: dict[str, dict[str, dict[int, int]]] = {}
        last_poll: dict[str, float] = {g: 0.0 for g in POLL_GROUPS}
        poll_ms = {
            POLL_FAST: self._poll_ms.get("FAST_MS", 300),
            POLL_SLOW: self._poll_ms.get("SLOW_MS", 1000),
            POLL_VERY_SLOW: self._poll_ms.get("VERY_SLOW_MS", 5000),
        }

        while not self._stop.is_set():
            now = time.time()
            self._drain_writes()

            for group in POLL_GROUPS:
                if (now - last_poll[group]) * 1000 >= poll_ms[group]:
                    last_poll[group] = now
                    if spec:
                        res = self._poll_group(spec, group)
                        self._merge_poll_into(accumulated, res)
                        if res and self._device_parser:
                            merged: dict[str, Any] = {}
                            for slave_id in res:
                                raw = accumulated.get(slave_id, {"coils": {}, "di": {}, "ir": {}, "hr": {}})
                                updates = self._device_parser(slave_id, raw, spec)
                                for domain, fields in (updates or {}).items():
                                    if isinstance(fields, dict):
                                        merged.setdefault(domain, {}).update(fields)
                            if merged:
                                self._apply_update(**merged)
                    break

            self._check_pending_verifies(accumulated)
            self._update_comm_status()
            self._stop.wait(timeout=0.1)

    def start(self) -> None:
        if self._spec is None:
            self._load_spec()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("ModbusMaster 后台线程已启动")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        if hasattr(self._transport, "close"):
            try:
                self._transport.close()
            except Exception as e:
                logger.debug("关闭 transport 时异常: %s", e)

    def get_link_summary(self) -> dict[str, int]:
        """返回链接摘要：在线 slave 数、总错误数，供 Settings 页面显示。锁内复制后遍历，不抛异常。"""
        with self._stats_lock:
            snap = {k: dict(v) for k, v in self._slave_stats.items()}
        online = sum(
            1 for sid in range(1, 10)
            if snap.get(sid, {}).get("success_count", 0) > 0
            and snap.get(sid, {}).get("fail_count", 0) < OFFLINE_THRESHOLD
        )
        total_errors = sum(snap.get(sid, {}).get("fail_count", 0) for sid in range(1, 10))
        return {"online_slaves": online, "total_errors": total_errors}

    def is_slave_online(self, slave_id: int) -> bool:
        """判断从站是否在线：success_count>0 且 fail_count<阈值。"""
        with self._stats_lock:
            s = self._slave_stats.get(slave_id, {})
        return s.get("success_count", 0) > 0 and s.get("fail_count", 0) < OFFLINE_THRESHOLD

    def restart_with_config(self, new_config: Any) -> None:
        """
        使用 new_config 中的串口参数重新初始化 transport 并重启轮询。
        在后台线程执行，不阻塞 UI。失败时保持旧连接不崩溃（回滚到旧 config）。
        """
        def _do_restart() -> None:
            logger.info("ModbusMaster 开始 restart_with_config (port=%s baudrate=%s)",
                        getattr(new_config.modbus, "port", ""),
                        getattr(new_config.modbus, "baudrate", ""))
            try:
                new_transport = create_transport_from_config(new_config)
                logger.info("ModbusMaster 已创建新 transport，准备停止旧连接")
            except Exception as e:
                logger.warning("ModbusMaster restart_with_config 创建新 transport 失败，保持旧连接: %s", e)
                return

            old_transport = self._transport
            self._stop.set()
            if self._thread:
                self._thread.join(timeout=3.0)
                if self._thread.is_alive():
                    logger.error("ModbusMaster 旧线程未能及时退出，回滚到旧连接")
                    self._stop.clear()
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                    try:
                        new_transport.close()
                    except Exception:
                        pass
                    return
                self._thread = None

            try:
                if hasattr(old_transport, "close"):
                    try:
                        old_transport.close()
                    except Exception as e:
                        logger.debug("关闭旧 transport 时异常: %s", e)
                self._transport = new_transport
                self._stop.clear()
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()
                logger.info("ModbusMaster restart_with_config 完成，已启动新连接")
            except Exception as e:
                logger.exception("ModbusMaster restart_with_config 启动失败，尝试回滚: %s", e)
                self._transport = old_transport
                try:
                    new_transport.close()
                except Exception:
                    pass
                self._stop.clear()
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()
                logger.warning("ModbusMaster 已回滚到旧 transport 并重启")

        threading.Thread(target=_do_restart, daemon=True).start()


# ---------- 全局实例（供 Settings 等页面调用 restart_with_config / get_link_summary）----------

_modbus_master_instance: "ModbusMaster | None" = None


def register_modbus_master(master: ModbusMaster) -> None:
    """Modbus 启动后注册，供 Settings 等获取"""
    global _modbus_master_instance
    _modbus_master_instance = master


def get_modbus_master() -> ModbusMaster | None:
    """获取已注册的 ModbusMaster 实例，未就绪时返回 None"""
    return _modbus_master_instance


# ---------- 工厂 ----------

def create_transport_from_config(config: Any) -> ModbusTransport:
    """根据 config.modbus 创建 Transport，use_mock 为 True 时返回 MockTransport"""
    m = config.modbus
    if getattr(m, "use_mock", True):
        return MockTransport()
    return RealSerialTransport(
        port=m.port,
        baudrate=m.baudrate,
        parity=m.parity,
        stopbits=m.stopbits,
        timeout=m.timeout,
    )
