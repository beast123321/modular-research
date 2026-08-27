import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReportPage } from "../src/pages/ReportPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/runs/run_fixture/report"]}>
        <ReportPage runId="run_fixture" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ReportPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            persisted_final_report: true,
            artifact: "final_report.md",
            markdown: "# Fixture report\n\nEvidence-backed conclusion.",
            notice: null
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("renders the persisted report artifact without synthesizing a new report", async () => {
    renderPage();
    expect(await screen.findByText("final_report.md")).toBeInTheDocument();
    expect(screen.getByText(/Fixture report/)).toBeInTheDocument();
    expect(screen.getByText(/Evidence-backed conclusion/)).toBeInTheDocument();
  });
});
