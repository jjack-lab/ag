import { useState, type FormEvent } from "react";
import { createAnimalFollowup, type AnimalProfile } from "./api";
import AnimalTrend from "./AnimalTrend";

export default function AnimalProfileView({ profile, onUpdated, onOpenVideo }: {
  profile: AnimalProfile; onUpdated: (profile: AnimalProfile) => void;
  onOpenVideo?: (id: string) => void;
}) {
  const [kind, setKind] = useState<"field_observation" | "veterinary_diagnosis">("field_observation");
  const [observedAt, setObservedAt] = useState(() => new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai" }).format(new Date()));
  const [note, setNote] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [source, setSource] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const saved = await createAnimalFollowup(profile.animal_id, { kind, observed_at: observedAt,
        note: note.trim(), diagnosis: kind === "veterinary_diagnosis" ? diagnosis.trim() : null,
        source_reference: kind === "veterinary_diagnosis" ? source.trim() : null });
      onUpdated({ ...profile, followups: [...(profile.followups || []), saved] });
      setNote(""); setDiagnosis(""); setSource("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "保存失败"); }
    finally { setSaving(false); }
  }
  return <section className="animal-profile" aria-label="个体档案详情">
    <h3>{profile.animal_id} · {profile.species === "sheep" ? "羊" : "牛"}</h3>
    {profile.animal_id.startsWith("DEMO-") && <p>模拟数据，仅供界面演示；个体身份与现场情况未经核实。</p>}
    <AnimalTrend profile={profile} />
    <h4>视频与人工核查</h4>
    {profile.visits.map((visit) => <article key={`${visit.job_id}:${visit.track_id}`}>
      <strong>{new Date(visit.recorded_at).toLocaleString("zh-CN")} · 视频内 ID {visit.track_id}</strong>
      <small>{visit.health_evidence ? `规则风险分 ${visit.health_evidence.risk_score}` : "暂无经验证的健康评分"} · 人工复核 {visit.reviews.length} 条</small>
      {onOpenVideo && <button type="button" onClick={() => onOpenVideo(visit.job_id)}>打开视频证据</button>}
    </article>)}
    <h4>现场回访与诊疗记录</h4>
    <p>以下记录由人员录入，来源尚未独立核验。</p>
    {(profile.followups || []).map((row) => <article key={row.id}>
      <strong>{row.observed_at} · {row.kind === "veterinary_diagnosis" ? "兽医结论记录" : "现场观察"}</strong>
      <span>{row.note}</span>{row.diagnosis && <small>{row.diagnosis} · 来源：{row.source_reference}</small>}
    </article>)}
    <form onSubmit={save}>
      <label>回访类型<select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}><option value="field_observation">现场观察</option><option value="veterinary_diagnosis">兽医结论记录</option></select></label>
      <label>回访日期<input type="date" required value={observedAt} onChange={(e) => setObservedAt(e.target.value)} /></label>
      <label>回访说明<textarea required maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} /></label>
      {kind === "veterinary_diagnosis" && <><label>兽医诊断<input required maxLength={200} value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} /></label><label>诊疗记录出处<input required maxLength={300} value={source} onChange={(e) => setSource(e.target.value)} /></label></>}
      <button disabled={saving}>{saving ? "保存中…" : "保存回访记录"}</button>
    </form>{error && <p role="alert">{error}</p>}
  </section>;
}
