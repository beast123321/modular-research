import { Route, Routes } from "react-router-dom";

import { EvidenceDetailPage } from "../pages/EvidenceDetailPage";
import { RunsPage } from "../pages/RunsPage";

export function App() {
  return (
    <Routes>
      <Route path="/runs/:runId/evidence/:evidenceId" element={<EvidenceDetailPage />} />
      <Route path="*" element={<RunsPage />} />
    </Routes>
  );
}
