import { useEffect, useRef, useState } from "react";
import { fetchAnimals, fetchAnimalProfile, type AnimalDirectoryRow, type AnimalProfile } from "./api";
import AnimalProfileView from "./AnimalProfileView";

export default function AnimalDirectory({ onOpenVideo }: { onOpenVideo: (id: string) => void }) {
  const [rows, setRows] = useState<AnimalDirectoryRow[]>([]);
  const [query, setQuery] = useState("");
  const [species, setSpecies] = useState("");
  const [profile, setProfile] = useState<AnimalProfile | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const profileRequest = useRef(0);
  useEffect(() => {
    let active = true; setLoading(true); setError("");
    fetchAnimals(query, species).then((data) => { if (active) setRows(data); })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "目录加载失败"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [query, species]);
  useEffect(() => { profileRequest.current += 1; setProfile(null); }, [query, species]);
  useEffect(() => () => { profileRequest.current += 1; }, []);
  async function open(id: string) {
    const token = ++profileRequest.current;
    setError(""); setProfile(null);
    try { const data = await fetchAnimalProfile(id); if (token === profileRequest.current) setProfile(data); }
    catch (cause) { if (token === profileRequest.current) setError(cause instanceof Error ? cause.message : "档案加载失败"); }
  }
  return <section className="workspace-feature" aria-label="个体档案目录">
    <header><span className="feature-eyebrow">ANIMAL RECORDS / 个体档案</span><h3>每一个编号，都有迹可循。</h3><p>跨视频记录由现场人员核对耳标后人工关联。视频内 Track ID 不能直接作为牛只档案编号。请在视频识别结果中建立首次关联。</p></header>
    <div className="feature-toolbar"><label>搜索个体编号<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="输入耳标或稳定编号" /></label><label>动物种类<select value={species} onChange={(e) => setSpecies(e.target.value)}><option value="">全部</option><option value="cattle">牛</option><option value="sheep">羊</option></select></label></div>
    {error && <p role="alert">{error}</p>}
    {loading ? <p>正在加载档案…</p> : <p>共 {rows.length} 份已关联档案</p>}
    {!loading && !rows.length && <p>暂无符合条件的档案。<a href="#/module/monitor">前往视频结果核对并关联个体</a></p>}
    <div className="feature-card-grid">{rows.map((row) => <button type="button" className={`record-card ${profile?.animal_id === row.animal_id ? "selected" : ""}`} key={row.animal_id} onClick={() => open(row.animal_id)}>
      <small>{row.animal_id.startsWith("DEMO-") ? "模拟数据 · 未经现场核实" : `${row.species === "sheep" ? "羊" : "牛"} · 稳定编号`}</small><strong>{row.animal_id}</strong><span>{row.video_count} 次视频 · {row.followup_count} 条回访</span><small>最近视频 {new Date(row.last_seen).toLocaleDateString("zh-CN")}</small>
    </button>)}</div>
    {profile && <AnimalProfileView key={profile.animal_id} profile={profile} onUpdated={(next) => { setProfile((current) => current?.animal_id === next.animal_id ? next : current); setRows((items) => items.map((row) => row.animal_id === next.animal_id ? { ...row, followup_count: next.followups.length } : row)); }} onOpenVideo={onOpenVideo} />}
  </section>;
}
