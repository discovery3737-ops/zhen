import { Routes, Route, Link } from "react-router-dom";
import RunsPage from "./pages/RunsPage";
import AuthCenterPage from "./pages/AuthCenterPage";

export default function App() {
  return (
    <>
      <nav style={{ padding: "12px 24px", background: "#f8f9fa", borderBottom: "1px solid #dee2e6" }}>
        <Link to="/" style={{ marginRight: 16 }}>运行中心</Link>
        <Link to="/auth">授权中心</Link>
      </nav>
      <Routes>
        <Route path="/" element={<RunsPage />} />
        <Route path="/auth" element={<AuthCenterPage />} />
      </Routes>
    </>
  );
}
