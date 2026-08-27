import { Route, Routes } from "react-router-dom";

import { RunsPage } from "../pages/RunsPage";

export function App() {
  return (
    <Routes>
      <Route path="*" element={<RunsPage />} />
    </Routes>
  );
}
