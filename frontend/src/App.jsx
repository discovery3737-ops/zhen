import { Routes, Route } from "react-router-dom";
import RunsPage from "./pages/RunsPage";
<<<<<<< HEAD

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RunsPage />} />
    </Routes>
=======
import AuthCenterPage from "./pages/AuthCenterPage";
import DataSourcesPage from "./pages/DataSourcesPage";
import SchedulePage from "./pages/SchedulePage";
import DeliveryPage from "./pages/DeliveryPage";
import SetupWizardPage from "./pages/SetupWizardPage";

export default function App() {
  return (
    <>
      <nav style={{ padding: "12px 24px", background: "#f8f9fa", borderBottom: "1px solid #dee2e6" }}>
        <Link to="/" style={{ marginRight: 16 }}>运行中心</Link>
        <Link to="/auth" style={{ marginRight: 16 }}>授权中心</Link>
        <Link to="/datasources" style={{ marginRight: 16 }}>数据源</Link>
        <Link to="/schedule" style={{ marginRight: 16 }}>调度</Link>
        <Link to="/delivery" style={{ marginRight: 16 }}>发送</Link>
        <Link to="/setup">设置向导</Link>
      </nav>
      <Routes>
        <Route path="/" element={<RunsPage />} />
        <Route path="/auth" element={<AuthCenterPage />} />
        <Route path="/datasources" element={<DataSourcesPage />} />
        <Route path="/schedule" element={<SchedulePage />} />
        <Route path="/delivery" element={<DeliveryPage />} />
        <Route path="/setup" element={<SetupWizardPage />} />
      </Routes>
    </>
>>>>>>> edfd4a2 (M2: config in DB + web-configurable settings)
  );
}
