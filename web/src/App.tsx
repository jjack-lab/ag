import { motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  ArrowUpRight,
  BellRing,
  ChartNoAxesCombined,
  CircleDot,
  Eye,
  HeartPulse,
  Play,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { AlertRecord, Dashboard, fetchAlerts, fetchDashboard } from "./api";
import RecognitionStudio from "./RecognitionStudio";
import "./workspace-interactions.css";

type WorkspaceView = "overview" | "monitor" | "alerts" | "cattle" | "analytics";

const capabilities = [
  {
    icon: ScanSearch,
    title: "牛只识别与持续追踪",
    text: "为每头牛建立稳定 ID，连续记录位置、速度与活动轨迹。",
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
  overview: "今日牧场健康概览",
  monitor: "实时监控",
  alerts: "全部健康告警",
  cattle: "牛只档案",
  analytics: "数据分析",
};

export default function App() {
  const [workspaceVisible, setWorkspaceVisible] = useState(false);
  const [activeView, setActiveView] = useState<WorkspaceView>("overview");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [dataError, setDataError] = useState(false);
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

  const cattleRecords = useMemo(
    () => Array.from(new Set(alerts.map((alert) => alert.cattle_id))),
    [alerts],
  );
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

  function openView(view: WorkspaceView, target = "workspace") {
    setWorkspaceVisible(true);
    setActiveView(view);
    scrollToElement(target);
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
              aria-label={`牛 ${alert.cattle_id}，${alert.reason}，${riskLabel[alert.level]}`}
              aria-expanded={expanded}
              onClick={() => setSelectedAlertId(expanded ? null : alert.id)}
            >
              <span className={`severity severity-${alert.level}`} />
              <span className="cattle-avatar">{alert.cattle_id}</span>
              <span className="alert-copy">
                <strong>牛 {alert.cattle_id}</strong>
                <small>{alert.reason}</small>
              </span>
              <span className="alert-meta">
                <b>{riskLabel[alert.level]}</b>
                <small>{new Date(alert.occurred_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</small>
              </span>
            </button>
            {expanded && (
              <div className="alert-details" role="region" aria-label={`牛 ${alert.cattle_id} 告警详情`}>
                <strong>处置建议：{alert.suggestion}</strong>
                <span>发生时间：{new Date(alert.occurred_at).toLocaleString("zh-CN")}</span>
                <span>置信度 {Math.round(alert.confidence * 100)}%</span>
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
        <span>今日监测牛只</span>
        <strong data-testid="monitored-cattle">{dashboard?.monitored_cattle ?? "—"}</strong>
        <small>来自已完成追踪任务</small>
      </article>
      <article className="risk">
        <span>高风险牛只</span>
        <strong>{dashboard?.high_risk_cattle ?? "—"}</strong>
        <small>需要优先人工复核</small>
      </article>
      <article>
        <span>待处理告警</span>
        <strong data-testid="open-alerts">{dashboard?.open_alerts ?? "—"}</strong>
        <small>来自本地健康规则</small>
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
        <div className="hero-media" />
        <div className="hero-grid" />
        <nav className="floating-nav liquid-glass">
          <a className="brand" href="#top" aria-label="星牧智控首页">
            <span className="brand-mark"><CircleDot size={20} /></span>
            <span>星牧智控 <small>AgriNebula</small></span>
          </a>
          <div className="nav-links">
            <a href="#workspace" onClick={() => openView("overview")}>今日工作台</a>
            <a href="#capabilities">识别能力</a>
            <a href="#workspace" onClick={() => openView("alerts")}>健康告警</a>
          </div>
          <span className={`local-status ${modelReady ? "" : "offline"}`}>
            <i /> {dataError ? "数据暂不可用" : modelReady ? "本地模型已就绪" : "正在连接本地服务"}
          </span>
        </nav>

        <motion.div className="hero-content" {...entrance} transition={{ duration: 0.8, ease: "easeOut" }}>
          <p className="eyebrow"><Eye size={15} /> AI 视觉驱动的牛群健康管理</p>
          <h1>看见每一头牛的变化</h1>
          <p className="hero-copy">让健康风险更早被发现。识别、追踪、分析与处置，在一个离线可用的牧场控制中心完成。</p>
          <div className="hero-actions">
            <button type="button" className="primary-action" onClick={() => openView("overview")}>
              进入健康控制中心 <ArrowUpRight size={18} />
            </button>
            <a className="secondary-action" href="#capabilities"><Play size={15} fill="currentColor" /> 查看识别能力</a>
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
          <button type="button" aria-label="健康告警" className={activeView === "alerts" ? "active" : ""} aria-current={activeView === "alerts" ? "page" : undefined} onClick={() => openView("alerts")}>
            <BellRing size={18} /> 健康告警 {!!dashboard?.open_alerts && <b>{dashboard.open_alerts}</b>}
          </button>
          <button type="button" className={activeView === "cattle" ? "active" : ""} aria-current={activeView === "cattle" ? "page" : undefined} onClick={() => openView("cattle")}><ShieldCheck size={18} /> 牛只档案</button>
          <button type="button" className={activeView === "analytics" ? "active" : ""} aria-current={activeView === "analytics" ? "page" : undefined} onClick={() => openView("analytics")}><ChartNoAxesCombined size={18} /> 数据分析</button>
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
              <RecognitionStudio />
            </section>
          )}

          {activeView === "alerts" && (
            <section className="focused-view alert-panel" id="alerts">
              <div className="panel-title"><div><p>风险筛查结果</p><h3>告警记录</h3></div><span>{alerts.length} 条</span></div>
              {renderAlertList("当前没有健康告警。")}
            </section>
          )}

          {activeView === "cattle" && (
            <section className="focused-view">
              <div className="view-intro"><ShieldCheck /><div><h3>个体记录</h3><p>根据当前告警记录汇总个体信息。</p></div></div>
              {dataError ? <p className="view-empty">档案数据暂不可用，请确认 API 已启动。</p> : cattleRecords.length === 0 ? <p className="view-empty">尚无可展示的牛只档案，完成追踪任务后会自动汇总。</p> : (
                <div className="record-grid">
                  {cattleRecords.map((cattleId) => {
                    const cattleAlerts = alerts.filter((alert) => alert.cattle_id === cattleId);
                    const latest = cattleAlerts[0];
                    return <article key={cattleId}><span>个体 ID</span><strong>牛 {cattleId}</strong><small>{cattleAlerts.length} 条告警 · 最新为{riskLabel[latest.level]}</small></article>;
                  })}
                </div>
              )}
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
            </section>
          )}
        </div>
      </section>
    </main>
  );
}
