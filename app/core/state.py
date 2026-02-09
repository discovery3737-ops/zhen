"""应用状态 - 线程安全，不阻塞 UI"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


# --- comm: 每个 slave(1~9) ---
@dataclass
class SlaveComm:
    """单个从站通信状态"""
    online: bool = False
    error_count: int = 0
    last_ok_ts: float = 0.0
    success_count: int = 0
    fail_count: int = 0
    last_rtt_ms: float | None = None


# --- power ---
@dataclass
class PowerState:
    """动力/电池/逆变器"""
    soc_x10: int | None = None          # SOC ×10 %
    batt_v_x100: int | None = None      # 电池电压 ×100 V
    batt_i_x100: int | None = None      # 电池电流 ×100 A
    batt_p_w: int | None = None         # 电池功率 W
    inv_state: int | None = None        # 逆变器状态
    inv_fault: bool | None = None       # 逆变器故障
    inv_ac_v_x10: int | None = None     # 逆变器交流电压 ×10 V
    inv_ac_p_w: int | None = None       # 逆变器交流功率 W


# --- hvac ---
@dataclass
class HvacState:
    """空调"""
    mode: int | None = None
    target_temp_x10: int | None = None  # 目标温度 ×10 ℃
    hp_ok: bool | None = None
    lp_ok: bool | None = None
    refrig_ok: bool | None = None
    comp_pwm_act_x10: int | None = None
    evap_pwm_act_x10: int | None = None
    cond_pwm_act_x10: int | None = None
    hvac_fault_code: int | None = None
    ac_enable: bool | None = None
    comp_enable: bool | None = None
    evap_fan_level: int | None = None
    cond_fan_level: int | None = None


# --- webasto ---
@dataclass
class WebastoState:
    """燃油加热器"""
    heater_on: bool | None = None
    water_temp_x10: int | None = None
    heater_state: int | None = None
    web_fault_code: int | None = None
    tc3_active: bool | None = None
    target_water_temp_x10: int | None = None
    hydronic_pump_on: bool | None = None


# --- lighting ---
@dataclass
class LightingState:
    """灯光"""
    main: bool | None = None
    strip: bool | None = None
    night: bool | None = None
    reading: bool | None = None
    strip_brightness: int | None = None


# --- pdu ---
@dataclass
class PduState:
    """PDU"""
    leg_limits: tuple[int, int] | None = None   # (UP, DOWN) 0/1
    awning_limits: tuple[int, int] | None = None  # (IN, OUT) 0/1
    e_stop: bool | None = None
    pdu_fault_code: int | None = None
    pdu_state: int | None = None   # 0=Idle,1=LegExt,2=LegRet,3=AwningExt,4=AwningRet,5=EStop,6=Fault
    ext_light_on: bool | None = None
    fridge_24v_on: bool | None = None
    inv_ac_out_on: bool | None = None
    inv_ac_out_fb: bool | None = None
    leg_motor_i_x100: int | None = None
    awning_motor_i_x100: int | None = None


# --- env ---
@dataclass
class EnvState:
    """环境"""
    cabin_temp_x10: int | None = None   # 舱内温度 ×10 ℃
    cabin_rh_x10: int | None = None     # 舱内湿度 ×10 %
    out_temp_x10: int | None = None
    out_rh_x10: int | None = None


# --- gas ---
@dataclass
class GasState:
    """燃气"""
    co_ppm: int | None = None
    lpg_lel_x10: int | None = None
    gas_alarm: bool | None = None
    gas_fault: bool | None = None
    warmup: bool | None = None


# --- auxfuel ---
@dataclass
class AuxFuelState:
    """辅助燃油"""
    aux_fuel_level_x10: int | None = None


@dataclass
class Snapshot:
    """全量状态快照"""
    # comm: slave 1~9
    comm: dict[int, SlaveComm] = field(default_factory=lambda: {i: SlaveComm() for i in range(1, 10)})
    power: PowerState = field(default_factory=PowerState)
    hvac: HvacState = field(default_factory=HvacState)
    webasto: WebastoState = field(default_factory=WebastoState)
    lighting: LightingState = field(default_factory=LightingState)
    pdu: PduState = field(default_factory=PduState)
    env: EnvState = field(default_factory=EnvState)
    gas: GasState = field(default_factory=GasState)
    auxfuel: AuxFuelState = field(default_factory=AuxFuelState)


def _copy_snapshot(snap: Snapshot) -> Snapshot:
    """安全拷贝 Snapshot，避免 copy.deepcopy 在 dataclass 上的 RecursionError"""
    comm_new = {
        k: SlaveComm(
            online=v.online,
            error_count=v.error_count,
            last_ok_ts=v.last_ok_ts,
            success_count=getattr(v, "success_count", 0),
            fail_count=getattr(v, "fail_count", 0),
            last_rtt_ms=getattr(v, "last_rtt_ms", None),
        )
        for k, v in snap.comm.items()
    }
    return Snapshot(
        comm=comm_new,
        power=PowerState(
            soc_x10=snap.power.soc_x10,
            batt_v_x100=snap.power.batt_v_x100,
            batt_i_x100=snap.power.batt_i_x100,
            batt_p_w=snap.power.batt_p_w,
            inv_state=snap.power.inv_state,
            inv_fault=snap.power.inv_fault,
            inv_ac_v_x10=snap.power.inv_ac_v_x10,
            inv_ac_p_w=snap.power.inv_ac_p_w,
        ),
        hvac=HvacState(
            mode=snap.hvac.mode,
            target_temp_x10=snap.hvac.target_temp_x10,
            hp_ok=snap.hvac.hp_ok,
            lp_ok=snap.hvac.lp_ok,
            refrig_ok=snap.hvac.refrig_ok,
            comp_pwm_act_x10=snap.hvac.comp_pwm_act_x10,
            evap_pwm_act_x10=snap.hvac.evap_pwm_act_x10,
            cond_pwm_act_x10=snap.hvac.cond_pwm_act_x10,
            hvac_fault_code=snap.hvac.hvac_fault_code,
            ac_enable=snap.hvac.ac_enable,
            comp_enable=snap.hvac.comp_enable,
            evap_fan_level=snap.hvac.evap_fan_level,
            cond_fan_level=snap.hvac.cond_fan_level,
        ),
        webasto=WebastoState(
            heater_on=snap.webasto.heater_on,
            water_temp_x10=snap.webasto.water_temp_x10,
            heater_state=snap.webasto.heater_state,
            web_fault_code=snap.webasto.web_fault_code,
            tc3_active=snap.webasto.tc3_active,
            target_water_temp_x10=snap.webasto.target_water_temp_x10,
            hydronic_pump_on=snap.webasto.hydronic_pump_on,
        ),
        lighting=LightingState(
            main=snap.lighting.main,
            strip=snap.lighting.strip,
            night=snap.lighting.night,
            reading=snap.lighting.reading,
            strip_brightness=snap.lighting.strip_brightness,
        ),
        pdu=PduState(
            leg_limits=snap.pdu.leg_limits,
            awning_limits=snap.pdu.awning_limits,
            e_stop=snap.pdu.e_stop,
            pdu_fault_code=snap.pdu.pdu_fault_code,
            pdu_state=snap.pdu.pdu_state,
            ext_light_on=snap.pdu.ext_light_on,
            fridge_24v_on=snap.pdu.fridge_24v_on,
            inv_ac_out_on=snap.pdu.inv_ac_out_on,
            inv_ac_out_fb=snap.pdu.inv_ac_out_fb,
            leg_motor_i_x100=snap.pdu.leg_motor_i_x100,
            awning_motor_i_x100=snap.pdu.awning_motor_i_x100,
        ),
        env=EnvState(
            cabin_temp_x10=snap.env.cabin_temp_x10,
            cabin_rh_x10=snap.env.cabin_rh_x10,
            out_temp_x10=snap.env.out_temp_x10,
            out_rh_x10=snap.env.out_rh_x10,
        ),
        gas=GasState(
            co_ppm=snap.gas.co_ppm,
            lpg_lel_x10=snap.gas.lpg_lel_x10,
            gas_alarm=snap.gas.gas_alarm,
            gas_fault=snap.gas.gas_fault,
            warmup=snap.gas.warmup,
        ),
        auxfuel=AuxFuelState(aux_fuel_level_x10=snap.auxfuel.aux_fuel_level_x10),
    )


def _merge_dataclass(target: Any, source: dict[str, Any]) -> None:
    """将 dict 合并到 dataclass 实例"""
    for k, v in source.items():
        if hasattr(target, k):
            setattr(target, k, v)


def _merge_comm(current: dict[int, SlaveComm], updates: dict[str, Any] | None) -> None:
    if not updates or not isinstance(updates, dict):
        return
    for slave_id, data in updates.items():
        try:
            sid = int(slave_id)
            if 1 <= sid <= 9 and isinstance(data, dict):
                if sid not in current:
                    current[sid] = SlaveComm()
                _merge_dataclass(current[sid], data)
        except (ValueError, TypeError):
            pass


class AppState(QObject):
    """应用状态：线程安全更新，通过信号通知 UI"""

    changed = pyqtSignal(object)        # Snapshot
    alarms_changed = pyqtSignal(object) # list
    comm_changed = pyqtSignal(object)   # dict

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._snapshot = Snapshot()

    def get_snapshot(self) -> Snapshot:
        """返回当前快照的深拷贝"""
        with self._lock:
            return _copy_snapshot(self._snapshot)

    def update(self, **kwargs: Any) -> None:
        """增量更新，合并后 emit changed（不阻塞 UI，锁内只做拷贝与合并）"""
        new_snap: Snapshot | None = None
        comm_updates: dict | None = None
        alarms: list | None = None
        snapshot_modified = False
        keys = list(kwargs.keys())
        logger.debug("AppState.update 等待锁 thread=%s keys=%s", threading.current_thread().name, keys)
        with self._lock:
            logger.debug("AppState.update 获得锁 thread=%s", threading.current_thread().name)
            snap = _copy_snapshot(self._snapshot)

            if "comm" in kwargs:
                comm_updates = kwargs.get("comm")
                _merge_comm(snap.comm, comm_updates)
                del kwargs["comm"]
                snapshot_modified = True

            if "power" in kwargs and isinstance(kwargs["power"], dict):
                _merge_dataclass(snap.power, kwargs["power"])
                del kwargs["power"]
                snapshot_modified = True
            if "hvac" in kwargs and isinstance(kwargs["hvac"], dict):
                _merge_dataclass(snap.hvac, kwargs["hvac"])
                del kwargs["hvac"]
                snapshot_modified = True
            if "webasto" in kwargs and isinstance(kwargs["webasto"], dict):
                _merge_dataclass(snap.webasto, kwargs["webasto"])
                del kwargs["webasto"]
                snapshot_modified = True
            if "lighting" in kwargs and isinstance(kwargs["lighting"], dict):
                _merge_dataclass(snap.lighting, kwargs["lighting"])
                del kwargs["lighting"]
                snapshot_modified = True
            if "pdu" in kwargs and isinstance(kwargs["pdu"], dict):
                _merge_dataclass(snap.pdu, kwargs["pdu"])
                del kwargs["pdu"]
                snapshot_modified = True
            if "env" in kwargs and isinstance(kwargs["env"], dict):
                _merge_dataclass(snap.env, kwargs["env"])
                del kwargs["env"]
                snapshot_modified = True
            if "gas" in kwargs and isinstance(kwargs["gas"], dict):
                _merge_dataclass(snap.gas, kwargs["gas"])
                del kwargs["gas"]
                snapshot_modified = True
            if "auxfuel" in kwargs and isinstance(kwargs["auxfuel"], dict):
                _merge_dataclass(snap.auxfuel, kwargs["auxfuel"])
                del kwargs["auxfuel"]
                snapshot_modified = True

            if "alarms" in kwargs:
                alarms = kwargs.get("alarms")
                del kwargs["alarms"]

            self._snapshot = snap
            if snapshot_modified:
                new_snap = _copy_snapshot(snap)
        logger.debug("AppState.update 释放锁 thread=%s emit_changed=%s", threading.current_thread().name, new_snap is not None)

        # 仅在快照（传感器/Modbus 数据）变化时 emit changed，避免 AlarmController 递归
        if new_snap is not None:
            self.changed.emit(new_snap)
        if comm_updates is not None:
            self.comm_changed.emit(comm_updates)
        if alarms is not None:
            self.alarms_changed.emit(alarms)
