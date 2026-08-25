export type StepStatus = "WAITING" | "RUNNING" | "COMPLETED" | "FAILED";
export type RunState =
  | "QUEUED"
  | "RUNNING_STEP_1"
  | "RUNNING_STEP_2"
  | "RUNNING_STEP_3"
  | "RUNNING_STEP_4"
  | "RUNNING_STEP_5"
  | "RUNNING_STEP_6"
  | "COMPLETED"
  | "FAILED";

export type StepProgress = {
  step: number;
  name: string;
  status: StepStatus;
  summary: Record<string, unknown>;
  warnings: string[];
  error?: string | null;
};

export type RunStatus = {
  run_id: string;
  state: RunState;
  created_at: string;
  updated_at: string;
  video_filename?: string | null;
  video_size_bytes?: number | null;
  error?: string | null;
  steps: StepProgress[];
};

export type SceneAsset = {
  kind: "point_cloud" | "mesh" | "unknown";
  format: string;
  url: string;
  point_count?: number | null;
  source: string;
  browser_notes: string[];
};

export type SceneMetadata = {
  run_id: string;
  coordinate_system?: string | null;
  reconstruction_status: string;
  georeferencing_status: string;
  assets: SceneAsset[];
  summary: Record<string, unknown>;
  warnings: string[];
};

export type Object3D = {
  object_id: string;
  class_name: string;
  track_id?: number | null;
  position_status: string;
  position?: number[] | null;
  coordinate_system?: string | null;
  detection_confidence?: number | null;
  observation_count?: number | null;
  is_dynamic_candidate: boolean;
  motion_status: string;
  evidence_level: "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT" | "UNKNOWN";
  evidence_score?: number | null;
  warnings: string[];
  raw: Record<string, unknown>;
};

export type EvidenceInfo = {
  run_id: string;
  levels: Record<string, string>;
  quality_regions: Array<Record<string, unknown>>;
  warnings: string[];
};

export type MeasurementResult = {
  measurement_id: string;
  distance_3d: number;
  horizontal_distance?: number | null;
  vertical_difference?: number | null;
  unit: string;
  measurement_status: string;
  evidence_score: number;
  evidence_level: "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT";
  warnings: string[];
  api_response_time_seconds?: number;
};

