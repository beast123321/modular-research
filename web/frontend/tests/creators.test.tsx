import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CreatorsPage } from "../src/pages/CreatorsPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/runs/run_fixture/creators"]}>
        <CreatorsPage runId="run_fixture" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("CreatorsPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            items: [
              {
                creator_id: "creator-1",
                nickname: "Fixture Creator",
                unique_id: "fixturecreator",
                followers: 1234,
                baseline_views: 800,
                run_video_count: 1,
                evidence_refs: ["run_fixture:raw:0001"]
              }
            ],
            page: 1,
            page_size: 50,
            total: 1
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("renders stored creator scale and run coverage", async () => {
    renderPage();
    expect(await screen.findByText("Fixture Creator")).toBeInTheDocument();
    expect(screen.getByText(/1,234 followers/i)).toBeInTheDocument();
    expect(screen.getByText(/1 video/i)).toBeInTheDocument();
  });
});
