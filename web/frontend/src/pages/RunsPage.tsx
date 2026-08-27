import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listRuns } from "../app/api";

function countLabel(value: number | null, singular: string): string {
  if (value === null) return `— ${singular}s`;
  return `${value} ${singular}${value === 1 ? "" : "s"}`;
}

export function RunsPage() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: listRuns });

  if (runs.isPending) return <p>Loading research runs…</p>;
  if (runs.isError) return <p role="alert">Unable to load research runs.</p>;
  if (!runs.data.length) return <p>No research runs available.</p>;

  return (
    <main>
      <h1>Research runs</h1>
      <ul>
        {runs.data.map((run) => (
          <li key={run.run_id}>
            <article>
              <h2>
                <Link to={`/runs/${encodeURIComponent(run.run_id)}`}>{run.topic ?? run.run_id}</Link>
              </h2>
              <p>{[run.platform, run.depth, run.status].filter(Boolean).join(" · ")}</p>
              <p>
                {countLabel(run.video_count, "video")} · {countLabel(run.creator_count, "creator")} · {countLabel(run.comment_count, "comment")}
              </p>
            </article>
          </li>
        ))}
      </ul>
    </main>
  );
}
