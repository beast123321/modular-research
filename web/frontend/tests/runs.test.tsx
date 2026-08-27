import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RunsPage } from "../src/pages/RunsPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RunsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("RunsPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify([
            {
              run_id: "run_fixture",
              topic: "fixture topic",
              platform: "douyin",
              depth: "standard",
              status: "completed",
              video_count: 1,
              creator_count: 1,
              comment_count: 1,
              provider_calls_attempted: 2,
              provider_calls_succeeded: 2,
              provider_calls_failed: 0,
              actual_estimated_cost_usd: null,
              artifact_availability: {}
            }
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("renders business-readable run metrics", async () => {
    renderPage();
    expect(await screen.findByText("fixture topic")).toBeInTheDocument();
    expect(screen.getByText(/1 video/i)).toBeInTheDocument();
    expect(screen.getByText(/1 creator/i)).toBeInTheDocument();
    expect(screen.getByText(/1 comment/i)).toBeInTheDocument();
  });
});
