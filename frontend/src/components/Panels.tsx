import { AlertTriangle, Download, Play, Upload } from "lucide-react";
import type { EvidenceInfo, MeasurementResult, Object3D, RunStatus, SceneMetadata } from "../types/api";

type TabKey = "scene" | "evidence" | "measurements" | "detections";

export function UploadPanel({
  file,
  gpsFile,
  onFile,
  onGpsFile,
  onCreate,
  onUpload,
  onProcess,
  runId,
  readOnly = false,
  processing = false,
  status
}: {
  file?: File | null;
  gpsFile?: File | null;
  runId?: string | null;
  status?: RunStatus | null;
  onFile: (file: File | null) => void;
  onGpsFile?: (file: File | null) => void;
  onCreate: () => void;
  onUpload: () => void;
  onProcess: () => void;
  readOnly?: boolean;
  processing?: boolean;
}) {
  return (
    <section className="topBar">
      <div className="brandBlock">
        <strong>SKYTRACE</strong>
        <span>SIH26158</span>
      </div>
      <div className="missionBlock">
        <span>Mission</span>
        <strong>{runId ?? "NOT INITIALIZED"}</strong>
      </div>
      <div className="missionBlock">
        <span>Drone Video</span>
        <strong>{status?.video_filename ?? file?.name ?? "NOT AVAILABLE"}</strong>
      </div>
      <div className="missionBlock">
        <span>Processing</span>
        <strong>{status?.state ?? "WAITING"}</strong>
      </div>
      <label className="fileControl" title="Upload the drone MP4">
        <Upload size={17} />
        <input type="file" accept="video/mp4" disabled={readOnly || processing} onChange={(event) => onFile(event.target.files?.[0] ?? null)} />
        <span>{file ? `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)` : "MP4"}</span>
      </label>
      <label className="fileControl" title="Optional JSON GPS or flight metadata">
        <Upload size={17} />
        <input type="file" accept="application/json,.json" disabled={readOnly || processing} onChange={(event) => onGpsFile?.(event.target.files?.[0] ?? null)} />
        <span>{gpsFile ? gpsFile.name : "GPS JSON"}</span>
      </label>
      <button onClick={onCreate}>New Analysis</button>
      <button onClick={onUpload} disabled={!file || !runId || readOnly || processing}>Upload</button>
      <button onClick={onProcess} disabled={!runId || readOnly || processing}>
        <Play size={16} /> Process
      </button>
    </section>
  );
}

export function ProgressPanel({ status }: { status?: RunStatus | null }) {
  return (
    <aside className="pipelinePanel" aria-label="Processing progress">
      <h2>Pipeline</h2>
      {(status?.steps ?? []).map((step) => (
        <div key={step.step} className={`step step-${step.status.toLowerCase()}`}>
          <span>{String(step.step).padStart(2, "0")}</span>
          <strong>{step.name}</strong>
          <em>{step.status}</em>
          {Object.keys(step.summary).length > 0 && <small>{Object.entries(step.summary).map(([k, v]) => `${k}: ${formatValue(v)}`).join(" | ")}</small>}
          {step.warnings.map((warning) => <small className="warningText" key={warning}>{warning}</small>)}
          {step.error && <small className="warningText">{step.error}</small>}
        </div>
      ))}
      {!status && <p>No mission initialized.</p>}
    </aside>
  );
}

export function DetailsPanel({
  scene,
  objects,
  selected,
  evidence,
  measurement,
  activeTab = "scene",
  onSelect,
  onDownload
}: {
  scene?: SceneMetadata | null;
  objects: Object3D[];
  selected?: Object3D | null;
  evidence?: EvidenceInfo | null;
  measurement?: MeasurementResult | null;
  activeTab?: TabKey;
  onSelect: (object: Object3D) => void;
  onDownload: () => void;
}) {
  return (
    <aside className="rightPanel">
      {activeTab === "scene" && <SceneBlock scene={scene} onDownload={onDownload} />}
      {activeTab === "evidence" && <EvidenceBlock evidence={evidence} scene={scene} measurement={measurement} />}
      {activeTab === "measurements" && <MeasurementsBlock scene={scene} measurement={measurement} />}
      {activeTab === "detections" && <DetectionsBlock objects={objects} selected={selected} onSelect={onSelect} />}
    </aside>
  );
}

