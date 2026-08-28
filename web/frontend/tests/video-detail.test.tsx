import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VideoDetailPage } from "../src/pages/VideoDetailPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/runs/run_fixture/videos/video-1"]}>
        <Routes>
          <Route path="/runs/:runId/videos/:videoId" element={<VideoDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("VideoDetailPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            video_id: "video-1",
            creator_id: "creator-1",
            caption: "Fixture Video",
            creator_nickname: "Fixture Creator",
            views: 1500,
            likes: 150,
            shares: 8,
            engagement_rate: 0.113,
            evidence_refs: ["run_fixture:raw:0001"],
            snapshots: [
              { id: 1, views: 1000, captured_at: "2026-08-27T00:02:00+00:00" },
              { id: 2, views: 1500, captured_at: "2026-08-27T00:04:00+00:00" }
            ],
            discoveries: [{ id: 1, source_type: "video_search", source_rank: 1 }],
            comments: [{ comment_id: "comment-1", text: "Great desk setup", like_count: 7 }]
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("shows the stored video detail, latest snapshot views, and comments", async () => {
    renderPage();
    expect(await screen.findByText("Fixture Video")).toBeInTheDocument();
    expect(screen.getByText(/1,500 views/i)).toBeInTheDocument();
    expect(screen.getByText("Great desk setup")).toBeInTheDocument();
  });
});
