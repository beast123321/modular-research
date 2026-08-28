import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { getReport } from "../app/api";

export function ReportPage({ runId: explicitRunId }: { runId?: string }) {
  const params = useParams();
  const runId = explicitRunId ?? params.runId;
  const report = useQuery({
    queryKey: ["report", runId],
    queryFn: () => getReport(runId!),
    enabled: Boolean(runId)
  });

  if (!runId) return <p role="alert">Run identifier is missing.</p>;
  if (report.isPending) return <p>Loading report…</p>;
  if (report.isError) return <p role="alert">Unable to load report.</p>;

  if (!report.data.persisted_final_report || !report.data.markdown) {
    return (
      <main>
        <h1>Report</h1>
        <p>{report.data.notice ?? "Final report not persisted for this run"}</p>
        {report.data.available_structured_artifacts?.length ? (
          <p>Available structured artifacts: {report.data.available_structured_artifacts.join(", ")}</p>
        ) : null}
      </main>
    );
  }

  return (
    <main>
      <h1>Report</h1>
      <p>{report.data.artifact}</p>
      <pre>{report.data.markdown}</pre>
    </main>
  );
}
