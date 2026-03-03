import { useState } from "react";
import { putGlobalConfig, putDatasetsConfig, putScheduleDaily, putDelivery, getDatasetsConfig, runDailyJob } from "../api";

export default function SetupWizardPage() {
  const [step, setStep] = useState(1);
  const [msg, setMsg] = useState("");
  const [running, setRunning] = useState(false);

  const handleWriteConfig = async () => {
    setMsg("");
    try {
      const res = await getDatasetsConfig();
      const items = res?.data?.items || [];
      await putDatasetsConfig(items.map((i) => ({ dataset_code: i.dataset_code, enabled: i.enabled, filters: i.filters })));
      await putScheduleDaily({ enabled: true, time: "00:10" });
      await putDelivery({ mode: "user", target: null, notify_admins: true });
      setMsg("配置已写入");
      setStep(2);
    } catch (e) {
      setMsg("写入失败: " + e.message);
    }
  };

  const handleRunTest = async () => {
    setRunning(true);
    setMsg("");
    const dt = new Date().toISOString().slice(0, 10);
    try {
      const res = await runDailyJob(dt);
      if (res.ok) {
        setMsg(`测试运行成功: run_id=${res.data?.run_id}，enabled_datasets=${(res.data?.enabled_datasets || []).join(", ") || "none"}`);
      } else {
        setMsg("运行失败");
      }
    } catch (e) {
      setMsg("运行失败: " + e.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 600 }}>
      <h2>设置向导</h2>
      <p style={{ color: "#6c757d" }}>写入配置 → 触发一次测试运行</p>
      {msg && <p style={{ color: msg.includes("失败") ? "#dc3545" : "#198754" }}>{msg}</p>}
      {step === 1 && (
        <div>
          <p>步骤 1：将当前配置写入数据库</p>
          <button onClick={handleWriteConfig} style={{ padding: "8px 24px" }}>
            写入配置
          </button>
        </div>
      )}
      {step === 2 && (
        <div>
          <p>步骤 2：触发一次 daily job 测试运行</p>
          <button onClick={handleRunTest} disabled={running} style={{ padding: "8px 24px" }}>
            {running ? "运行中..." : "触发测试运行"}
          </button>
        </div>
      )}
    </div>
  );
}
