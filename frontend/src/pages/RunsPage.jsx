import { useState, useEffect } from "react";
import { getRuns, downloadReport } from "../api";

const MOCK_RUNS = [
  {
    run_id: "run-mock-001",
    dt: "2025-02-28",
    status: "success",
    started_at: "2025-02-28T10:00:00Z",
    finished_at: "2025-02-28T10:05:00Z",
    message: "Mock: Daily job completed",
  },
];

export default function RunsPage() {
  const [runs, setRuns] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [useMock, setUseMock] = useState(false);
  const [downloadError, setDownloadError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getRuns(page, pageSize)
      .then((res) => {
        if (cancelled) return;
        if (res.ok && res.data) {
          const d = res.data;
          setRuns(d.items || []);
          setTotal(d.total ?? 0);
          setUseMock(false);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setRuns(MOCK_RUNS);
        setTotal(1);
        setUseMock(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [page, pageSize]);

  const handleDownloadReport = async (dt) => {
    setDownloadError(null);
    try {
      await downloadReport(dt);
    } catch (err) {
      setDownloadError(err.message);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <h1>运行中心</h1>
      {useMock && (
        <p style={{ color: "#856404", background: "#fff3cd", padding: 12, borderRadius: 4 }}>
          后端不可用，已 fallback 到 mock 数据
        </p>
      )}
      {error && <p style={{ color: "#dc3545" }}>{error}</p>}
      {downloadError && <p style={{ color: "#dc3545" }}>下载失败: {downloadError}</p>}
      {loading ? (
        <p>加载中...</p>
      ) : (
        <>
          <table style={{ width: "100%", borderCollapse: "collapse", background: "#fff", borderRadius: 8, overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.1)" }}>
            <thead>
              <tr style={{ background: "#f8f9fa" }}>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #dee2e6" }}>run_id</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #dee2e6" }}>dt</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #dee2e6" }}>status</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #dee2e6" }}>started_at</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #dee2e6" }}>message</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "1px solid #dee2e6" }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id} style={{ borderBottom: "1px solid #eee" }}>
                  <td style={{ padding: 12 }}>{r.run_id}</td>
                  <td style={{ padding: 12 }}>{r.dt}</td>
                  <td style={{ padding: 12 }}>{r.status}</td>
                  <td style={{ padding: 12 }}>{r.started_at ? new Date(r.started_at).toLocaleString() : "-"}</td>
                  <td style={{ padding: 12 }}>{r.message || "-"}</td>
                  <td style={{ padding: 12 }}>
                    <button
                      onClick={() => handleDownloadReport(r.dt)}
                      style={{ padding: "6px 12px", cursor: "pointer", borderRadius: 4, border: "1px solid #0d6efd", background: "#0d6efd", color: "#fff" }}
                    >
                      下载报表
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ marginTop: 12, color: "#6c757d" }}>
            共 {total} 条 | 第 {page} 页
          </p>
          {page > 1 && (
            <button onClick={() => setPage((p) => p - 1)} style={{ marginRight: 8 }}>
              上一页
            </button>
          )}
          {page * pageSize < total && (
            <button onClick={() => setPage((p) => p + 1)}>下一页</button>
          )}
        </>
      )}
    </div>
  );
}
