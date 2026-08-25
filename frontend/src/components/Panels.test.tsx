import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { DetailsPanel, ProgressPanel } from "./Panels";
import type { EvidenceInfo, Object3D, RunStatus, SceneMetadata } from "../types/api";

const status: RunStatus = {
  run_id: "demo",
  state: "RUNNING_STEP_2",
  created_at: "2026-08-25T00:00:00Z",
  updated_at: "2026-08-25T00:00:01Z",
  steps: [
    { step: 1, name: "Frame extraction", status: "COMPLETED", summary: { selected_frames: 12 }, warnings: [] },
    { step: 2, name: "3D reconstruction", status: "RUNNING", summary: {}, warnings: [] }
  ]
};

const scene: SceneMetadata = {
  run_id: "demo",
  coordinate_system: "local east-north-up metres",
  reconstruction_status: "available",
  georeferencing_status: "available",
  assets: [{ kind: "point_cloud", format: "PLY", url: "/runs/demo/assets/georeferenced/point_cloud_georef.ply", point_count: 3, source: "Step 3 georeferenced PLY", browser_notes: [] }],
  summary: {},
  warnings: ["Low GPS support"]
};

const object: Object3D = {
  object_id: "track_7",
  class_name: "car",
  track_id: 7,
  position_status: "estimated",
  position: [1, 2, 3],
  coordinate_system: "local east-north-up metres",
  detection_confidence: 0.8,
  observation_count: 4,
  is_dynamic_candidate: true,
  motion_status: "unknown",
  evidence_level: "HIGH",
  evidence_score: 0.8,
  warnings: [],
  raw: {}
};

const evidence: EvidenceInfo = {
  run_id: "demo",
  levels: {
    HIGH: "strong supporting evidence",
    MEDIUM: "moderate supporting evidence",
    LOW: "weak supporting evidence",
    INSUFFICIENT: "insufficient evidence for reliable interpretation"
  },
  quality_regions: [],
  warnings: []
};

test("renders processing state", () => {
  render(<ProgressPanel status={status} />);
  expect(screen.getByText("Frame extraction")).toBeInTheDocument();
  expect(screen.getByText("RUNNING")).toBeInTheDocument();
  expect(screen.getByText(/selected_frames: 12/)).toBeInTheDocument();
});

test("renders object metadata, evidence legend, and warnings", () => {
  render(
    <DetailsPanel
      scene={scene}
      objects={[object]}
      selected={object}
      evidence={evidence}
      measurement={{ measurement_id: "m1", distance_3d: 2, horizontal_distance: 1, vertical_difference: 1, unit: "m", measurement_status: "ESTIMATED", evidence_score: 0.2, evidence_level: "LOW", warnings: ["Measurement has low evidence support."] }}
      onSelect={() => undefined}
      onDownload={() => undefined}
    />
  );
  expect(screen.getAllByText(/car #7/i).length).toBeGreaterThan(0);
  expect(screen.getByText("Motion status unknown")).toBeInTheDocument();
  expect(screen.getByText(/strong supporting evidence/)).toBeInTheDocument();
  expect(screen.getByText(/Low GPS support/)).toBeInTheDocument();
  expect(screen.getByText(/Measurement has low evidence support/)).toBeInTheDocument();
});
