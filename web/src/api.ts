export type Dashboard = {
  monitored_cattle: number;
  high_risk_cattle: number;
  open_alerts: number;
  model_status: string;
};

export type AlertRecord = {
  id: string;
  cattle_id: string;
  risk_type: string;
  level: "low" | "medium" | "high";
  reason: string;
  suggestion: string;
  occurred_at: string;
  confidence: number;
  evidence_path?: string | null;
  status: string;
};

export type TrackingResult = {
  video_path: string;
  trajectory_csv: string;
  alert_csv: string;
  health_summary_csv: string;
  health_report_html: string;
  frame_count: number;
  tracked_cattle: number;
  alert_count: number;
};

export type VideoJob = {
  id: string;
  source_path?: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  created_at?: string;
  updated_at?: string;
  result?: TrackingResult | null;
  error?: string | null;
};

export type ImageRecognitionResult = {
  kind: "image";
  status: "completed";
  detection_count: number;
  source_url: string;
  result_url: string;
};

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String(payload.detail)
        : "服务暂时不可用";
    throw new Error(detail);
  }
  return payload as T;
}

export function fetchDashboard(): Promise<Dashboard> {
  return request("/api/dashboard");
}

export function fetchAlerts(): Promise<AlertRecord[]> {
  return request("/api/alerts?status=open");
}

export function recognizeImage(file: File): Promise<ImageRecognitionResult> {
  const body = new FormData();
  body.append("file", file);
  return request("/api/recognition/image", { method: "POST", body });
}

export function createVideoJob(file: File): Promise<VideoJob> {
  const body = new FormData();
  body.append("file", file);
  body.append("class_id", "1");
  body.append("tracker", "bytetrack.yaml");
  return request("/api/jobs/video", { method: "POST", body });
}

export function fetchVideoJob(id: string): Promise<VideoJob> {
  return request(`/api/jobs/${id}`);
}

export function resultMediaUrl(path: string): string {
  return `/media/results/${path.replaceAll("\\", "/")}`;
}
