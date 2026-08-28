export type StageState = {
  name: string;
  status: string | null;
  status_basis: string | null;
  calls_attempted: number | null;
  calls_succeeded: number | null;
  calls_failed: number | null;
  summary: string | null;
};

export function StageFlow({ stages }: { stages: StageState[] }) {
  if (!stages.length) return <p>No stage data available.</p>;

  return (
    <ol aria-label="Research stages">
      {stages.map((stage) => (
        <li key={stage.name}>
          <strong>{stage.name}</strong>
          <span> {stage.status ?? "UNKNOWN"}</span>
          {stage.status_basis ? <span> · {stage.status_basis}</span> : null}
          {stage.summary ? <p>{stage.summary}</p> : null}
        </li>
      ))}
    </ol>
  );
}
