import { motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  ArrowUpRight,
  BellRing,
  ChartNoAxesCombined,
  ClipboardList,
  CircleDot,
  Eye,
  HeartPulse,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertRecord, Dashboard, fetchAlerts, fetchDashboard, fetchVideoJob, type VideoJob } from "./api";
import RecognitionStudio from "./RecognitionStudio";
import DatasetEvaluationCenter from "./DatasetEvaluationCenter";
import InventoryPanel from "./InventoryPanel";
import ActionTaskInbox from "./ActionTaskInbox";
import HealthInsights from "./HealthInsights";
import ParticleField from "./ParticleField";
import "./workspace-interactions.css";
import "./site-refresh.css";

type WorkspaceView = "overview" | "monitor" | "alerts" | "tasks" | "cattle" | "analytics" | "inventory" | "health";

const capabilities = [
  {
    icon: ScanSearch,
    title: "牛只识别与持续追踪",
    text: "为视频内牛只分配 Track ID，记录位置、速度与活动轨迹。",
    meta: "YOLO · TRACK ID",
  },
  {
    icon: HeartPulse,
    title: "健康风险提前预警",
    text: "发现长时间不动、疑似倒地、离群与活动量下降。",
    meta: "BEHAVIOR · ALERT",
  },
  {
    icon: ChartNoAxesCombined,
    title: "个体档案与群体趋势",
    text: "把检测结果转化为牧场人员能够直接执行的健康任务。",
    meta: "INSIGHT · ACTION",
  },
];

const riskLabel: Record<AlertRecord["level"], string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险",
};

const viewTitle: Record<WorkspaceView, string> = {
  overview: "视频任务与历史规则概览",
  monitor: "实时监控",
  alerts: "全部健康告警",
  tasks: "处置待办与复查",
  cattle: "牛只档案",
  analytics: "数据分析",
  inventory: "圈舍存栏核对",
  health: "健康模型分析",
};

function isVideoJobResponse(value: unknown): value is VideoJob {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  if (typeof candidate.id !== "string" || candidate.id.trim() === "") return false;
  if (
    typeof candidate.status !== "string" ||
    !["queued", "running", "completed", "failed"].includes(candidate.status)
  ) return false;
  if (typeof candidate.progress !== "number" || !Number.isFinite(candidate.progress)) return false;
  if (candidate.status === "completed") {
    if (typeof candidate.result !== "object" || candidate.result === null || Array.isArray(candidate.result)) {
      return false;
    }
    const result = candidate.result as Record<string, unknown>;
    const pathFields = [
      "video_path",
      "trajectory_csv",
      "alert_csv",
      "health_summary_csv",
      "health_report_html",
    ];
    if (!pathFields.every((field) => typeof result[field] === "string")) return false;
    const countFields = ["frame_count", "tracked_cattle", "alert_count"];
    if (!countFields.every((field) => typeof result[field] === "number" && Number.isFinite(result[field]))) {
      return false;
    }
  }
  return true;
}

