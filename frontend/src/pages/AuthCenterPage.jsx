import { useState, useEffect, useCallback } from "react";
import { authSessionStart, authSessionFinish, authCredentialStatus } from "../api";

export default function AuthCenterPage() {
  const [session, setSession] = useState(null);
  const [credential, setCredential] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchCredentialStatus = useCallback(async () => {
    try {
      const res = await authCredentialStatus();
      if (res.ok && res.data) setCredential(res.data);
    } catch (e) {
      console.warn("credential status:", e);
    }
  }, []);

  useEffect(() => {
    fetchCredentialStatus();
    const t = setInterval(fetchCredentialStatus, 10000);
    return () => clearInterval(t);
  }, [fetchCredentialStatus]);

  const handleStart = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await authSessionStart();
      if (res.ok && res.data) {
        setSession(res.data);
      } else {
        setError("创建会话失败");
      }
    } catch (e) {
      setError(e.message || "创建会话失败");
    } finally {
      setLoading(false);
    }
  };

  const handleFinish = async () => {
    if (!session?.session_id) return;
    setError(null);
    setLoading(true);
    try {
      const res = await authSessionFinish(session.session_id, session.token);
      if (res.ok) {
        setSession(null);
        await fetchCredentialStatus();
      } else {
        setError(res.message || "完成授权失败");
      }
    } catch (e) {
      setError(e.message || "完成授权失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1000, margin: "0 auto" }}>
      <h1>授权中心</h1>

      <div style={{ marginBottom: 16, padding: 12, background: "#f8f9fa", borderRadius: 8 }}>
        <strong>凭证状态：</strong>
        {credential ? (
          <span style={{ color: credential.status === "ACTIVE" ? "#198754" : "#6c757d" }}>
            {credential.status}
            {credential.last_check && ` (最后校验: ${new Date(credential.last_check).toLocaleString()})`}
            {credential.message && ` - ${credential.message}`}
          </span>
        ) : (
          <span>加载中...</span>
        )}
      </div>

      {error && (
        <div style={{ color: "#dc3545", marginBottom: 16, padding: 12, background: "#fff5f5", borderRadius: 8 }}>
          {error}
        </div>
      )}

      <div style={{ marginBottom: 16 }}>
        <button
          onClick={handleStart}
          disabled={loading || !!session}
          style={{ padding: "8px 16px", marginRight: 8, cursor: loading || session ? "not-allowed" : "pointer", borderRadius: 4 }}
        >
          创建授权会话
        </button>
        {session && (
          <button
            onClick={handleFinish}
            disabled={loading}
            style={{ padding: "8px 16px", cursor: loading ? "not-allowed" : "pointer", borderRadius: 4, background: "#0d6efd", color: "#fff", border: "none" }}
          >
            完成授权
          </button>
        )}
      </div>

      {session?.novnc_url && (
        <div style={{ border: "1px solid #dee2e6", borderRadius: 8, overflow: "hidden" }}>
          <p style={{ padding: 8, margin: 0, background: "#f8f9fa" }}>
            noVNC 会话（有效期至 {session.expires_at ? new Date(session.expires_at).toLocaleString() : "-"}）
          </p>
          <iframe
            src={session.novnc_url}
            title="noVNC"
            style={{ width: "100%", height: 600, border: "none" }}
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
          />
        </div>
      )}
    </div>
  );
}
