import type { EvidenceDetail, LineageGraph, RunSummary } from "./types";

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
