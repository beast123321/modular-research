import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VocPage } from "../src/pages/VocPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/runs/run_fixture/voc"]}>
        <VocPage runId="run_fixture" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("VocPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            denominator: 20,
            labels: [
              { label: "purchase_intent", count: 5, share: 0.25 },
              { label: "pain_point", count: 3, share: 0.15 }
            ]
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("renders backend-classified VOC counts and shares without recomputing them", async () => {
    renderPage();
    expect(await screen.findByText("purchase_intent")).toBeInTheDocument();
    expect(screen.getByText(/5 of 20 comments/i)).toBeInTheDocument();
    expect(screen.getByText(/25%/i)).toBeInTheDocument();
    expect(screen.getByText("pain_point")).toBeInTheDocument();
  });
});
