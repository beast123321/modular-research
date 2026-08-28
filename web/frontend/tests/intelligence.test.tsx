import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IntelligencePage } from "../src/pages/IntelligencePage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/runs/run_fixture/intelligence"]}>
        <IntelligencePage runId="run_fixture" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("IntelligencePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        const payload = url.endsWith("/findings")
          ? [{ id: "finding-1", finding_type: "OBSERVATION", category: "hook", statement: "Fast hooks correlate with stronger views", support_count: 4, evidence_refs: ["ev-1"], metrics: {} }]
          : url.endsWith("/patterns")
            ? [{ id: "pattern-1", performance_metric: "views", pattern_field: "hook_type", pattern_value: "question", lift: 1.8, top_support: 5, baseline_support: 3, evidence_refs: ["ev-1"] }]
            : url.endsWith("/insights")
              ? [{ id: "insight-1", statement: "Question hooks deserve a focused creative test", confidence: 0.82, analyzer_name: "fixture", analyzer_mode: "semantic", evidence_refs: ["ev-1"] }]
              : url.endsWith("/hypotheses")
                ? [{ id: "hypothesis-1", statement: "Lead with a question hook", objective: "increase hold rate", status: "PROPOSED", confidence: 0.78, analyzer_name: "fixture", analyzer_mode: "semantic", evidence_refs: ["ev-1"] }]
                : [{ id: "brief-1", hypothesis_id: "hypothesis-1", objective: "increase hold rate", target_audience: "desk workers", confidence: 0.74, analyzer_name: "fixture", analyzer_mode: "semantic", evidence_refs: ["ev-1"], timeline: [] }];
        return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
      })
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("renders persisted findings, patterns, insights, hypotheses, and briefs", async () => {
    renderPage();
    expect(await screen.findByText("Fast hooks correlate with stronger views")).toBeInTheDocument();
    expect(screen.getByText(/hook_type: question/i)).toBeInTheDocument();
    expect(screen.getByText("Question hooks deserve a focused creative test")).toBeInTheDocument();
    expect(screen.getByText("Lead with a question hook")).toBeInTheDocument();
    expect(screen.getByText(/increase hold rate/i)).toBeInTheDocument();
  });
});
