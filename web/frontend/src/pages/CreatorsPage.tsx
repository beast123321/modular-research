import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { listCreators } from "../app/api";

function formatCount(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("en-US");
}

function videoLabel(value: number | null): string {
  if (value === null) return "— videos";
  return `${value.toLocaleString("en-US")} video${value === 1 ? "" : "s"}`;
}

export function CreatorsPage({ runId: explicitRunId }: { runId?: string }) {
  const params = useParams();
  const runId = explicitRunId ?? params.runId;
  const creators = useQuery({
    queryKey: ["creators", runId],
    queryFn: () => listCreators(runId!),
    enabled: Boolean(runId)
  });

  if (!runId) return <p role="alert">Run identifier is missing.</p>;
  if (creators.isPending) return <p>Loading creators…</p>;
  if (creators.isError) return <p role="alert">Unable to load creators.</p>;
  if (!creators.data.items.length) return <p>No creators available.</p>;

  return (
    <main>
      <h1>Creators</h1>
      <ul>
        {creators.data.items.map((creator) => (
          <li key={creator.creator_id}>
            <article>
              <h2>
                <Link to={`/runs/${encodeURIComponent(runId)}/creators/${encodeURIComponent(creator.creator_id)}`}>
                  {creator.nickname ?? creator.creator_id}
                </Link>
              </h2>
              <p>{formatCount(creator.followers)} followers</p>
              <p>{videoLabel(creator.run_video_count)}</p>
            </article>
          </li>
        ))}
      </ul>
    </main>
  );
}
