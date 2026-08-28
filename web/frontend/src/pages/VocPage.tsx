import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { getVoc } from "../app/api";

function formatShare(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

export function VocPage({ runId: explicitRunId }: { runId?: string }) {
  const params = useParams();
  const runId = explicitRunId ?? params.runId;
  const voc = useQuery({
    queryKey: ["voc", runId],
    queryFn: () => getVoc(runId!),
    enabled: Boolean(runId)
  });

  if (!runId) return <p role="alert">Run identifier is missing.</p>;
  if (voc.isPending) return <p>Loading VOC…</p>;
  if (voc.isError) return <p role="alert">Unable to load VOC.</p>;
  if (!voc.data.labels.length) return <p>No VOC labels available.</p>;

  return (
    <main>
      <h1>Voice of Customer</h1>
      <p>{voc.data.denominator.toLocaleString("en-US")} comments analyzed</p>
      <ul>
        {voc.data.labels.map((item) => (
          <li key={item.label}>
            <article>
              <h2>{item.label}</h2>
              <p>
                {item.count.toLocaleString("en-US")} of {voc.data.denominator.toLocaleString("en-US")} comments
              </p>
              <p>{formatShare(item.share)}</p>
            </article>
          </li>
        ))}
      </ul>
    </main>
  );
}
