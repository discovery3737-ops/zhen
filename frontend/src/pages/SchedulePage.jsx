import { useState, useEffect } from "react";
import { getScheduleDaily, putScheduleDaily } from "../api";

export default function SchedulePage() {
  const [enabled, setEnabled] = useState(true);
  const [time, setTime] = useState("00:10");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const res = await getScheduleDaily();
      if (res.ok && res.data) {
        setEnabled(res.data.enabled ?? true);
        setTime(res.data.time || "00:10");
      }
    } catch (e) {
      setMsg("加载失败: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    setMsg("");
    try {
      await putScheduleDaily({ enabled, time });
      setMsg("保存成功");
      await load();
    } catch (e) {
      setMsg("保存失败: " + e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div style={{ padding: 24 }}>加载中...</div>;
  return (
    <div style={{ padding: 24, maxWidth: 500 }}>
      <h2>调度配置</h2>
      <p style={{ color: "#6c757d" }}>每天 0 点后运行时间（HH:mm），供 Beat 使用</p>
      {msg && <p style={{ color: msg.includes("失败") ? "#dc3545" : "#198754" }}>{msg}</p>}
      <div style={{ marginBottom: 16 }}>
        <label>
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          启用
        </label>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label>运行时间 </label>
        <input
          type="text"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          placeholder="00:10"
          style={{ padding: "6px 10px", width: 80 }}
        />
        <span style={{ marginLeft: 8, color: "#999" }}>（默认 00:10）</span>
      </div>
      <button onClick={save} disabled={saving} style={{ padding: "8px 24px" }}>
        {saving ? "保存中..." : "保存"}
      </button>
    </div>
  );
}
