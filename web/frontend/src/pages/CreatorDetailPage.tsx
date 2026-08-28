import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getCreator } from "../app/api";

function formatCount(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("en-US");
}

export function CreatorDetailPage() {
  const { runId, creatorId } = useParams();
  const identifiersPresent = Boolean(runId && creatorId);
  const creator = useQuery({
    queryKey: ["creator", runId, creatorId],
    queryFn: () => getCreator(runId!, creatorId!),
    enabled: identifiersPresent
  });

  if (!identifiersPresent) return <p role="alert">Creator identifiers are missing.</p>;
  if (creator.isPending) return <p>Loading creator…</p>;
  if (creator.isError) return <p role="alert">Unable to load creator.</p>;

  return (
    <main>
      <h1>{creator.data.nickname ?? creator.data.creator_id}</h1>
      <p>{formatCount(creator.data.followers)} followers</p>
      <section>
        <h2>Run videos</h2>
        {creator.data.videos.length ? (
          <ul>
            {creator.data.videos.map((video) => (
              <li key={video.video_id}>
                <Link to={`/runs/${encodeURIComponent(runId!)}/videos/${encodeURIComponent(video.video_id)}`}>
                  {video.caption ?? video.video_id}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p>No linked videos in this run.</p>
        )}
      </section>
    </main>
  );
}
