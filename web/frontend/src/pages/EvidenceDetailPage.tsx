import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { getEvidence, getLineage } from "../app/api";

export function EvidenceDetailPage() {
  const { runId, evidenceId } = useParams();
  const identifiersPresent = Boolean(runId && evidenceId);

  const evidence = useQuery({
    queryKey: ["evidence", runId, evidenceId],
    queryFn: () => getEvidence(runId!, evidenceId!),
    enabled: identifiersPresent
  });
  const lineage = useQuery({
    queryKey: ["lineage", runId, evidenceId],
    queryFn: () => getLineage(runId!, evidenceId!),
    enabled: identifiersPresent
  });

  if (!identifiersPresent) return <p role="alert">Evidence identifiers are missing.</p>;
  if (evidence.isPending || lineage.isPending) return <p>Loading evidence…</p>;
  if (evidence.isError || lineage.isError) return <p role="alert">Unable to load evidence.</p>;

  return (
    <main>
      <h1>Evidence</h1>
      <dl>
        <dt>Endpoint</dt>
        <dd>{evidence.data.endpoint ?? "—"}</dd>
        <dt>Method</dt>
        <dd>{evidence.data.method ?? "—"}</dd>
        <dt>Source</dt>
        <dd>{evidence.data.source_type ?? "—"}</dd>
      </dl>

      <section>
        <h2>Normalized entities</h2>
        <p>{evidence.data.normalized_entities.length} stored reference(s)</p>
      </section>

      <section>
        <h2>Stored lineage</h2>
        {lineage.data.edges.length ? (
          <ul>
            {lineage.data.edges.map((edge) => (
              <li key={`${edge.target_type}:${edge.target_id}:${edge.relation}`}>
                <span>{edge.target_type}</span>{" "}
                <span>{edge.target_id}</span>{" "}
                <strong>{edge.relation}</strong>
              </li>
            ))}
          </ul>
        ) : (
          <p>No stored lineage edges.</p>
        )}
      </section>

      <section>
        <h2>Sanitized payload</h2>
        <pre>{JSON.stringify({ request: evidence.data.request, response: evidence.data.response }, null, 2)}</pre>
      </section>
    </main>
  );
}
