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
import { useEffect, useState } from "react";
import {
  AlertRecord,
  Dashboard,
  fetchAlerts,
  fetchDashboard,
} from "./api";
import RecognitionStudio from "./RecognitionStudio";

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

export default function App() {
  const [workspaceVisible, setWorkspaceVisible] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [dataError, setDataError] = useState(false);
  const reduceMotion = useReducedMotion();
  const entrance = reduceMotion
    ? { initial: false as const, animate: {} }
    : { initial: { opacity: 0, y: 24, filter: "blur(10px)" }, animate: { opacity: 1, y: 0, filter: "blur(0px)" } };

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

  const modelReady = dashboard?.model_status === "ready";
  const dateLabel = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(new Date());

  return (
    <main className="app-shell">
      <section className="hero" aria-label="星牧智控欢迎页">
        <div className="hero-media" />
        <div className="hero-grid" />
        <nav className="floating-nav liquid-glass">
          <a className="brand" href="#top" aria-label="星牧智控首页">
            <span className="brand-mark"><CircleDot size={20} /></span>
            <span>星牧智控 <small>AgriNebula</small></span>
          </a>
          <div className="nav-links">
            <a href="#workspace">今日工作台</a>
            <a href="#capabilities">识别能力</a>
            <a href="#alerts">健康告警</a>
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
            <button className="primary-action" onClick={() => setWorkspaceVisible(true)}>
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
        <aside className="workspace-nav liquid-glass">
          <div className="mini-brand"><span className="brand-mark"><CircleDot size={18} /></span> AgriNebula</div>
          <button className="active"><Activity size={18} /> 今日工作台</button>
          <button><ScanSearch size={18} /> 实时监控</button>
          <button>
            <BellRing size={18} /> 健康告警
            {!!dashboard?.open_alerts && <b>{dashboard.open_alerts}</b>}
          </button>
          <button><ShieldCheck size={18} /> 牛只档案</button>
          <button><ChartNoAxesCombined size={18} /> 数据分析</button>
          <div className="system-card">
            <i /> {dataError ? "数据暂不可用" : modelReady ? "系统运行正常" : "正在连接服务"}
            <small>本地模式 · {modelReady ? "YOLO11 已加载" : "等待模型状态"}</small>
          </div>
        </aside>

        <div className="workspace-main">
          <header className="workspace-header">
            <div><p>{dateLabel}</p><h2>今日牧场健康概览</h2></div>
            <button
              className="plain-button"
              onClick={() => document.getElementById("recognition-studio")?.scrollIntoView()}
            >
              开始视频识别 <ArrowUpRight size={17} />
            </button>
          </header>
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
              <small>{modelReady ? "本地 YOLO11 + ByteTrack" : "未声称模型在线"}</small>
            </article>
          </div>
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
              <div className="panel-title"><div><p>需要关注</p><h3>最新健康告警</h3></div><button>查看全部</button></div>
              <div className="alert-list">
                {dataError && <p className="empty-alerts">数据暂不可用，请确认本地 API 已启动。</p>}
                {!dataError && alerts.length === 0 && (
                  <p className="empty-alerts">当前没有待处理健康告警。</p>
                )}
                {alerts.map((alert) => (
                  <button className="alert-row" key={alert.id}>
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
                ))}
              </div>
            </article>
          </div>
        </div>
      </section>
    </main>
  );
}
