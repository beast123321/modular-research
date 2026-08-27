import type { BriefSummary, CreatorDetail, CreatorSummary, EvidenceDetail, FindingSummary, HypothesisSummary, InsightSummary, LineageGraph, MediaSummary, Page, PatternSummary, ReportSummary, RunSummary, VideoDetail, VideoSummary, VocSummary } from "./types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function listRuns(): Promise<RunSummary[]> {
  return getJson<RunSummary[]>("/api/runs");
}

export function getEvidence(runId: string, evidenceId: string): Promise<EvidenceDetail> {
  return getJson<EvidenceDetail>(
    `/api/runs/${encodeURIComponent(runId)}/evidence/${encodeURIComponent(evidenceId)}`
  );
}

export function getLineage(runId: string, evidenceId: string): Promise<LineageGraph> {
  return getJson<LineageGraph>(
    `/api/runs/${encodeURIComponent(runId)}/lineage/${encodeURIComponent(evidenceId)}`
  );
}

export function listVideos(runId: string): Promise<Page<VideoSummary>> {
  return getJson<Page<VideoSummary>>(`/api/runs/${encodeURIComponent(runId)}/videos`);
}

export function getVideo(runId: string, videoId: string): Promise<VideoDetail> {
  return getJson<VideoDetail>(
    `/api/runs/${encodeURIComponent(runId)}/videos/${encodeURIComponent(videoId)}`
  );
}

export function listCreators(runId: string): Promise<Page<CreatorSummary>> {
  return getJson<Page<CreatorSummary>>(`/api/runs/${encodeURIComponent(runId)}/creators`);
}

export function getCreator(runId: string, creatorId: string): Promise<CreatorDetail> {
  return getJson<CreatorDetail>(
    `/api/runs/${encodeURIComponent(runId)}/creators/${encodeURIComponent(creatorId)}`
  );
}

export function getVoc(runId: string): Promise<VocSummary> {
  return getJson<VocSummary>(`/api/runs/${encodeURIComponent(runId)}/voc`);
}

export function listMedia(runId: string): Promise<MediaSummary[]> {
  return getJson<MediaSummary[]>(`/api/runs/${encodeURIComponent(runId)}/media`);
}

export function listFindings(runId: string): Promise<FindingSummary[]> {
  return getJson<FindingSummary[]>(`/api/runs/${encodeURIComponent(runId)}/findings`);
}

export function listPatterns(runId: string): Promise<PatternSummary[]> {
  return getJson<PatternSummary[]>(`/api/runs/${encodeURIComponent(runId)}/patterns`);
}

export function listInsights(runId: string): Promise<InsightSummary[]> {
  return getJson<InsightSummary[]>(`/api/runs/${encodeURIComponent(runId)}/insights`);
}

export function listHypotheses(runId: string): Promise<HypothesisSummary[]> {
  return getJson<HypothesisSummary[]>(`/api/runs/${encodeURIComponent(runId)}/hypotheses`);
}

export function listBriefs(runId: string): Promise<BriefSummary[]> {
  return getJson<BriefSummary[]>(`/api/runs/${encodeURIComponent(runId)}/briefs`);
}

export function getReport(runId: string): Promise<ReportSummary> {
  return getJson<ReportSummary>(`/api/runs/${encodeURIComponent(runId)}/report`);
}
