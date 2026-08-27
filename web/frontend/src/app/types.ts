export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

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

export type VideoSummary = {
  video_id: string;
  creator_id: string | null;
  caption: string | null;
  creator_nickname: string | null;
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  engagement_rate: number | null;
  evidence_refs: string[];
};

export type VideoSnapshot = {
  id: number | string;
  views: number | null;
  captured_at: string | null;
};

export type VideoComment = {
  comment_id: string;
  text: string | null;
  like_count: number | null;
};

export type VideoDiscovery = {
  id: number | string;
  source_type: string | null;
  source_rank: number | null;
};

export type VideoDetail = {
  video_id: string;
  creator_id: string | null;
  caption: string | null;
  creator_nickname: string | null;
  views: number | null;
  likes: number | null;
  shares: number | null;
  engagement_rate: number | null;
  evidence_refs: string[];
  snapshots: VideoSnapshot[];
  discoveries: VideoDiscovery[];
  comments: VideoComment[];
};
