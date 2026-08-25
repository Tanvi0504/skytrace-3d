import type { EvidenceInfo, MeasurementResult, Object3D, RunStatus, SceneMetadata } from "../types/api";

const API_BASE = import.meta.env.VITE_SKYTRACE_API_BASE ?? "";

export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep the HTTP status text.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listRuns: () => request<{ runs: string[] }>("/runs"),
  createRun: () => request<{ run_id: string; status: RunStatus }>("/runs", { method: "POST" }),
  uploadVideo: (runId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ filename: string; size_bytes: number }>(`/runs/${runId}/upload`, { method: "POST", body });
  },
  startProcessing: (runId: string) =>
    request<RunStatus>(`/runs/${runId}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    }),
  getStatus: (runId: string) => request<RunStatus>(`/runs/${runId}/status`),
  getScene: (runId: string) => request<SceneMetadata>(`/runs/${runId}/scene`),
  getObjects: (runId: string) => request<{ run_id: string; objects: Object3D[] }>(`/runs/${runId}/objects`),
  getEvidence: (runId: string) => request<EvidenceInfo>(`/runs/${runId}/evidence`),
  getResults: (runId: string) => request<{ run_id: string; files: Record<string, string> }>(`/runs/${runId}/results`),
  measure: (runId: string, pointA: number[], pointB: number[]) =>
    request<MeasurementResult>(`/runs/${runId}/measure`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        point_a: { x: pointA[0], y: pointA[1], z: pointA[2] },
        point_b: { x: pointB[0], y: pointB[1], z: pointB[2] },
        unit: "m"
      })
    })
};
