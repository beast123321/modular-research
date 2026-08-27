import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VideosPage } from "../src/pages/VideosPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/runs/run_fixture/videos"]}>
        <VideosPage runId="run_fixture" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("VideosPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            items: [
              {
                video_id: "video-1",
                creator_id: "creator-1",
                caption: "Fixture Video",
                creator_nickname: "Fixture Creator",
                views: 1000,
                likes: 100,
                comments: 10,
                shares: 5,
                engagement_rate: 0.115,
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

  it("renders evidence-backed video discovery metrics", async () => {
    renderPage();
    expect(await screen.findByText("Fixture Video")).toBeInTheDocument();
    expect(screen.getByText("Fixture Creator")).toBeInTheDocument();
    expect(screen.getByText(/1,000 views/i)).toBeInTheDocument();
  });
});