function SceneBlock({ scene, onDownload }: { scene?: SceneMetadata | null; onDownload: () => void }) {
  const video = scene?.summary.video as Record<string, unknown> | undefined;
  const reconstruction = scene?.summary.reconstruction as Record<string, unknown> | undefined;
  const georef = scene?.summary.georeferencing as Record<string, unknown> | undefined;
  return (
    <div className="panelStack">
      <h2>3D Scene</h2>
      <Metric label="Input video" value={video?.filename ?? video?.video_path ?? "NOT AVAILABLE"} />
      <Metric label="Duration" value={seconds(video?.duration_seconds)} />
      <Metric label="Resolution" value={resolution(video)} />
      <Metric label="FPS" value={video?.fps ?? "NOT AVAILABLE"} />
      <Metric label="Reconstruction" value={scene?.reconstruction_status ?? "NOT AVAILABLE"} />
      <Metric label="Registered frames" value={reconstruction?.registered_image_count ?? reconstruction?.registered_images ?? "NOT AVAILABLE"} />
      <Metric label="3D points" value={scene?.assets[0]?.point_count ?? reconstruction?.sparse_point_count ?? "NOT AVAILABLE"} />
      <Metric label="Georeferencing" value={scene?.georeferencing_status ?? "NOT AVAILABLE"} />
      <Metric label="GPS observations" value={georef?.gps_observation_count ?? "NOT AVAILABLE"} />
      <Metric label="Coordinate system" value={scene?.coordinate_system ?? "NOT AVAILABLE"} />
      {scene?.warnings.map((warning) => <p className="warningText" key={warning}><AlertTriangle size={14} /> {warning}</p>)}
      <button onClick={onDownload}><Download size={16} /> Export Results</button>
    </div>
  );
}

function EvidenceBlock({ evidence, scene, measurement }: { evidence?: EvidenceInfo | null; scene?: SceneMetadata | null; measurement?: MeasurementResult | null }) {
  const analysis = scene?.summary.analysis as Record<string, unknown> | undefined;
  return (
    <div className="panelStack">
      <h2>Evidence Map</h2>
      <Metric label="Quality regions" value={evidence?.quality_regions.length ?? analysis?.quality_region_count ?? "NOT AVAILABLE"} />
      <Metric label="Evidence basis" value={analysis?.methodology ?? "Computed only when Step 6 has georeferenced geometry."} />
      {evidence && Object.entries(evidence.levels).map(([level, text]) => <p key={level}><strong>{level}</strong> = {text}</p>)}
      {evidence?.warnings.map((warning) => <p className="warningText" key={warning}><AlertTriangle size={14} /> {warning}</p>)}
      {measurement && <MeasurementBlock measurement={measurement} />}
    </div>
  );
}

function MeasurementsBlock({ scene, measurement }: { scene?: SceneMetadata | null; measurement?: MeasurementResult | null }) {
  const hasMetricScene = scene?.georeferencing_status === "available";
  return (
    <div className="panelStack">
      <h2>Measurements</h2>
      <Metric label="Metric scale" value={hasMetricScene ? "AVAILABLE" : "NOT AVAILABLE"} />
      <Metric label="Absolute position error" value="NOT AVAILABLE" detail="No independent ground-truth/reference dataset was supplied." />
      <Metric label="Measurement MAE" value="NOT AVAILABLE" detail="No surveyed reference measurements were supplied." />
      <Metric label="Surface completeness" value="NOT AVAILABLE" detail="No reference geometry was supplied." />
      {measurement ? <MeasurementBlock measurement={measurement} /> : <p>Measurement result appears only after selecting two reconstructed scene points.</p>}
    </div>
  );
}

