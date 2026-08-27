import { Route, Routes } from "react-router-dom";

import { EvidenceDetailPage } from "../pages/EvidenceDetailPage";
import { RunsPage } from "../pages/RunsPage";
import { VideoDetailPage } from "../pages/VideoDetailPage";
import { VideosPage } from "../pages/VideosPage";

export function App() {
  return (
    <Routes>
      <Route path="/runs/:runId/evidence/:evidenceId" element={<EvidenceDetailPage />} />
      <Route path="/runs/:runId/videos/:videoId" element={<VideoDetailPage />} />
      <Route path="/runs/:runId/videos" element={<VideosPage />} />
      <Route path="*" element={<RunsPage />} />
    </Routes>
  );
}
