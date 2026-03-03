import { useState, useEffect } from "react";
import { getDatasetsConfig, putDatasetsConfig } from "../api";

export default function DataSourcesPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const res = await getDatasetsConfig();
      if (res.ok && res.data?.items) setItems(res.data.items);
    } catch (e) {
      setMsg("加载失败: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const toggle = (code) => {
    setItems((prev) =>
      prev.map((i) => (i.dataset_code === code ? { ...i, enabled: !i.enabled } : i))
    );
  };

  const save = async () => {
    setSaving(true);
    setMsg("");
    try {
      await putDatasetsConfig(items.map((i) => ({ dataset_code: i.dataset_code, enabled: i.enabled, filters: i.filters })));
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
    <div style={{ padding: 24, maxWidth: 600 }}>
      <h2>数据源配置</h2>
      <p style={{ color: "#6c757d" }}>勾选要采集的数据源，保存后 daily job 仅运行已启用项</p>
      {msg && <p style={{ color: msg.includes("失败") ? "#dc3545" : "#198754" }}>{msg}</p>}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {items.map((i) => (
          <li key={i.dataset_code} style={{ padding: "12px 0", borderBottom: "1px solid #eee", display: "flex", alignItems: "center", gap: 12 }}>
            <input
              type="checkbox"
              checked={!!i.enabled}
              onChange={() => toggle(i.dataset_code)}
            />
            <span>{i.name || i.dataset_code}</span>
            <span style={{ color: "#999", fontSize: 12 }}>({i.dataset_code})</span>
          </li>
        ))}
      </ul>
      <button onClick={save} disabled={saving} style={{ marginTop: 16, padding: "8px 24px" }}>
        {saving ? "保存中..." : "保存"}
      </button>
    </div>
  );
}
