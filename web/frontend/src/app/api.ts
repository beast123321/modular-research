import type { CreatorDetail, CreatorSummary, EvidenceDetail, LineageGraph, MediaSummary, Page, RunSummary, VideoDetail, VideoSummary, VocSummary } from "./types";

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
