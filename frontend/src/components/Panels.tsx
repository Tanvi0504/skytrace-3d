import { AlertTriangle, Download, Play, Upload } from "lucide-react";
import type { EvidenceInfo, MeasurementResult, Object3D, RunStatus, SceneMetadata } from "../types/api";

export function UploadPanel({
  file,
  onFile,
  onCreate,
  onUpload,
  onProcess,
  runId
}: {
  file?: File | null;
  runId?: string | null;
  onFile: (file: File | null) => void;
  onCreate: () => void;
  onUpload: () => void;
  onProcess: () => void;
}) {
  return (
    <section className="toolbarBand">
      <div>
        <strong>SkyTrace</strong>
        <span>{runId ? `Run ${runId}` : "No run selected"}</span>
      </div>
      <label className="fileControl">
        <Upload size={17} />
        <input type="file" accept="video/mp4" onChange={(event) => onFile(event.target.files?.[0] ?? null)} />
        <span>{file ? `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)` : "Choose MP4"}</span>
      </label>
      <button onClick={onCreate}>New Analysis</button>
      <button onClick={onUpload} disabled={!file || !runId}>Upload</button>
      <button onClick={onProcess} disabled={!runId}>
        <Play size={16} /> Process
      </button>
    </section>
  );
}

export function ProgressPanel({ status }: { status?: RunStatus | null }) {
  return (
    <section className="progressStrip" aria-label="Processing progress">
      {(status?.steps ?? []).map((step) => (
        <div key={step.step} className={`step step-${step.status.toLowerCase()}`}>
          <span>Step {step.step}</span>
          <strong>{step.name}</strong>
          <em>{step.status}</em>
          {Object.keys(step.summary).length > 0 && <small>{Object.entries(step.summary).map(([k, v]) => `${k}: ${v}`).join(" | ")}</small>}
          {step.error && <small className="warningText">{step.error}</small>}
        </div>
      ))}
    </section>
  );
}

export function DetailsPanel({
  scene,
  objects,
  selected,
  evidence,
  measurement,
  onSelect,
  onDownload
}: {
  scene?: SceneMetadata | null;
  objects: Object3D[];
  selected?: Object3D | null;
  evidence?: EvidenceInfo | null;
  measurement?: MeasurementResult | null;
  onSelect: (object: Object3D) => void;
  onDownload: () => void;
}) {
  return (
    <section className="detailsGrid">
      <div className="panel">
        <h2>Objects</h2>
        <div className="objectList">
          {objects.length === 0 && <p>No Step 5 object associations available.</p>}
          {objects.map((object) => (
            <button key={object.object_id} onClick={() => onSelect(object)} className={selected?.object_id === object.object_id ? "selected" : ""}>
              <span>{object.class_name} #{object.track_id ?? object.object_id}</span>
              <small>{object.position_status}</small>
            </button>
          ))}
        </div>
      </div>
      <div className="panel">
        <h2>Selected Object</h2>
        {selected ? (
          <dl>
            <dt>Class</dt><dd>{selected.class_name}</dd>
            <dt>Position</dt><dd>{selected.position ? selected.position.map((v) => v.toFixed(2)).join(", ") : "Unavailable"}</dd>
            <dt>Observations</dt><dd>{selected.observation_count ?? "Unknown"}</dd>
            <dt>Evidence</dt><dd>{selected.evidence_level}</dd>
            <dt>Motion</dt><dd>{selected.motion_status === "unknown" ? "Motion status unknown" : selected.motion_status}</dd>
          </dl>
        ) : <p>Select a marker or object row.</p>}
      </div>
      <div className="panel">
        <h2>Evidence</h2>
        {evidence && Object.entries(evidence.levels).map(([level, text]) => <p key={level}><strong>{level}</strong> = {text}</p>)}
        {measurement && <MeasurementBlock measurement={measurement} />}
      </div>
      <div className="panel">
        <h2>Info</h2>
        <dl>
          <dt>Run</dt><dd>{scene?.run_id ?? "None"}</dd>
          <dt>Coordinate system</dt><dd>{scene?.coordinate_system ?? "Not available"}</dd>
          <dt>Scene asset</dt><dd>{scene?.assets[0]?.source ?? "No supported asset"}</dd>
          <dt>Displayed points</dt><dd>{scene?.assets[0]?.point_count ?? "Unknown"}</dd>
        </dl>
        {scene?.warnings.map((warning) => <p className="warningText" key={warning}><AlertTriangle size={14} /> {warning}</p>)}
        <button onClick={onDownload}><Download size={16} /> Export Results</button>
      </div>
    </section>
  );
}

function MeasurementBlock({ measurement }: { measurement: MeasurementResult }) {
  const risky = measurement.evidence_level === "LOW" || measurement.evidence_level === "INSUFFICIENT";
  return (
    <div className={risky ? "measurement warningBox" : "measurement"}>
      <strong>Distance {measurement.distance_3d.toFixed(2)} {measurement.unit}</strong>
      <span>Horizontal: {measurement.horizontal_distance?.toFixed(2) ?? "Unavailable"}</span>
      <span>Vertical: {measurement.vertical_difference?.toFixed(2) ?? "Unavailable"}</span>
      <span>Evidence: {measurement.evidence_level}</span>
      {measurement.warnings.map((warning) => <small key={warning}>{warning}</small>)}
    </div>
  );
}

