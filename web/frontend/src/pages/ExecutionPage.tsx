import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { getExecution } from "../app/api";
import type { StageState } from "../app/types";

function formatNullable(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("en-US");
}

function formatCost(value: number | null): string {
  return value === null ? "—" : `$${value.toFixed(3)}`;
}

function StageRow({ stage }: { stage: StageState }) {
  return (
    <li>
      <article>
        <h2>{stage.name}</h2>
        <p>Status: {stage.status}</p>
        <p>Status basis: {stage.status_basis}</p>
        <p>
          Calls: {formatNullable(stage.calls_attempted)} attempted · {formatNullable(stage.calls_succeeded)} succeeded · {formatNullable(stage.calls_failed)} failed
        </p>
      </article>
    </li>
  );
}

export function ExecutionPage({ runId: explicitRunId }: { runId?: string }) {
  const params = useParams();
  const runId = explicitRunId ?? params.runId;
  const execution = useQuery({
    queryKey: ["execution", runId],
    queryFn: () => getExecution(runId!),
    enabled: Boolean(runId)
  });

  if (!runId) return <p role="alert">Run identifier is missing.</p>;
  if (execution.isPending) return <p>Loading execution…</p>;
  if (execution.isError) return <p role="alert">Unable to load execution.</p>;

  const data = execution.data;
  return (
    <main>
      <h1>Execution</h1>
      <section>
        <h2>Plan vs actual</h2>
        <p>Expected requests: {formatNullable(data.expected_requests)} · Maximum requests: {formatNullable(data.max_requests)}</p>
        <p>Expected cost: {formatCost(data.expected_cost_usd)} · Maximum cost: {formatCost(data.max_cost_usd)}</p>
        <p>{formatNullable(data.calls_attempted)} attempted · {formatNullable(data.calls_succeeded)} succeeded · {formatNullable(data.calls_failed)} failed</p>
        <p>Actual estimated cost: {formatCost(data.actual_estimated_cost_usd)}</p>
      </section>
      <section>
        <h2>Stages</h2>
        {data.stages.length ? <ul>{data.stages.map((stage) => <StageRow key={stage.name} stage={stage} />)}</ul> : <p>No execution stages available.</p>}
      </section>
    </main>
  );
}
