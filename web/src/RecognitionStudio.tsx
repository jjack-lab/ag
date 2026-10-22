import {
  CheckCircle2,
  FileText,
  Image as ImageIcon,
  LoaderCircle,
  UploadCloud,
  Video,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";

import {
  createVideoJob,
  fetchVideoJob,
  ImageRecognitionResult,
  recognizeImage,
  resultMediaUrl,
  VideoJob,
  VideoEvent,
} from "./api";
import CrossDomainResults from "./CrossDomainResults";
import HealthEvidence from "./HealthEvidence";
import VideoReviewWorkspace from "./VideoReviewWorkspace";
import InventoryPanel from "./InventoryPanel";
import VideoEventTimeline from "./VideoEventTimeline";
import SpatialAnalysisPanel from "./SpatialAnalysisPanel";
import VideoCorrectionEditor from "./VideoCorrectionEditor";
import ActionTaskPanel from "./ActionTaskPanel";
import VideoCaptureGuidance from "./VideoCaptureGuidance";
import InspectionSummary from "./InspectionSummary";

type RecognitionMode = "image" | "video";
type StudioResult =
  | { kind: "image"; data: ImageRecognitionResult; classId: number }
  | { kind: "video"; data: VideoJob };
type Props = { requestedJob?: VideoJob | null };

const DEFAULT_MESSAGE = "选择文件后，系统会自动使用牧业专用模型识别。";

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export default function RecognitionStudio({ requestedJob }: Props) {
  const [mode, setMode] = useState<RecognitionMode>("image");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<StudioResult | null>(null);
  const [status, setStatus] = useState<"idle" | "running" | "error">("idle");
  const [message, setMessage] = useState(DEFAULT_MESSAGE);
  const [confidence, setConfidence] = useState(0.25);
  const [iou, setIou] = useState(0.45);
  const [classId, setClassId] = useState(-1);
  const [tracker, setTracker] = useState<"bytetrack.yaml" | "botsort.yaml">(
    "bytetrack.yaml",
  );
  const [reviewRevision, setReviewRevision] = useState(0);
  const [selectedTaskEvent, setSelectedTaskEvent] = useState<VideoEvent | null>(null);
  const runToken = useRef(0);
  const resultVideo = useRef<HTMLVideoElement>(null);

  useEffect(
    () => () => {
      runToken.current += 1;
    },
    [],
  );

  useEffect(() => {
    if (!requestedJob) return;
    runToken.current += 1;
    setMode("video");
    setFile(null);
    setResult({ kind: "video", data: requestedJob });
    setSelectedTaskEvent(null);
    setStatus("idle");
    setMessage("已打开该盘点绑定的视频证据。");
  }, [requestedJob]);

  function resetRun() {
    runToken.current += 1;
    setFile(null);
    setResult(null);
    setSelectedTaskEvent(null);
    setStatus("idle");
    setMessage(DEFAULT_MESSAGE);
  }

  function switchMode(nextMode: RecognitionMode) {
    setMode(nextMode);
    resetRun();
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setStatus("error");
      setMessage(
        mode === "image" ? "请先选择一张牛只图片。" : "请先选择一段牛或羊视频。",
      );
      return;
    }

    const token = runToken.current + 1;
    runToken.current = token;
    setStatus("running");
    setResult(null);
    setMessage(mode === "image" ? "正在识别图片，请稍候…" : "正在创建视频追踪任务…");

    try {
      if (mode === "image") {
        const imageResult = await recognizeImage(file, {
          conf: confidence,
          iou,
          classId,
          tracker,
        });
        if (runToken.current !== token) return;
        setResult({ kind: "image", data: imageResult, classId });
        setStatus("idle");
        setMessage("识别完成，结果已经显示在右侧。");
        return;
      }

      let job = await createVideoJob(file, {
        conf: confidence,
        iou,
        classId: classId === -1 ? 1 : classId,
        tracker,
      });
      while (runToken.current === token) {
        setMessage(`视频追踪中，进度 ${Math.round(job.progress * 100)}%…`);
        if (job.status === "completed") {
          setResult({ kind: "video", data: job });
          setStatus("idle");
          setMessage("追踪完成，视频、轨迹和健康证据已生成。");
          return;
        }
        if (job.status === "failed") {
          throw new Error(job.error || "视频追踪失败，请检查文件后重试。");
        }
        job = await fetchVideoJob(job.id);
        if (job.status !== "completed" && job.status !== "failed") {
          await delay(1000);
        }
      }
    } catch (error) {
      if (runToken.current !== token) return;
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "识别失败，请重试。");
    }
  }

  const isImage = mode === "image";
  const imageResult = result?.kind === "image" ? result.data : null;
  const videoJob = result?.kind === "video" ? result.data : null;
  const tracking = videoJob?.result;

  return (
    <section
      id="recognition-studio"
      className="recognition-studio"
      aria-labelledby="recognition-title"
    >
      <div className="recognition-control">
        <div className="panel-title recognition-heading">
          <div>
            <p>智能识别工作台</p>
            <h3 id="recognition-title">上传文件，直接查看识别结果</h3>
          </div>
          <span className="step-hint">选择文件 → 开始识别 → 查看结果</span>
        </div>

        <div className="recognition-tabs" aria-label="选择识别类型">
          <button
            type="button"
            className={isImage ? "active" : ""}
            onClick={() => switchMode("image")}
          >
            <ImageIcon size={18} /> 图片识别
          </button>
          <button
            type="button"
            className={!isImage ? "active" : ""}
            onClick={() => switchMode("video")}
          >
            <Video size={18} /> 视频识别
          </button>
        </div>

        <form onSubmit={submit}>
          <label className="upload-zone">
            <input
              key={mode}
              aria-label={isImage
                ? classId === 0 ? "选择羊只图片" : "选择牛只图片"
                : classId === 0 ? "选择羊只视频" : "选择牛只视频"}
              type="file"
              accept={isImage ? "image/*" : "video/*"}
              onChange={(event) => {
                runToken.current += 1;
                setFile(event.target.files?.[0] || null);
                setResult(null);
                setStatus("idle");
                setMessage(DEFAULT_MESSAGE);
              }}
            />
            <span className="upload-icon">
              <UploadCloud />
            </span>
            <strong>
              {file
                ? file.name
                : isImage
                  ? classId === 0 ? "选择或拖入羊只图片" : "选择或拖入牛只图片"
                  : classId === 0 ? "选择或拖入羊只视频" : "选择或拖入牛只视频"}
            </strong>
            <small>
              {isImage ? "支持 JPG、PNG、BMP" : "支持 MP4、AVI、MOV、MKV"}
            </small>
          </label>

          {!isImage && file && <VideoCaptureGuidance file={file} />}

          <div className="recognition-parameters" aria-label="识别参数">
            <label>
              检测置信度
              <input
                aria-label="检测置信度"
                type="number"
                min="0.05"
                max="0.95"
                step="0.05"
                value={confidence}
                onChange={(event) => setConfidence(Number(event.target.value))}
              />
            </label>
            <label>
              重叠阈值
              <input
                aria-label="重叠阈值"
                type="number"
                min="0.05"
                max="0.95"
                step="0.05"
                value={iou}
                onChange={(event) => setIou(Number(event.target.value))}
              />
            </label>
            <label>
              识别类别
              <select
                aria-label="识别类别"
                value={classId}
                onChange={(event) => setClassId(Number(event.target.value))}
              >
                <option value={-1}>{isImage ? "全部牲畜" : "默认牛"}</option>
                <option value={1}>牛</option>
                <option value={0}>羊</option>
              </select>
            </label>
            {!isImage && (
              <label>
                跟踪算法
                <select
                  aria-label="跟踪算法"
                  value={tracker}
                  onChange={(event) =>
                    setTracker(event.target.value as "bytetrack.yaml" | "botsort.yaml")
                  }
                >
                  <option value="bytetrack.yaml">ByteTrack</option>
                  <option value="botsort.yaml">BoT-SORT</option>
                </select>
              </label>
            )}
          </div>

          <div className={`recognition-message ${status}`} role="status">
            {status === "running" ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <CheckCircle2 size={17} />
            )}
            <span>{message}</span>
          </div>

          <button
            className="recognition-submit"
            type="submit"
            disabled={status === "running"}
          >
            {status === "running"
              ? "识别处理中…"
              : isImage
                ? "开始图片识别"
                : "开始视频识别"}
          </button>
        </form>
      </div>

      <div className="recognition-result">
        <div className="result-header">
          <span>识别结果</span>
          {imageResult && <strong>识别到 {imageResult.detection_count} {result?.kind === "image" && result.classId === 1 ? "头牛" : result?.kind === "image" && result.classId === 0 ? "只羊" : "个目标"}</strong>}
          {tracking && <strong>视频内 Track ID：{tracking.tracked_cattle} 个</strong>}
        </div>
        <div className="result-stage">
          {!result && (
            <div className="empty-result">
              <ImageIcon size={38} />
              <strong>结果会显示在这里</strong>
              <span>检测框、Track ID、轨迹与健康证据清晰可见</span>
            </div>
          )}
          {imageResult && (
            <img src={imageResult.result_url} alt="牛只图片识别结果" />
          )}
          {tracking && (
            <video
              ref={resultVideo}
              src={resultMediaUrl(tracking.video_path)}
              controls
              aria-label={tracking.species === "sheep" ? "羊只视频追踪结果" : "牛只视频追踪结果"}
            />
          )}
        </div>
        {tracking && (
          <div className="result-artifacts" aria-label="追踪结果文件">
            <span>
              {tracking.frame_count} 帧 · {tracking.alert_count} 条规则告警
              {tracking.trajectory_anomaly_count
                ? ` · ${tracking.trajectory_anomaly_count} 条轨迹异常`
                : ""}
            </span>
            {tracking.species !== "sheep" && <a
              href={resultMediaUrl(tracking.health_report_html)}
              target="_blank"
              rel="noreferrer"
            >
              <FileText size={14} /> 健康报告
            </a>}
            <a href={resultMediaUrl(tracking.video_path)} download>
              下载结果视频
            </a>
            <a href={resultMediaUrl(tracking.trajectory_csv)} download>
              轨迹 CSV
            </a>
            {tracking.species !== "sheep" && <a href={resultMediaUrl(tracking.alert_csv)} download>
              告警 CSV
            </a>}
            {tracking.species !== "sheep" && <a href={resultMediaUrl(tracking.health_summary_csv)} download>
              健康汇总 CSV
            </a>}
            {tracking.trajectory_anomaly_csv && (
              <a href={resultMediaUrl(tracking.trajectory_anomaly_csv)} download>
                轨迹异常 CSV
              </a>
            )}
            <small>若浏览器无法直接播放结果视频，请使用“下载结果视频”。</small>
          </div>
        )}
        {tracking && videoJob && <VideoEventTimeline jobId={videoJob.id} refreshKey={reviewRevision} onCreateTask={setSelectedTaskEvent} onSeek={(seconds) => {
          if (!resultVideo.current) return;
          resultVideo.current.currentTime = seconds;
          resultVideo.current.scrollIntoView?.({ block: "center", behavior: "smooth" });
        }} />}
        {tracking && videoJob && <SpatialAnalysisPanel key={videoJob.id} jobId={videoJob.id} videoPath={tracking.video_path}
          onReportSaved={() => setReviewRevision((value) => value + 1)} />}
        {tracking && videoJob && <VideoCorrectionEditor key={videoJob.id} jobId={videoJob.id}
          videoPath={tracking.video_path} species={tracking.species || "cattle"}
          trackIds={tracking.track_ids || []}
          onCorrectionChanged={() => setReviewRevision((value) => value + 1)} />}
        {tracking && (
          <HealthEvidence
            species={tracking.species || "cattle"}
            profiles={tracking.health_evidence || []}
          />
        )}
        {tracking?.species === "sheep" && <section className="sheep-motion-panel" aria-label="羊只活动状态分析">
          <header><strong>羊只活动状态</strong><small>根据检测框中心位移估计，仅描述移动程度</small></header>
          <p>低位移、移动、快速移动为规则估计，不能据此判断采食、坐卧或健康状态。镜头移动和 ID 切换会影响结果。</p>
          {(tracking.sheep_motion_summary || []).length === 0 && <p>此视频没有足够的连续追踪帧，暂无法估计活动状态。</p>}
          {(tracking.sheep_motion_summary || []).map((row) => <article key={row.track_id}>
            <strong>视频内 ID {row.track_id}</strong>
            <span>低位移 {row.still_seconds.toFixed(1)} 秒</span>
            <span>移动 {row.moving_seconds.toFixed(1)} 秒</span>
            <span>快速移动 {row.fast_seconds.toFixed(1)} 秒</span>
            <small>有效观察 {row.observed_seconds.toFixed(1)} 秒</small>
          </article>)}
        </section>}
        {tracking?.trajectory_anomaly_status === "ok" && (
          <section
            className="behavior-result"
            aria-label="轨迹异常检测结果"
          >
            <header>
              <div>
                <strong>轨迹异常检测</strong>
                <span>Isolation Forest · 与牛群整体对比</span>
              </div>
              <small>
                发现 {tracking.trajectory_anomaly_count ?? 0} 头活动模式偏离牛群
              </small>
            </header>
            {(tracking.trajectory_anomalies || [])
              .filter((row) => row.is_outlier)
              .map((row) => (
                <article className="behavior-track" key={row.track_id}>
                  <div>
                    <strong>视频内 ID {row.track_id}</strong>
                    <small>
                      异常得分 {(row.anomaly_score * 100).toFixed(1)}%
                    </small>
                  </div>
                  <div className="behavior-table">
                    <div>
                      <span>主要差异特征</span>
                      <strong>
                        {(row.top_contributors || []).join("、") || "—"}
                      </strong>
                      <small>建议人工复核活动与采食情况</small>
                    </div>
                  </div>
                </article>
              ))}
          </section>
        )}
        {tracking?.trajectory_anomaly_status === "skipped" && (
          <p className="behavior-unavailable">
            轨迹异常检测已跳过（{tracking.trajectory_anomaly_reason || "牛只数量不足"}
            ），规则健康分析不受影响。
          </p>
        )}
        {tracking?.trajectory_anomaly_status === "failed" && (
          <p className="behavior-unavailable">
            轨迹异常检测运行失败，其他结果已保留。
            {tracking.trajectory_anomaly_reason && ` ${tracking.trajectory_anomaly_reason}`}
          </p>
        )}
        {tracking?.behavior_model_status === "ready" && (
          <section className="behavior-result" aria-label="行为识别结果">
            <header>
              <div>
                <strong>行为识别</strong>
                <span>研究演示模型</span>
              </div>
              <small>模型版本 {tracking.behavior_model_version || "未知"}</small>
            </header>
            {[...new Set((tracking.behavior_summary || []).map((row) => row.track_id))].map(
              (trackId) => {
                const rows = (tracking.behavior_summary || []).filter(
                  (row) => row.track_id === trackId,
                );
                const uncertain = Math.max(
                  0,
                  ...rows.map((row) => row.uncertain_duration_seconds),
                );
                return (
                  <article className="behavior-track" key={trackId}>
                    <div>
                      <strong>视频内 ID {trackId}</strong>
                      <small>无法确定 {uncertain.toFixed(1)} 秒</small>
                    </div>
                    <div className="behavior-table">
                      {rows.map((row) => (
                        <div key={`${row.track_id}-${row.behavior_name}`}>
                          <span>{row.behavior_display_name}</span>
                          <strong>{row.duration_seconds.toFixed(1)} 秒</strong>
                          <small>{(row.eligible_ratio * 100).toFixed(1)}%</small>
                        </div>
                      ))}
                    </div>
                  </article>
                );
              },
            )}
            <footer>
              {tracking.behavior_csv && (
                <a href={resultMediaUrl(tracking.behavior_csv)} download>
                  行为时间线 CSV
                </a>
              )}
              {tracking.behavior_summary_csv && (
                <a href={resultMediaUrl(tracking.behavior_summary_csv)} download>
                  行为汇总 CSV
                </a>
              )}
            </footer>
          </section>
        )}
        {tracking && tracking.behavior_model_status === "unavailable" && (
          <p className="behavior-unavailable">
            {tracking.species === "sheep"
              ? "羊的行为与健康模型尚未验证，本次仅提供检测和追踪。"
              : "行为模型未加载，检测、追踪和规则健康分析仍可用。"}
          </p>
        )}
        {tracking && tracking.behavior_model_status === "failed" && (
          <p className="behavior-unavailable">
            行为识别运行失败，其他结果已保留。
            {tracking.behavior_model_error && ` ${tracking.behavior_model_error}`}
          </p>
        )}
        {!isImage && <VideoReviewWorkspace
          selectedJob={videoJob}
          onReviewSaved={() => setReviewRevision((value) => value + 1)}
          onSelectJob={(job) => {
            runToken.current += 1;
            setResult({ kind: "video", data: job });
            setSelectedTaskEvent(null);
            setStatus("idle");
            setMessage("已打开历史视频结果和人工复核记录。");
          }}
        />}
        {!isImage && <InventoryPanel selectedJob={videoJob} />}
        {tracking && videoJob && <ActionTaskPanel key={videoJob.id} job={videoJob} selectedEvent={selectedTaskEvent} />}
        {tracking && videoJob && <InspectionSummary key={videoJob.id} job={videoJob} />}
      </div>
      <CrossDomainResults />
    </section>
  );
}