function DetectionsBlock({ objects, selected, onSelect }: { objects: Object3D[]; selected?: Object3D | null; onSelect: (object: Object3D) => void }) {
  const counts = objects.reduce<Record<string, number>>((accumulator, object) => {
    accumulator[object.class_name] = (accumulator[object.class_name] ?? 0) + 1;
    return accumulator;
  }, {});
  return (
    <div className="panelStack">
      <h2>Detections - {objects.length}</h2>
      {Object.entries(counts).map(([className, count]) => <Metric key={className} label={className} value={count} />)}
      <div className="objectList">
        {objects.length === 0 && <p>No Step 5 object associations available.</p>}
        {objects.map((object) => (
          <button key={object.object_id} onClick={() => onSelect(object)} className={selected?.object_id === object.object_id ? "selected" : ""}>
            <span>{object.class_name} #{object.track_id ?? object.object_id}</span>
            <small>{object.position_status}</small>
          </button>
        ))}
      </div>
      <SelectedObject selected={selected} />
    </div>
  );
}

function SelectedObject({ selected }: { selected?: Object3D | null }) {
  if (!selected) return <p>Select a marker or object row.</p>;
  return (
    <dl>
      <dt>Class</dt><dd>{selected.class_name}</dd>
      <dt>Confidence</dt><dd>{percent(selected.detection_confidence)}</dd>
      <dt>Position</dt><dd>{selected.position ? selected.position.map((v) => v.toFixed(2)).join(", ") : "UNAVAILABLE"}</dd>
      <dt>Frames</dt><dd>{frameRange(selected)}</dd>
      <dt>Observations</dt><dd>{selected.observation_count ?? "NOT AVAILABLE"}</dd>
      <dt>Evidence</dt><dd>{selected.evidence_level}</dd>
      <dt>Motion</dt><dd>{selected.motion_status === "unknown" ? "Motion status unknown" : selected.motion_status}</dd>
      {selected.warnings.length > 0 && <><dt>Warnings</dt><dd>{selected.warnings.join(" | ")}</dd></>}
    </dl>
  );
}

function MeasurementBlock({ measurement }: { measurement: MeasurementResult }) {
  const risky = measurement.evidence_level === "LOW" || measurement.evidence_level === "INSUFFICIENT";
  return (
    <div className={risky ? "measurement warningBox" : "measurement"}>
      <strong>Distance {measurement.distance_3d.toFixed(2)} {measurement.unit}</strong>
      <span>Status: {measurement.measurement_status}</span>
      <span>Horizontal: {measurement.horizontal_distance?.toFixed(2) ?? "NOT AVAILABLE"}</span>
      <span>Vertical: {measurement.vertical_difference?.toFixed(2) ?? "NOT AVAILABLE"}</span>
      <span>Evidence: {measurement.evidence_level}</span>
      {measurement.warnings.map((warning) => <small key={warning}>{warning}</small>)}
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: unknown; detail?: string }) {
  return (
    <div className="metricRow">
      <span>{label}</span>
      <strong>{formatValue(value)}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "NOT AVAILABLE";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(3);
  if (typeof value === "boolean") return value ? "AVAILABLE" : "NOT AVAILABLE";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function seconds(value: unknown): string {
  return typeof value === "number" ? `${value.toFixed(1)} s` : "NOT AVAILABLE";
}

function resolution(video?: Record<string, unknown>): string {
  const width = video?.width ?? video?.resolution_width;
  const height = video?.height ?? video?.resolution_height;
  return typeof width === "number" && typeof height === "number" ? `${width} x ${height}` : "NOT AVAILABLE";
}

function percent(value?: number | null): string {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "NOT AVAILABLE";
}

function frameRange(object: Object3D): string {
  const first = object.raw.first_frame_index;
  const last = object.raw.last_frame_index;
  if (typeof first === "number" && typeof last === "number") return `${first}-${last}`;
  return "NOT AVAILABLE";
}
