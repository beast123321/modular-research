import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CreatorDetailPage } from "../src/pages/CreatorDetailPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/runs/run_fixture/creators/creator-1"]}>
        <Routes>
          <Route path="/runs/:runId/creators/:creatorId" element={<CreatorDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("CreatorDetailPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            creator_id: "creator-1",
            nickname: "Fixture Creator",
            unique_id: "fixturecreator",
            followers: 1234,
            baseline_views: 800,
            run_video_count: 1,
            evidence_refs: ["run_fixture:raw:0001"],
            videos: [
              {
                video_id: "video-1",
                caption: "Fixture Video",
                views: 1500,
                likes: 150,
                shares: 8
              }
            ]
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("shows the stored creator profile and linked run videos", async () => {
    renderPage();
    expect(await screen.findByText("Fixture Creator")).toBeInTheDocument();
    expect(screen.getByText(/1,234 followers/i)).toBeInTheDocument();
    expect(screen.getByText("Fixture Video")).toBeInTheDocument();
  });
});
