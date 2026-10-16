export type Dashboard = {
  latest_cattle_track_count: number | null;
  latest_cattle_processed_at: string | null;
  high_risk_alerts: number;
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

export type BehaviorSummaryRow = {
  track_id: number;
  behavior_name: string;
  behavior_display_name: string;
  duration_seconds: number;
  eligible_ratio: number;
  uncertain_duration_seconds: number;
  model_version: string;
};

export type TrajectoryAnomaly = {
  track_id: number;
  is_outlier: boolean;
  anomaly_score: number;
  top_contributors?: string[];
};

export type HealthEvidenceProfile = {
  track_id: number;
  risk_score: number;
  risk_level: string;
  observations: {
    type: string;
    label: string;
    time_seconds: number | null;
    confidence: number | null;
    detail: string;
    suggestion: string;
  }[];
};

export type TrackingResult = {
  video_path: string;
  trajectory_csv: string;
  alert_csv: string;
  health_summary_csv: string;
  health_report_html: string;
  frame_count: number;
  tracked_cattle: number;
  species?: "cattle" | "sheep";
  track_ids?: number[];
  health_evidence?: HealthEvidenceProfile[];
  alert_count: number;
  behavior_csv?: string | null;
  behavior_summary_csv?: string | null;
  behavior_model_status?: "ready" | "unavailable" | "failed";
  behavior_model_version?: string | null;
  behavior_model_error?: string | null;
  behavior_summary?: BehaviorSummaryRow[];
  trajectory_anomaly_csv?: string | null;
  trajectory_anomaly_count?: number;
  trajectory_anomaly_status?: "ok" | "skipped" | "failed" | "unavailable";
  trajectory_anomaly_reason?: string | null;
  trajectory_anomalies?: TrajectoryAnomaly[];
  sheep_motion_summary?: {
    track_id: number;
    still_seconds: number;
    moving_seconds: number;
    fast_seconds: number;
    observed_seconds: number;
  }[];
  sheep_motion_events?: {
    track_id: number;
    time_seconds: number;
    label: string;
    detail: string;
  }[];
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

export type InventoryRecheck = {
  id: string; check_id: string; counted_count: number;
  outcome: "resolved" | "shortfall_pending" | "surplus_pending" | "loss_user_recorded";
  movement_records_checked: boolean; field_search_complete: boolean;
  lost_count: number | null; operator_name: string; note: string; created_at: string;
};

export type InventoryCheck = {
  id: string; job_id: string; species: "cattle" | "sheep"; pen_id: string;
  expected_count: number; baseline_source: string; observed_count: number | null;
  coverage: "complete" | "partial" | "unknown"; coverage_note: string;
  operator_name: string; observed_at: string; created_at: string;
  status: "coverage_needed" | "count_needed" | "preliminary_match" |
    "discrepancy_pending" | "verified_match" | "shortfall_pending" |
    "surplus_pending" | "loss_user_recorded";
  difference: number | null; current_count: number | null; video_track_count: number | null;
  lost_count: number | null; verification_status: "user_recorded";
  rechecks: InventoryRecheck[];
};

export type NewInventoryCheck = Pick<InventoryCheck, "job_id" | "pen_id" | "expected_count" |
  "baseline_source" | "observed_count" | "coverage" | "coverage_note" |
  "operator_name" | "observed_at">;

export type NewInventoryRecheck = Pick<InventoryRecheck, "counted_count" | "outcome" |
  "movement_records_checked" | "field_search_complete" | "lost_count" | "operator_name" | "note">;

export type VideoReview = {
  id: string;
  job_id: string;
  species: "cattle" | "sheep";
  issue_type: "missed_detection" | "id_switch" | "false_alert" | "health_concern" | "other";
  track_id: number | null;
  time_seconds: number | null;
  verdict: "confirmed" | "rejected" | "uncertain";
  note: string;
  created_at: string;
};

export type VideoEvent = {
  id: number;
  kind: "alert" | "behavior" | "review" | "correction" | "movement";
  time_seconds: number;
  track_id: number | null;
  label: string;
  detail: string;
};

export type VideoCorrection = {
  id: string;
  job_id: string;
  species: "cattle" | "sheep";
  kind: "missed_detection" | "id_correction" | "behavior_correction";
  frame_index: number;
  time_seconds: number;
  track_id: number | null;
  corrected_track_id: number | null;
  behavior_label: string | null;
  box: { x: number; y: number; width: number; height: number } | null;
  note: string;
  created_at: string;
};

export type DatasetEvaluation = {
  id: string;
  job_id: string;
  dataset_name: string;
  source_url: string;
  dataset_version: string;
  license_name: string;
  split_name: "development" | "validation" | "external_test";
  video_sha256: string;
  annotations_sha256: string;
  metrics: {
    labeled_frames: number;
    ground_truth_boxes: number;
    true_positive: number;
    false_positive: number;
    false_negative: number;
    precision: number;
    recall: number;
    f1: number;
    id_switches: number;
    iou_threshold: number;
  };
  created_at: string;
};

export type NewVideoCorrection = Pick<VideoCorrection, "kind" | "time_seconds" | "track_id" | "corrected_track_id" | "behavior_label" | "box" | "note">;

export type NewVideoReview = Pick<VideoReview, "issue_type" | "track_id" | "time_seconds" | "verdict" | "note">;

export type AnimalLink = {
  job_id: string;
  track_id: number;
  animal_id: string;
  species: "cattle" | "sheep";
  linked_at: string;
};

export type AnimalProfile = {
  animal_id: string;
  species: "cattle" | "sheep";
  visits: (AnimalLink & {
    recorded_at: string;
    health_evidence: HealthEvidenceProfile | null;
    sheep_motion: NonNullable<TrackingResult["sheep_motion_summary"]>[number] | null;
    reviews: VideoReview[];
  })[];
  followups: AnimalFollowup[];
};

export type AnimalFollowup = {
  id: string;
  animal_id: string;
  kind: "field_observation" | "veterinary_diagnosis";
  observed_at: string;
  note: string;
  diagnosis: string | null;
  source_reference: string | null;
  verification_status: "user_recorded";
  created_at: string;
};

export type ImageRecognitionResult = {
  kind: "image";
  status: "completed";
  detection_count: number;
  source_url: string;
  result_url: string;
};

export type CrossDomainVariantMetric = {
  sample_count: number;
  accepted_count?: number;
  coverage: number;
  selective_accuracy?: number | null;
  selective_macro_f1?: number | null;
  selective_risk: number | null;
};

export type CrossDomainExperimentResult = {
  status: "not_run" | "blocked" | "complete";
  dataset_id: string;
  dataset_version: string;
  sample_counts: Partial<Record<"strict" | "extended", number>>;
  model_hash_prefix: string | null;
  quality_policy: "predeclared_heuristic" | "validation_logistic" | null;
  variant_metrics: Partial<
    Record<
      "strict" | "extended",
      Record<
        | "uncalibrated"
        | "calibrated"
        | "calibrated_fixed_rejection"
        | "calibrated_quality_rejection",
        CrossDomainVariantMetric
      >
    >
  >;
  limitations: string[];
  figure_urls: Partial<
    Record<"confusion_matrix" | "risk_coverage" | "stress_curves", string>
  >;
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

export type RecognitionParameters = {
  conf: number;
  iou: number;
  classId: number;
  tracker: "bytetrack.yaml" | "botsort.yaml";
};

export function recognizeImage(
  file: File,
  parameters: RecognitionParameters,
): Promise<ImageRecognitionResult> {
  const body = new FormData();
  body.append("file", file);
  body.append("conf", String(parameters.conf));
  body.append("iou", String(parameters.iou));
  body.append("class_id", String(parameters.classId));
  return request("/api/recognition/image", { method: "POST", body });
}

export function createVideoJob(
  file: File,
  parameters: RecognitionParameters,
): Promise<VideoJob> {
  const body = new FormData();
  body.append("file", file);
  body.append("conf", String(parameters.conf));
  body.append("iou", String(parameters.iou));
  body.append("class_id", String(parameters.classId));
  body.append("tracker", parameters.tracker);
  return request("/api/jobs/video", { method: "POST", body });
}

export function fetchVideoJob(id: string): Promise<VideoJob> {
  return request(`/api/jobs/${id}`);
}

export function fetchVideoJobs(): Promise<VideoJob[]> {
  return request("/api/jobs/video");
}

export function fetchInventoryChecks(): Promise<InventoryCheck[]> {
  return request("/api/inventory-checks");
}

export type InventoryPage = {
  items: InventoryCheck[];
  total: number;
  limit: number;
  offset: number;
};

export function fetchInventoryPage(options: {
  limit: number; offset: number; penId: string; status: string;
}): Promise<InventoryPage> {
  const query = new URLSearchParams({
    limit: String(options.limit), offset: String(options.offset),
    pen_id: options.penId, status: options.status,
  });
  return request(`/api/inventory-checks/page?${query}`);
}

export function createInventoryCheck(values: NewInventoryCheck): Promise<InventoryCheck> {
  return request("/api/inventory-checks", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values),
  });
}

export function createInventoryRecheck(checkId: string, values: NewInventoryRecheck): Promise<InventoryCheck> {
  return request(`/api/inventory-checks/${encodeURIComponent(checkId)}/rechecks`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values),
  });
}

