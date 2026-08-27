import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { getVideo } from "../app/api";

function formatCount(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("en-US");
}

export function VideoDetailPage() {
  const { runId, videoId } = useParams();
  const identifiersPresent = Boolean(runId && videoId);
  const video = useQuery({
    queryKey: ["video", runId, videoId],
    queryFn: () => getVideo(runId!, videoId!),
    enabled: identifiersPresent
  });

  if (!identifiersPresent) return <p role="alert">Video identifiers are missing.</p>;
  if (video.isPending) return <p>Loading video…</p>;
  if (video.isError) return <p role="alert">Unable to load video.</p>;

  const latestSnapshot = video.data.snapshots.at(-1);
  const latestViews = latestSnapshot?.views ?? video.data.views;

  return (
    <main>
      <h1>{video.data.caption ?? video.data.video_id}</h1>
      <p>{video.data.creator_nickname ?? video.data.creator_id ?? "Unknown creator"}</p>
      <p>{formatCount(latestViews)} views</p>

      <section>
        <h2>Comments</h2>
        {video.data.comments.length ? (
          <ul>
            {video.data.comments.map((comment) => (
              <li key={comment.comment_id}>{comment.text ?? "—"}</li>
            ))}
          </ul>
        ) : (
          <p>No stored comments.</p>
        )}
      </section>
    </main>
  );
}
