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
import { moduleHref, moduleNames, parseSiteRoute, type ModuleName } from "./moduleRoutes";
import "./workspace-interactions.css";
import "./site-refresh.css";
import "./immersive-home.css";
import "./module-navigation.css";
import "./cosmic-palette.css";

type WorkspaceView = ModuleName;

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
  const [route, setRoute] = useState(() => parseSiteRoute(window.location.hash));
  const [introPercent, setIntroPercent] = useState(0);
  const [introVisible, setIntroVisible] = useState(() => parseSiteRoute(window.location.hash).kind === "home");
  const [heroEntering, setHeroEntering] = useState(false);
  const activeView = route.kind === "module" ? route.name : "overview";
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
    const onHashChange = () => setRoute(parseSiteRoute(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    if (!introVisible) return;
    if (reduceMotion) {
      setIntroVisible(false);
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(() => {
      const progress = Math.min(100, Math.floor(((Date.now() - started) / 1100) * 100));
      setIntroPercent(progress);
      if (progress === 100) {
        window.clearInterval(timer);
        window.setTimeout(() => setIntroVisible(false), 260);
      }
    }, 30);
    return () => window.clearInterval(timer);
  }, [introVisible, reduceMotion]);

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

  function navigate(hash: string) {
    window.location.hash = hash;
    setRoute(parseSiteRoute(hash));
    window.scrollTo?.(0, 0);
  }

  function showView(view: WorkspaceView, target = "workspace") {
    navigate(moduleHref(view));
    if (target !== "workspace") scrollToElement(target);
  }

  function openView(view: WorkspaceView, target = "workspace") {
    inventoryOpenToken.current += 1;
    setOpeningInventoryJobId(null);
    setInventoryVideoError("");
    setRequestedVideoJob(null);
    showView(view, target);
  }

  function enterWorkspace() {
    if (reduceMotion) {
      navigate("#/modules");
      return;
    }
    setHeroEntering(true);
    window.setTimeout(() => {
      setHeroEntering(false);
      navigate("#/modules");
    }, 850);
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
      {route.kind === "home" && <>
      {introVisible && <div className="intro-loader" aria-label="场景加载动画"><div className="intro-loader-brand">AGRI <span>/</span> NEBULA</div><div className="intro-loader-bottom"><span>牧场视觉健康系统</span><strong>{introPercent}%</strong></div><div className="intro-loader-track"><i style={{ width: `${introPercent}%` }} /></div></div>}
      <section className={`hero immersive-hero ${heroEntering ? "hero-entering" : ""}`} aria-label="星牧智控欢迎页">
        <div className="immersive-scene" aria-hidden="true" />
        <ParticleField />
        <nav className="floating-nav liquid-glass">
          <a className="brand" href="#/" aria-label="星牧智控首页">
            <span className="brand-mark"><CircleDot size={20} /></span>
            <span>星牧智控 <small>AgriNebula</small></span>
          </a>
          <div className="nav-links">
            <a href="#/modules">模块入口</a>
            <a href={moduleHref("monitor")}>视频识别</a>
            <a href={moduleHref("health")}>健康报告</a>
            <a href={moduleHref("alerts")}>健康告警</a>
          </div>
          <span className={`local-status ${modelReady ? "" : "offline"}`}>
            <i /> {dataError ? "数据暂不可用" : modelReady ? "本地模型已就绪" : "正在连接本地服务"}
          </span>
        </nav>

        <motion.div className="hero-content immersive-content" {...entrance} transition={{ duration: 0.8, ease: "easeOut" }}>
          <div className="immersive-scene-label"><Eye size={14} /> FIELD 01 / CATTLE VISION <span>开发视频演示素材</span></div>
          <button type="button" className="immersive-portal" onClick={enterWorkspace} aria-label="进入健康控制中心">
            <span className="immersive-portal-image" />
            <span className="immersive-portal-ring"><ArrowUpRight size={25} /></span>
            <span className="immersive-portal-caption">进入健康控制中心</span>
          </button>
          <div className="immersive-headline"><span>AGRI / NEBULA</span><h1>看见每一头牛的变化</h1></div>
          <div className="immersive-info">
            <p className="hero-copy">从视频识别到行为线索，再到人工核查与健康报告。让每一次判断都能回到原始证据。</p>
            <div className="immersive-links"><button type="button" className="hero-report-link" onClick={() => openView("health")}>查看健康分析与报告 <ArrowUpRight size={17} /></button><a className="hero-report-link" href={moduleHref("monitor")}>查看识别能力 <ArrowUpRight size={17} /></a></div>
            <div className={`immersive-reading ${dashboard?.latest_cattle_track_count == null ? "is-empty" : ""}`}><small>最近牛视频</small><strong>{dashboard?.latest_cattle_track_count ?? "暂无记录"}</strong><span>视频内 Track ID · 非存栏总数</span></div>
          </div>
        </motion.div>

        <div className="hero-foot immersive-foot"><span>01 视频识别</span><span>02 行为与规则</span><span>03 报告与复核</span><span>点击中央入口进入模块 →</span></div>
      </section>
      </>}

      {route.kind === "modules" && <section className="module-hub" aria-label="工作模块入口">
        <ParticleField />
        <div className="module-hub-inner">
          <nav className="module-hub-nav"><a className="brand" href="#/" aria-label="星牧智控首页"><span className="brand-mark"><CircleDot size={20} /></span><span>星牧智控 <small>AgriNebula</small></span></a><span>FIELD SYSTEM / 08 MODULES</span></nav>
          <header className="module-hub-heading"><span>SELECT YOUR WORKSPACE / 选择工作空间</span><h1>选择工作模块</h1><p>从一段视频出发，进入识别、健康分析、告警核查与圈舍盘点。每个模块都有独立网址，可直接访问。</p></header>
          <div className="module-grid">{moduleNames.map((name, index) => {
            const details: Record<ModuleName, [string, string, typeof Activity]> = {
              overview: ["今日工作台", "最近任务与待核查提示", Activity],
              monitor: ["视频识别", "上传视频，查看追踪与证据", ScanSearch],
              health: ["健康模型", "健康数据、风险分析与报告", HeartPulse],
              alerts: ["健康告警", "查看规则提示与视频线索", BellRing],
              tasks: ["处置待办", "记录核查、误报与复查", ClipboardList],
              cattle: ["牛只档案", "核对耳标并关联个体记录", ShieldCheck],
              analytics: ["数据分析", "统计结果与模型评估", ChartNoAxesCombined],
              inventory: ["圈舍盘点", "人工记录与视频结果核对", CircleDot],
            };
            const [title, description, Icon] = details[name];
            return <a className="module-card" href={moduleHref(name)} onClick={() => navigate(moduleHref(name))} key={name}><span className="module-card-top"><small>{String(index + 1).padStart(2, "0")} / 08</small><ArrowUpRight size={19} /></span><Icon size={32} strokeWidth={1.5} /><span><strong>{title}</strong><small>{description}</small></span></a>;
          })}</div>
        </div>
      </section>}

      {route.kind === "module" && <section id="workspace" className="workspace section-pad workspace-focus module-workspace">
        <aside className="workspace-nav liquid-glass" aria-label="工作区导航">
          <div className="mini-brand"><span className="brand-mark"><CircleDot size={18} /></span> AgriNebula</div>
          <a className="module-back-link" href="#/modules">← 返回模块入口</a>
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
              <div className="workspace-grid">
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
      </section>}
    </main>
  );
}