export function fetchVideoReviews(jobId: string): Promise<VideoReview[]> {
  return request(`/api/jobs/${jobId}/reviews`);
}

export function fetchVideoEvents(jobId: string): Promise<VideoEvent[]> {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/events`);
}

export function videoEventClipUrl(jobId: string, eventId: number): string {
  return `/api/jobs/${encodeURIComponent(jobId)}/events/${eventId}/clip`;
}

export function fetchVideoCorrections(jobId: string): Promise<VideoCorrection[]> {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/corrections`);
}

export function createVideoCorrection(jobId: string, correction: NewVideoCorrection): Promise<VideoCorrection> {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/corrections`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(correction),
  });
}

export function deleteVideoCorrection(jobId: string, correctionId: string): Promise<void> {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/corrections/${encodeURIComponent(correctionId)}`, { method: "DELETE" });
}

export function videoCorrectionsCsvUrl(jobId: string): string {
  return `/api/jobs/${encodeURIComponent(jobId)}/corrections.csv`;
}

export function fetchDatasetEvaluations(): Promise<DatasetEvaluation[]> {
  return request("/api/evaluations");
}

export function createDatasetEvaluation(values: {
  jobId: string; datasetName: string; sourceUrl: string; datasetVersion: string;
  licenseName: string; splitName: DatasetEvaluation["split_name"]; annotations: File;
}): Promise<DatasetEvaluation> {
  const body = new FormData();
  body.append("job_id", values.jobId);
  body.append("dataset_name", values.datasetName);
  body.append("source_url", values.sourceUrl);
  body.append("dataset_version", values.datasetVersion);
  body.append("license_name", values.licenseName);
  body.append("split_name", values.splitName);
  body.append("annotations", values.annotations);
  return request("/api/evaluations", { method: "POST", body });
}

