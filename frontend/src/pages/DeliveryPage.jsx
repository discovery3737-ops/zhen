import { useState, useEffect } from "react";
import { getDelivery, putDelivery } from "../api";

export default function DeliveryPage() {
  const [mode, setMode] = useState("user");
  const [target, setTarget] = useState("");
  const [notifyAdmins, setNotifyAdmins] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const res = await getDelivery();
      if (res.ok && res.data) {
        setMode(res.data.mode || "user");
        setTarget(res.data.target || "");
        setNotifyAdmins(res.data.notify_admins ?? true);
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
      await putDelivery({ mode, target: target || null, notify_admins: notifyAdmins });
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
      <h2>发送配置</h2>
      <p style={{ color: "#6c757d" }}>配置发送对象与管理员告警（暂不真实发送，仅保存配置）</p>
      {msg && <p style={{ color: msg.includes("失败") ? "#dc3545" : "#198754" }}>{msg}</p>}
      <div style={{ marginBottom: 16 }}>
        <label>模式 </label>
        <select value={mode} onChange={(e) => setMode(e.target.value)} style={{ padding: "6px 10px" }}>
          <option value="user">user</option>
          <option value="group">group</option>
        </select>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label>目标 </label>
        <input
          type="text"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="user/group id"
          style={{ padding: "6px 10px", width: 200 }}
        />
      </div>
      <div style={{ marginBottom: 16 }}>
        <label>
          <input type="checkbox" checked={notifyAdmins} onChange={(e) => setNotifyAdmins(e.target.checked)} />
          通知管理员
        </label>
      </div>
      <button onClick={save} disabled={saving} style={{ padding: "8px 24px" }}>
        {saving ? "保存中..." : "保存"}
      </button>
    </div>
  );
}
