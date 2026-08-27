export type RunSummary = {
  run_id: string;
  topic: string | null;
  platform: string | null;
  depth: string | null;
  status: string | null;
  video_count: number | null;
  creator_count: number | null;
  comment_count: number | null;
  provider_calls_attempted: number | null;
  provider_calls_succeeded: number | null;
  provider_calls_failed: number | null;
  actual_estimated_cost_usd: number | null;
  artifact_availability: Record<string, unknown>;
};

export type NormalizedEntity = {
  type: string;
  id: string;
};

export type EvidenceDetail = {
  id: string;
  run_id: string;
  endpoint: string | null;
  method: string | null;
  source_type: string | null;
  source_key: string | null;
  fetched_at: string | null;
  request: unknown;
  response: unknown;
  normalized_entities: NormalizedEntity[];
};

export type LineageEdge = {
  source_type: string;
  source_id: string;
  target_type: string;
  target_id: string;
  relation: string;
};

export type LineageGraph = {
  root_id: string;
  edges: LineageEdge[];
};
