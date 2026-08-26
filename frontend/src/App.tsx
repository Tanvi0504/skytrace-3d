import { useEffect, useMemo, useState } from "react";
import { Activity, Ruler } from "lucide-react";
import { DetailsPanel, ProgressPanel, UploadPanel } from "./components/Panels";
import { api } from "./services/api";
import type { EvidenceInfo, MeasurementResult, Object3D, RunStatus, SceneMetadata } from "./types/api";
import { SkyTraceViewer } from "./viewer/SkyTraceViewer";
import "./styles/app.css";

type TabKey = "scene" | "evidence" | "measurements" | "detections";

export default function App() {
  const initialRun = window.location.pathname.startsWith("/viewer/") ? window.location.pathname.split("/").pop() : null;
  const [runId, setRunId] = useState<string | null>(initialRun ?? null);
  const [file, setFile] = useState<File | null>(null);
  const [gpsFile, setGpsFile] = useState<File | null>(null);
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [scene, setScene] = useState<SceneMetadata | null>(null);
  const [objects, setObjects] = useState<Object3D[]>([]);
  const [selected, setSelected] = useState<Object3D | null>(null);
  const [evidence, setEvidence] = useState<EvidenceInfo | null>(null);
  const [evidenceMode, setEvidenceMode] = useState(false);
  const [measuring, setMeasuring] = useState(false);
  const [points, setPoints] = useState<number[][]>([]);
  const [measurement, setMeasurement] = useState<MeasurementResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("scene");

  const asset = useMemo(() => scene?.assets[0], [scene]);
  const isReadOnlyDemo = runId === "processed-demo";
  const isProcessing = status?.state.startsWith("RUNNING_") ?? false;

  useEffect(() => {
    if (!runId) return;
    void refresh(runId);
    const timer = window.setInterval(() => void refresh(runId), 3000);
    return () => window.clearInterval(timer);
  }, [runId]);

  async function refresh(id: string) {
    try {
      const [nextStatus, nextScene, objectPayload, nextEvidence] = await Promise.all([
        api.getStatus(id),
        api.getScene(id),
        api.getObjects(id),
        api.getEvidence(id)
      ]);
      setStatus(nextStatus);
      setScene(nextScene);
      setObjects(objectPayload.objects);
      setEvidence(nextEvidence);
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load run.");
    }
  }

  async function createRun() {
    try {
      const response = await api.createRun();
      setRunId(response.run_id);
      setStatus(response.status);
      setScene(null);
      setObjects([]);
      setSelected(null);
      setEvidence(null);
      setMeasurement(null);
      setGpsFile(null);
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create a new analysis.");
    }
  }

  async function upload() {
    if (!runId || !file) return;
    try {
      await api.uploadVideo(runId, file);
      if (gpsFile) await api.uploadGpsMetadata(runId, gpsFile);
      await refresh(runId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not upload the video.");
    }
  }

  async function process() {
    if (!runId) return;
    try {
      await api.startProcessing(runId);
      await refresh(runId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not start processing.");
    }
  }

  async function handlePoint(point: number[]) {
    const next = points.length >= 2 ? [point] : [...points, point];
    setPoints(next);
    if (runId && next.length === 2) {
      try {
        setMeasurement(await api.measure(runId, next[0], next[1]));
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Measurement unavailable.");
      }
    }
  }

  async function downloadResults() {
    if (!runId) return;
    try {
      const results = await api.getResults(runId);
      const blob = new Blob([JSON.stringify(results, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `skytrace-${runId}-results.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not export results.");
    }
  }

  function activateTab(key: TabKey) {
    setActiveTab(key);
    setEvidenceMode(key === "evidence");
    setMeasuring(key === "measurements");
    if (key !== "measurements") setPoints([]);
  }

  return (
    <main>
      <UploadPanel
        file={file}
        gpsFile={gpsFile}
        runId={runId}
        readOnly={isReadOnlyDemo}
        processing={isProcessing}
        status={status}
        onFile={setFile}
        onGpsFile={setGpsFile}
        onCreate={createRun}
        onUpload={upload}
        onProcess={process}
      />
      {runId === "processed-demo" && <div className="demoNotice">PRE-PROCESSED DEMO RESULT - backup view; it was not generated by this browser session.</div>}
      {message && <div className="message">{message}</div>}
      <section className="operationsGrid">
        <ProgressPanel status={status} />
        <section className="viewerBand">
          <div className="tabBar" role="tablist" aria-label="SkyTrace output views">
            {[
              ["scene", "3D Scene"],
              ["evidence", "Evidence Map"],
              ["measurements", "Measurements"],
              ["detections", "Detections"]
            ].map(([key, label]) => (
              <button key={key} className={activeTab === key ? "active" : ""} onClick={() => activateTab(key as TabKey)}>
                {label}
              </button>
            ))}
          </div>
          <div className="viewerActions">
            <button className={evidenceMode ? "active" : ""} onClick={() => setEvidenceMode((value) => !value)}>
              <Activity size={16} /> Evidence
            </button>
            <button className={measuring ? "active" : ""} onClick={() => { setMeasuring((value) => !value); setPoints([]); }}>
              <Ruler size={16} /> Measure
            </button>
          </div>
          <SkyTraceViewer asset={asset} objects={objects} evidence={evidence} evidenceMode={evidenceMode} measuring={measuring} selectedPoints={points} onPoint={handlePoint} onObject={setSelected} />
        </section>
        <DetailsPanel scene={scene} objects={objects} selected={selected} evidence={evidence} measurement={measurement} activeTab={activeTab} onSelect={setSelected} onDownload={downloadResults} />
      </section>
    </main>
  );
}