export function createVideoReview(jobId: string, review: NewVideoReview): Promise<VideoReview> {
  return request(`/api/jobs/${jobId}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(review),
  });
}

export function fetchAnimalLinks(jobId: string): Promise<AnimalLink[]> {
  return request(`/api/jobs/${jobId}/animal-links`);
}

export function createAnimalLink(jobId: string, trackId: number, animalId: string): Promise<AnimalLink> {
  return request(`/api/jobs/${jobId}/animal-links`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track_id: trackId, animal_id: animalId }),
  });
}

export function deleteAnimalLink(jobId: string, trackId: number): Promise<void> {
  return request(`/api/jobs/${jobId}/animal-links/${trackId}`, { method: "DELETE" });
}

export function fetchAnimalProfile(animalId: string): Promise<AnimalProfile> {
  return request(`/api/animals/${encodeURIComponent(animalId)}`);
}

export function createAnimalFollowup(
  animalId: string,
  values: Pick<AnimalFollowup, "kind" | "observed_at" | "note" | "diagnosis" | "source_reference">,
): Promise<AnimalFollowup> {
  return request(`/api/animals/${encodeURIComponent(animalId)}/followups`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
}

export function fetchCrossDomainExperiment(): Promise<CrossDomainExperimentResult> {
  return request("/api/experiments/cross-domain-behavior");
}

export function resultMediaUrl(path: string): string {
  return `/media/results/${path.replaceAll("\\", "/")}`;
}