export default function App() {
  const [workspaceVisible, setWorkspaceVisible] = useState(false);
  const [activeView, setActiveView] = useState<WorkspaceView>("overview");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [dataError, setDataError] = useState(false);
  const [requestedVideoJob, setRequestedVideoJob] = useState<VideoJob | null>(null);
  const [openingInventoryJobId, setOpeningInventoryJobId] = useState<string | null>(null);
  const [inventoryVideoError, setInventoryVideoError] = useState("");
  const inventoryOpenToken = useRef(0);
  const reduceMotion = useReducedMotion();
  const entrance = reduceMotion
    ? { initial: false as const, animate: {} }
    : {
        initial: { opacity: 0, y: 24, filter: "blur(10px)" },
        animate: { opacity: 1, y: 0, filter: "blur(0px)" },
      };

  useEffect(() => {
    let active = true;
    Promise.all([fetchDashboard(), fetchAlerts()])
      .then(([nextDashboard, nextAlerts]) => {
        if (!active) return;
        setDashboard(nextDashboard);
        setAlerts(nextAlerts);
        setDataError(false);
      })
      .catch(() => {
        if (!active) return;
        setDashboard(null);
        setAlerts([]);
        setDataError(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const alertDistribution = useMemo(
    () => ({
      high: alerts.filter((alert) => alert.level === "high").length,
      medium: alerts.filter((alert) => alert.level === "medium").length,
      low: alerts.filter((alert) => alert.level === "low").length,
    }),
    [alerts],
  );

  function scrollToElement(id: string) {
    window.setTimeout(() => {
      const element = document.getElementById(id);
      if (element && typeof element.scrollIntoView === "function") {
        element.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }, 0);
  }

  function showView(view: WorkspaceView, target = "workspace") {
    setWorkspaceVisible(true);
    setActiveView(view);
    scrollToElement(target);
  }

  function openView(view: WorkspaceView, target = "workspace") {
    inventoryOpenToken.current += 1;
    setOpeningInventoryJobId(null);
    setInventoryVideoError("");
    setRequestedVideoJob(null);
    showView(view, target);
  }

  async function openInventoryVideo(jobId: string) {
    const token = inventoryOpenToken.current + 1;
    inventoryOpenToken.current = token;
    setOpeningInventoryJobId(jobId);
    setInventoryVideoError("");
    try {
      const response: unknown = await fetchVideoJob(jobId);
      if (inventoryOpenToken.current !== token) return;
      if (!isVideoJobResponse(response)) {
        throw new Error("视频证据加载失败");
      }
      const job = response;
      if (job.status !== "completed" || !job.result) {
        throw new Error("视频任务尚未完成，暂不能打开证据");
      }
      setRequestedVideoJob(job);
      showView("monitor", "recognition-studio");
    } catch (error) {
      if (inventoryOpenToken.current !== token) return;
      setInventoryVideoError(error instanceof Error ? error.message : "视频证据加载失败");
    } finally {
      if (inventoryOpenToken.current === token) setOpeningInventoryJobId(null);
    }
  }

  const modelReady = dashboard?.model_status === "ready";
  const dateLabel = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(new Date());

  const renderAlertList = (emptyText: string) => (
    <div className="alert-list">
      {dataError && <p className="empty-alerts">数据暂不可用，请确认本地 API 已启动。</p>}
      {!dataError && alerts.length === 0 && <p className="empty-alerts">{emptyText}</p>}
      {alerts.map((alert) => {
        const expanded = selectedAlertId === alert.id;
        return (
          <div className="alert-item" key={alert.id}>
            <button
              type="button"
              className="alert-row"
              aria-label={`视频内 ID ${alert.cattle_id}，${alert.reason}，${riskLabel[alert.level]}`}
              aria-expanded={expanded}
              onClick={() => setSelectedAlertId(expanded ? null : alert.id)}
            >
              <span className={`severity severity-${alert.level}`} />
              <span className="cattle-avatar">{alert.cattle_id}</span>
              <span className="alert-copy">
                <strong>视频内 ID {alert.cattle_id}</strong>
                <small>{alert.reason}</small>
              </span>
              <span className="alert-meta">
                <b>{riskLabel[alert.level]}</b>
                <small>{new Date(alert.occurred_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</small>
              </span>
            </button>
            {expanded && (
              <div className="alert-details" role="region" aria-label={`视频内 ID ${alert.cattle_id} 告警详情`}>
                <strong>处置建议：{alert.suggestion}</strong>
                <span>发生时间：{new Date(alert.occurred_at).toLocaleString("zh-CN")}</span>
                <span>置信度 {Math.round(alert.confidence * 100)}%</span>
                {alert.id.includes(":") && <button type="button" onClick={() => openInventoryVideo(alert.id.split(":")[0])}>
                  打开对应视频证据
                </button>}
                {inventoryVideoError && <small role="alert">{inventoryVideoError}</small>}
                <small>该结果用于健康风险筛查，不替代兽医诊断。</small>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  const metrics = (
    <div className="metric-grid">
      <article>
        <span>最近牛视频 Track ID 数</span>
        <strong data-testid="monitored-cattle">{dashboard ? dashboard.latest_cattle_track_count ?? "暂无记录" : "—"}</strong>
        <small>{dashboard?.latest_cattle_processed_at
          ? `处理时间：${new Date(dashboard.latest_cattle_processed_at).toLocaleString("zh-CN")}`
          : "仅统计已完成的牛视频"}</small>
      </article>
      <article className="risk">
        <span>历史高风险规则提示</span>
        <strong>{dashboard?.high_risk_alerts ?? "—"}</strong>
        <small>未处理提示条数，需优先人工复核</small>
      </article>
      <article>
        <span>历史未处理规则提示</span>
        <strong data-testid="open-alerts">{dashboard?.open_alerts ?? "—"}</strong>
        <small>跨视频累计；不代表当前牛只数</small>
      </article>
      <article>
        <span>模型运行状态</span>
        <strong className={modelReady ? "online" : ""}>
          {dataError ? "不可用" : modelReady ? "就绪" : "连接中"}
        </strong>
        <small>{modelReady ? "本地 YOLO11 + ByteTrack" : "未声明模型在线"}</small>
      </article>
    </div>
  );

  return (
    <main className="app-shell" id="top">
      <section className="hero" aria-label="星牧智控欢迎页">
        <ParticleField />
        <nav className="floating-nav liquid-glass">
          <a className="brand" href="#top" aria-label="星牧智控首页">
            <span className="brand-mark"><CircleDot size={20} /></span>
            <span>星牧智控 <small>AgriNebula</small></span>
          </a>
          <div className="nav-links">
            <a href="#workspace" onClick={() => openView("overview")}>今日工作台</a>
            <a href="#capabilities">识别能力</a>
            <a href="#workspace" onClick={() => openView("health")}>健康报告</a>
            <a href="#workspace" onClick={() => openView("alerts")}>健康告警</a>
          </div>
          <span className={`local-status ${modelReady ? "" : "offline"}`}>
            <i /> {dataError ? "数据暂不可用" : modelReady ? "本地模型已就绪" : "正在连接本地服务"}
          </span>
        </nav>

        <motion.div className="hero-content" {...entrance} transition={{ duration: 0.8, ease: "easeOut" }}>
          <div className="hero-story">
            <p className="eyebrow"><Eye size={15} /> AI 视觉驱动的牛群健康管理 <span className="hero-signal-dot" /></p>
            <h1>看见每一头牛的变化</h1>
            <p className="hero-copy">从每一帧视频到每一条健康线索。识别、追踪、行为分析与人工复核，在同一个牧场控制中心清晰呈现。</p>
            <div className="hero-actions">
              <button type="button" className="primary-action" onClick={() => openView("overview")}>进入健康控制中心 <ArrowUpRight size={18} /></button>
              <button type="button" className="hero-report-link" onClick={() => openView("health")}>查看健康分析与报告 <ArrowUpRight size={17} /></button>
              <a className="hero-report-link" href="#capabilities">查看识别能力 <ArrowUpRight size={17} /></a>
            </div>
            <div className="hero-pipeline"><span>01 视频识别</span><i /><span>02 行为与规则</span><i /><span>03 报告与复核</span></div>
          </div>
          <div className="hero-visual" aria-label="健康分析工作流展示">
            <div className="hero-visual-top"><span><i /> LOCAL ANALYSIS ENGINE</span><small>VIDEO → EVIDENCE</small></div>
            <div className="hero-hologram"><span className="hero-hologram-ring one" /><span className="hero-hologram-ring two" /><span className="hero-hologram-core"><HeartPulse size={54} /></span><i className="hero-hologram-node node-one" /><i className="hero-hologram-node node-two" /><i className="hero-hologram-node node-three" /></div>
            <div className="hero-visual-bottom"><div><small>最近牛视频</small><strong>{dashboard?.latest_cattle_track_count ?? "—"}</strong><span>视频内 Track ID</span></div><div><small>分析链路</small><strong>03</strong><span>识别 / 分析 / 复核</span></div></div>
          </div>
        </motion.div>

        <div className="hero-foot">
          <span>YOLO 视觉识别</span><span>持续目标追踪</span><span>行为风险分析</span><span>离线本地运行</span>
        </div>
      </section>

      <section id="capabilities" className="capabilities section-pad">
        <header className="section-heading">
          <p>从视频到行动建议</p>
          <h2>识别不止于一个检测框</h2>
        </header>
        <div className="capability-grid">
          {capabilities.map(({ icon: Icon, title, text, meta }, index) => (
            <motion.article
              className="capability-card liquid-glass"
              key={title}
              initial={reduceMotion ? false : { opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1, duration: 0.45 }}
            >
              <div className="capability-top"><span className="icon-box"><Icon /></span><small>{meta}</small></div>
              <div><h3>{title}</h3><p>{text}</p></div>
            </motion.article>
          ))}
        </div>
      </section>

      <section id="workspace" className={`workspace section-pad ${workspaceVisible ? "workspace-focus" : ""}`}>
        <aside className="workspace-nav liquid-glass" aria-label="工作区导航">
          <div className="mini-brand"><span className="brand-mark"><CircleDot size={18} /></span> AgriNebula</div>
          <button type="button" className={activeView === "overview" ? "active" : ""} aria-current={activeView === "overview" ? "page" : undefined} onClick={() => openView("overview")}><Activity size={18} /> 今日工作台</button>
          <button type="button" className={activeView === "monitor" ? "active" : ""} aria-current={activeView === "monitor" ? "page" : undefined} onClick={() => openView("monitor")}><ScanSearch size={18} /> 实时监控</button>
          <button type="button" className={activeView === "health" ? "active" : ""} aria-current={activeView === "health" ? "page" : undefined} onClick={() => openView("health")}><HeartPulse size={18} /> 健康模型分析</button>
          <button type="button" aria-label="健康告警" className={activeView === "alerts" ? "active" : ""} aria-current={activeView === "alerts" ? "page" : undefined} onClick={() => openView("alerts")}>
            <BellRing size={18} /> 健康告警 {!!dashboard?.open_alerts && <b>{dashboard.open_alerts}</b>}
          </button>
          <button type="button" className={activeView === "tasks" ? "active" : ""} aria-current={activeView === "tasks" ? "page" : undefined} onClick={() => openView("tasks")}><ClipboardList size={18} /> 处置待办</button>
          <button type="button" className={activeView === "cattle" ? "active" : ""} aria-current={activeView === "cattle" ? "page" : undefined} onClick={() => openView("cattle")}><ShieldCheck size={18} /> 牛只档案</button>
          <button type="button" className={activeView === "analytics" ? "active" : ""} aria-current={activeView === "analytics" ? "page" : undefined} onClick={() => openView("analytics")}><ChartNoAxesCombined size={18} /> 数据分析</button>
          <button type="button" className={activeView === "inventory" ? "active" : ""} aria-current={activeView === "inventory" ? "page" : undefined} onClick={() => openView("inventory")}><ShieldCheck size={18} /> 圈舍盘点</button>
          <div className="system-card">
            <i /> {dataError ? "数据暂不可用" : modelReady ? "系统运行正常" : "正在连接服务"}
            <small>本地模式 · {modelReady ? "YOLO11 已加载" : "等待模型状态"}</small>
          </div>
        </aside>

        <div className="workspace-main">
          <header className="workspace-header">
            <div><p>{dateLabel}</p><h2>{viewTitle[activeView]}</h2></div>
            {activeView === "overview" && (
              <button type="button" className="plain-button" onClick={() => openView("monitor", "recognition-studio")}>
                开始视频识别 <ArrowUpRight size={17} />
              </button>
            )}
          </header>

          {activeView === "overview" && (
            <>
              {metrics}
              <RecognitionStudio />
              <div className="workspace-grid">
                <article className="monitor-panel">
                  <div className="panel-title"><div><p>一号牛舍</p><h3>实时识别画面</h3></div><span className="live"><i /> LIVE</span></div>
                  <div className="monitor-visual">
                    <div className="scan-line" />
                    <div className="monitor-copy"><ScanSearch size={32} /><span>摄像头画面接入后将在此显示</span></div>
                  </div>
                </article>
                <article id="alerts" className="alert-panel">
                  <div className="panel-title"><div><p>需要关注</p><h3>最新健康告警</h3></div><button type="button" onClick={() => openView("alerts")}>查看全部</button></div>
                  {renderAlertList("当前没有待处理健康告警。")}
                </article>
              </div>
            </>
          )}

          {activeView === "monitor" && (
            <section className="focused-view" aria-label="实时监控功能区">
              <div className="view-intro"><ScanSearch /><div><h3>识别与追踪工作区</h3><p>上传图片或视频进行识别；摄像头硬件接入将在后续配置。</p></div></div>
              <RecognitionStudio requestedJob={requestedVideoJob} />
            </section>
          )}

          {activeView === "health" && <HealthInsights onOpenVideo={openInventoryVideo} />}

          {activeView === "alerts" && (
            <section className="focused-view alert-panel" id="alerts">
              <div className="panel-title"><div><p>风险筛查结果</p><h3>告警记录</h3></div><span>{alerts.length} 条</span></div>
              {renderAlertList("当前没有健康告警。")}
            </section>
          )}

          {activeView === "tasks" && <ActionTaskInbox
            onOpenVideo={openInventoryVideo}
            openingJobId={openingInventoryJobId}
            videoOpenError={inventoryVideoError}
          />}

          {activeView === "cattle" && (
            <section className="focused-view">
              <div className="view-intro"><ShieldCheck /><div><h3>个体记录</h3><p>跨视频个体需由现场人员核对耳标后人工关联。视频内 Track ID 不能直接作为牛只档案编号。</p></div></div>
              <p className="view-empty">请在视频识别结果中核对耳标并建立个体关联，再查看跨视频记录。</p>
            </section>
          )}

          {activeView === "analytics" && (
            <section className="focused-view">
              <div className="view-intro"><ChartNoAxesCombined /><div><h3>统计概览</h3><p>以下统计来自当前仪表盘和健康告警，不生成虚构趋势。</p></div></div>
              {metrics}
              <div className="distribution-grid" aria-label="告警风险分布">
                <article><span>高风险告警</span><strong>{alertDistribution.high}</strong></article>
                <article><span>中风险告警</span><strong>{alertDistribution.medium}</strong></article>
                <article><span>低风险告警</span><strong>{alertDistribution.low}</strong></article>
              </div>
              <DatasetEvaluationCenter />
            </section>
          )}
          {activeView === "inventory" && <InventoryPanel
            onOpenVideo={openInventoryVideo}
            openingJobId={openingInventoryJobId}
            videoOpenError={inventoryVideoError}
          />}
        </div>
      </section>
    </main>
  );
}
