import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EvidenceDetailPage } from "../src/pages/EvidenceDetailPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/runs/run_fixture/evidence/run_fixture%3Araw%3A0001"]}>
        <Routes>
          <Route path="/runs/:runId/evidence/:evidenceId" element={<EvidenceDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("EvidenceDetailPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/lineage/")) {
          return new Response(
            JSON.stringify({
              root_id: "run_fixture:raw:0001",
              edges: [
                {
                  source_type: "raw_evidence",
                  source_id: "run_fixture:raw:0001",
                  target_type: "video",
                  target_id: "video-1",
                  relation: "normalized_as"
                }
              ]
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response(
          JSON.stringify({
            id: "run_fixture:raw:0001",
            run_id: "run_fixture",
            endpoint: "/fixture",
            method: "GET",
            source_type: "video_search",
            source_key: "fixture",
            fetched_at: "2026-08-27T00:01:00+00:00",
            request: { Authorization: "***REDACTED***" },
            response: { api_key: "***REDACTED***", ok: true },
            normalized_entities: [{ type: "video", id: "video-1" }]
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      })
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("shows evidence identity and stored lineage without inventing relationships", async () => {
    renderPage();
    expect(await screen.findByText("/fixture")).toBeInTheDocument();
    expect(screen.getByText("video-1")).toBeInTheDocument();
    expect(screen.getByText("normalized_as")).toBeInTheDocument();
  });
});
