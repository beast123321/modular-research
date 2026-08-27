import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MediaPage } from "../src/pages/MediaPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/runs/run_fixture/media"]}>
        <MediaPage runId="run_fixture" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("MediaPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify([
            {
              run_id: "run_fixture",
              video_id: "video-1",
              keyframe_count: 3,
              transcript_count: 2,
              creative_analysis_count: 1
            }
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("renders stored media coverage counts for each video", async () => {
    renderPage();
    expect(await screen.findByText("video-1")).toBeInTheDocument();
    expect(screen.getByText(/3 keyframes/i)).toBeInTheDocument();
    expect(screen.getByText(/2 transcript segments/i)).toBeInTheDocument();
    expect(screen.getByText(/1 creative analysis/i)).toBeInTheDocument();
  });
});
