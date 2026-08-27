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
