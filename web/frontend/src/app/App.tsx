import { Route, Routes } from "react-router-dom";

import { CreatorDetailPage } from "../pages/CreatorDetailPage";
import { CreatorsPage } from "../pages/CreatorsPage";
import { EvidenceDetailPage } from "../pages/EvidenceDetailPage";
import { ExecutionPage } from "../pages/ExecutionPage";
import { IntelligencePage } from "../pages/IntelligencePage";
import { MediaPage } from "../pages/MediaPage";
import { ReportPage } from "../pages/ReportPage";
import { RunsPage } from "../pages/RunsPage";
import { VideoDetailPage } from "../pages/VideoDetailPage";
import { VideosPage } from "../pages/VideosPage";
import { VocPage } from "../pages/VocPage";

export function App() {
  return (
    <Routes>
      <Route path="/runs/:runId/evidence/:evidenceId" element={<EvidenceDetailPage />} />
      <Route path="/runs/:runId/videos/:videoId" element={<VideoDetailPage />} />
      <Route path="/runs/:runId/videos" element={<VideosPage />} />
      <Route path="/runs/:runId/creators/:creatorId" element={<CreatorDetailPage />} />
      <Route path="/runs/:runId/creators" element={<CreatorsPage />} />
      <Route path="/runs/:runId/voc" element={<VocPage />} />
      <Route path="/runs/:runId/media" element={<MediaPage />} />
      <Route path="/runs/:runId/intelligence" element={<IntelligencePage />} />
      <Route path="/runs/:runId/report" element={<ReportPage />} />
      <Route path="/runs/:runId/execution" element={<ExecutionPage />} />
      <Route path="*" element={<RunsPage />} />
    </Routes>
  );
}
