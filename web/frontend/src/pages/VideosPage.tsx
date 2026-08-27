import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { listVideos } from "../app/api";

function formatCount(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("en-US");
}

export function VideosPage({ runId: explicitRunId }: { runId?: string }) {
  const params = useParams();
  const runId = explicitRunId ?? params.runId;
  const videos = useQuery({
    queryKey: ["videos", runId],
    queryFn: () => listVideos(runId!),
    enabled: Boolean(runId)
  });

  if (!runId) return <p role="alert">Run identifier is missing.</p>;
  if (videos.isPending) return <p>Loading videos…</p>;
  if (videos.isError) return <p role="alert">Unable to load videos.</p>;
  if (!videos.data.items.length) return <p>No videos available.</p>;

  return (
    <main>
      <h1>Videos</h1>
      <ul>
        {videos.data.items.map((video) => (
          <li key={video.video_id}>
            <article>
              <h2>
                <Link to={`/runs/${encodeURIComponent(runId)}/videos/${encodeURIComponent(video.video_id)}`}>
                  {video.caption ?? video.video_id}
                </Link>
              </h2>
              <p>{video.creator_nickname ?? video.creator_id ?? "Unknown creator"}</p>
              <p>{formatCount(video.views)} views</p>
            </article>
          </li>
        ))}
      </ul>
    </main>
  );
}
