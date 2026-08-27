import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { listBriefs, listFindings, listHypotheses, listInsights, listPatterns } from "../app/api";

export function IntelligencePage({ runId: explicitRunId }: { runId?: string }) {
  const params = useParams();
  const runId = explicitRunId ?? params.runId;
  const findings = useQuery({ queryKey: ["findings", runId], queryFn: () => listFindings(runId!), enabled: Boolean(runId) });
  const patterns = useQuery({ queryKey: ["patterns", runId], queryFn: () => listPatterns(runId!), enabled: Boolean(runId) });
  const insights = useQuery({ queryKey: ["insights", runId], queryFn: () => listInsights(runId!), enabled: Boolean(runId) });
  const hypotheses = useQuery({ queryKey: ["hypotheses", runId], queryFn: () => listHypotheses(runId!), enabled: Boolean(runId) });
  const briefs = useQuery({ queryKey: ["briefs", runId], queryFn: () => listBriefs(runId!), enabled: Boolean(runId) });

  if (!runId) return <p role="alert">Run identifier is missing.</p>;
  if ([findings, patterns, insights, hypotheses, briefs].some((query) => query.isPending)) return <p>Loading intelligence…</p>;
  if ([findings, patterns, insights, hypotheses, briefs].some((query) => query.isError)) return <p role="alert">Unable to load intelligence.</p>;

  return (
    <main>
      <h1>Intelligence</h1>
      <section>
        <h2>Findings</h2>
        <ul>{findings.data!.map((item) => <li key={item.id}>{item.statement}</li>)}</ul>
      </section>
      <section>
        <h2>Patterns</h2>
        <ul>{patterns.data!.map((item) => <li key={item.id}>{item.pattern_field}: {item.pattern_value}{item.lift === null ? "" : ` · lift ${item.lift}`}</li>)}</ul>
      </section>
      <section>
        <h2>Insights</h2>
        <ul>{insights.data!.map((item) => <li key={item.id}>{item.statement}</li>)}</ul>
      </section>
      <section>
        <h2>Hypotheses</h2>
        <ul>{hypotheses.data!.map((item) => <li key={item.id}>{item.statement} · {item.status}</li>)}</ul>
      </section>
      <section>
        <h2>Briefs</h2>
        <ul>{briefs.data!.map((item) => <li key={item.id}>{item.objective}</li>)}</ul>
      </section>
    </main>
  );
}
