import { useEffect, useState, type FormEvent } from "react";
import { fetchAnalytics, statisticsQuery, fetchSpatialHistory, type WorkspaceStatistics, type SpatialReport } from "./api";

export default function WorkspaceAnalytics({ onOpenVideo }: { onOpenVideo: (id: string) => void }) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [range, setRange] = useState({ start: "", end: "", revision: 0 });
  const [data, setData] = useState<WorkspaceStatistics | null>(null);
  const [error, setError] = useState("");
  const [pen, setPen] = useState("");
  const [camera, setCamera] = useState("");
  const [kind, setKind] = useState<SpatialReport["kind"]>("feeding");
  const [history, setHistory] = useState<SpatialReport[]>([]);
  const [spatialError, setSpatialError] = useState("");
  const [searched, setSearched] = useState(false);
  useEffect(() => {
    let active = true; setError(""); setData(null);
    fetchAnalytics(range.start, range.end).then((rows) => { if (active) setData(rows); })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "统计加载失败"); });
    return () => { active = false; };
  }, [range]);
  async function searchSpatial(event: FormEvent) {
    event.preventDefault(); setSpatialError(""); setHistory([]); setSearched(false);
    try { setHistory(await fetchSpatialHistory(pen.trim(), camera.trim(), kind)); setSearched(true); }
    catch (cause) { setSpatialError(cause instanceof Error ? cause.message : "空间统计加载失败"); }
  }
  const totals = data?.totals;
  const peak = Math.max(1, ...((data?.daily || []).map((row) => row.videos)));
  return <section className="workspace-feature" aria-label="历史数据分析">
    <header><span className="feature-eyebrow">ACTIVITY ANALYTICS / 运行分析</span><h3>用记录，观察变化。</h3><p>按北京时间自然日统计完整历史。视频按创建日期，告警按发生日期，处理按实际处理日期汇总。</p></header>
    <form className="feature-toolbar" onSubmit={(e) => { e.preventDefault(); setRange({ start, end, revision: range.revision + 1 }); }}>
      <label>开始日期<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label><label>结束日期<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label><button>查询统计</button>
      {data && <a className="feature-link" href={`/api/analytics.csv${statisticsQuery(range.start, range.end)}`} download>导出统计 CSV</a>}
    </form>
    {error && <p role="alert">{error}</p>}
    {!data && !error && <p>正在汇总历史记录…</p>}
    {totals && <div className="feature-card-grid kpi-cards">{[
      ["视频任务", totals.videos], ["完成视频", totals.completed_videos], ["牛视频 / 羊视频", `${totals.cattle_videos || 0} / ${totals.sheep_videos || 0}`],
      ["规则提示", totals.alerts], ["已处理提示", totals.resolved_alerts], ["新建 / 关闭事项", `${totals.tasks_created || 0} / ${totals.tasks_closed || 0}`],
    ].map(([label, value]) => <article key={label}><span>{label}</span><strong>{value ?? 0}</strong></article>)}</div>}
    {data && !data.daily.length && <p>暂无此日期范围内的统计记录。</p>}
    {!!data?.daily.length && <><div className="history-chart" aria-label="每日视频任务数量">{data.daily.map((row) => <div key={row.date}><span>{row.date}</span><i style={{ width: `${row.videos / peak * 100}%` }} /><b>{row.videos} 段</b></div>)}</div>
      <div className="feature-table-scroll"><table><caption>每日任务、告警与处置记录</caption><thead><tr><th>日期</th><th>视频</th><th>完成</th><th>失败</th><th>新告警</th><th>处理告警</th><th>新事项</th><th>关闭事项</th></tr></thead><tbody>{data.daily.map((row) => <tr key={row.date}><td>{row.date}</td><td>{row.videos}</td><td>{row.completed_videos}</td><td>{row.failed_videos}</td><td>{row.alerts}</td><td>{row.resolved_alerts}</td><td>{row.tasks_created}</td><td>{row.tasks_closed}</td></tr>)}</tbody></table></div></>}
    <section className="spatial-history-query"><h4>固定机位的区域与栏门记录</h4><p>按圈舍、机位和类型查看已保存的统计；画区不同的视频应分别核对，短片不推算多日趋势。</p>
      <form className="feature-toolbar" onSubmit={searchSpatial}><label>圈舍编号<input required value={pen} onChange={(e) => setPen(e.target.value)} /></label><label>机位编号<input required value={camera} onChange={(e) => setCamera(e.target.value)} /></label><label>观察类型<select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}><option value="feeding">采食附近观察区</option><option value="water">饮水附近观察区</option><option value="gate">栏门穿线</option></select></label><button>查询机位记录</button></form>
      {spatialError && <p role="alert">{spatialError}</p>}{searched && !history.length && <p>该机位尚无此类统计。请先在视频结果中画区或画线。</p>}
      {history.map((row) => <article className="feature-record" key={`${row.job_id}:${row.kind}`}><strong>{new Date(row.observed_at).toLocaleString("zh-CN")}</strong><p>{row.kind === "gate" ? `自动进入 ${row.metrics.enter ?? 0} / 自动离开 ${row.metrics.leave ?? 0} 次` : `自动进入 ${row.metrics.entries ?? 0} 次 / 停留 ${(row.metrics.dwell_seconds ?? 0).toFixed(1)} 秒`} · 视频 {row.duration_seconds.toFixed(1)} 秒</p><small>画区/画线坐标：{row.geometry.join(", ")} · 需人工核对</small><button type="button" onClick={() => onOpenVideo(row.job_id)}>回看与核对</button></article>)}
    </section>
  </section>;
}
