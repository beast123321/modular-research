import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StageFlow } from "../src/components/StageFlow";

describe("StageFlow", () => {
  it("labels inferred stage status in text", () => {
    render(
      <StageFlow
        stages={[
          {
            name: "VOC",
            status: "COMPLETED",
            status_basis: "inferred",
            calls_attempted: null,
            calls_succeeded: null,
            calls_failed: null,
            summary: null
          }
        ]}
      />
    );
    expect(screen.getByText("VOC")).toBeInTheDocument();
    expect(screen.getByText(/inferred/i)).toBeInTheDocument();
  });
});
