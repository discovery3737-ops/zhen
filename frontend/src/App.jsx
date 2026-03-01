import { Routes, Route } from "react-router-dom";
import RunsPage from "./pages/RunsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RunsPage />} />
    </Routes>
  );
}
