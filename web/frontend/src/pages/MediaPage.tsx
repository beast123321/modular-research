import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { listMedia } from "../app/api";

function countLabel(value: number, singular: string, plural: string): string {
  return `${value.toLocaleString("en-US")} ${value === 1 ? singular : plural}`;
}

export function MediaPage({ runId: explicitRunId }: { runId?: string }) {
  const params = useParams();
  const runId = explicitRunId ?? params.runId;
  const media = useQuery({
    queryKey: ["media", runId],
    queryFn: () => listMedia(runId!),
    enabled: Boolean(runId)
  });

  if (!runId) return <p role="alert">Run identifier is missing.</p>;
  if (media.isPending) return <p>Loading media…</p>;
  if (media.isError) return <p role="alert">Unable to load media.</p>;
  if (!media.data.length) return <p>No media artifacts available.</p>;

  return (
    <main>
      <h1>Media</h1>
      <ul>
        {media.data.map((item) => (
          <li key={item.video_id}>
            <article>
              <h2>{item.video_id}</h2>
              <p>{countLabel(item.keyframe_count, "keyframe", "keyframes")}</p>
              <p>{countLabel(item.transcript_count, "transcript segment", "transcript segments")}</p>
              <p>{item.creative_analysis_count.toLocaleString("en-US")} creative analysis</p>
            </article>
          </li>
        ))}
      </ul>
    </main>
  );
}
