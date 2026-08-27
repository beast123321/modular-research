import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExecutionPage } from "../src/pages/ExecutionPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/runs/run_fixture/execution"]}>
        <ExecutionPage runId="run_fixture" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ExecutionPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            expected_requests: 12,
            max_requests: 20,
            expected_cost_usd: 0.012,
            max_cost_usd: 0.02,
            calls_attempted: 12,
            calls_succeeded: 12,
            calls_failed: 0,
            actual_estimated_cost_usd: 0.012,
            stages: [
              {
                name: "DISCOVERY",
                status: "COMPLETED",
                status_basis: "execution",
                calls_attempted: 4,
                calls_succeeded: 4,
                calls_failed: 0,
                summary: null
              },
              {
                name: "PATTERN_MINING",
                status: "COMPLETED",
                status_basis: "inferred",
                calls_attempted: null,
                calls_succeeded: null,
                calls_failed: null,
                summary: null
              }
            ]
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("renders plan-vs-actual execution with explicit stage status basis", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Execution" })).toBeInTheDocument();
    expect(screen.getByText(/12 attempted/i)).toBeInTheDocument();
    expect(screen.getByText(/Actual estimated cost: \$0\.012/i)).toBeInTheDocument();
    expect(screen.getByText("DISCOVERY")).toBeInTheDocument();
    expect(screen.getByText(/status basis: execution/i)).toBeInTheDocument();
    expect(screen.getByText("PATTERN_MINING")).toBeInTheDocument();
    expect(screen.getByText(/status basis: inferred/i)).toBeInTheDocument();
  });
});
