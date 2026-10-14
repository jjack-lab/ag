import { FormEvent, useEffect, useState } from "react";

import {
  AnimalLink,
  AnimalProfile,
  createAnimalLink,
  deleteAnimalLink,
  createAnimalFollowup,
  fetchAnimalLinks,
  fetchAnimalProfile,
  VideoJob,
} from "./api";
import AnimalTrend from "./AnimalTrend";

export default function AnimalIdentityPanel({ job }: { job: VideoJob }) {
  const [links, setLinks] = useState<AnimalLink[]>([]);
  const [trackId, setTrackId] = useState("");
  const [animalId, setAnimalId] = useState("");
  const [profile, setProfile] = useState<AnimalProfile | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [followupKind, setFollowupKind] = useState<"field_observation" | "veterinary_diagnosis">("field_observation");
  const [observedAt, setObservedAt] = useState("");
  const [followupNote, setFollowupNote] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [sourceReference, setSourceReference] = useState("");
  const tracks = job.result?.track_ids?.length
    ? job.result.track_ids
    : (job.result?.health_evidence || []).map((row) => row.track_id);

  useEffect(() => {
    let active = true;
    setLinks([]);
    setProfile(null);
    setTrackId("");
    fetchAnimalLinks(job.id)
      .then((rows) => { if (active && Array.isArray(rows)) setLinks(rows); })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "个体关联加载失败"); });
    return () => { active = false; };
  }, [job.id]);

  async function showProfile(id: string) {
    setError("");
    try {
      setProfile(await fetchAnimalProfile(id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "个体档案加载失败");
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (trackId === "" || !animalId.trim()) return;
    setSaving(true);
    setError("");
    try {
      const link = await createAnimalLink(job.id, Number(trackId), animalId.trim());
      setLinks((rows) => [...rows.filter((row) => row.track_id !== link.track_id), link]);
      await showProfile(link.animal_id);
      setAnimalId("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "关联失败");
    } finally {
      setSaving(false);
    }
  }

  async function submitFollowup(event: FormEvent) {
    event.preventDefault();
    if (!profile || !observedAt || !followupNote.trim()) return;
    setSaving(true);
    setError("");
    try {
      const saved = await createAnimalFollowup(profile.animal_id, {
        kind: followupKind,
        observed_at: observedAt,
        note: followupNote.trim(),
        diagnosis: followupKind === "veterinary_diagnosis" ? diagnosis.trim() : null,
        source_reference: followupKind === "veterinary_diagnosis" ? sourceReference.trim() : null,
      });
      setProfile((current) => current ? { ...current, followups: [...(current.followups || []), saved] } : current);
      setFollowupNote("");
      setDiagnosis("");
      setSourceReference("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "回访记录保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function unlink(track: number) {
    setError("");
    try {
      await deleteAnimalLink(job.id, track);
      setLinks((rows) => rows.filter((row) => row.track_id !== track));
      setProfile(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "解除关联失败");
    }
  }

  return <section className="animal-identity-panel" aria-label="跨视频个体档案">
    <h4>跨视频个体档案</h4>
    <p>现场核对耳标或登记号后，将视频内 Track ID 关联到同一个稳定编号；系统不会自动判断两段视频是否为同一只动物。</p>
    {tracks.length > 0 ? <form onSubmit={submit}>
      <label>视频内 Track ID
        <select value={trackId} required onChange={(event) => setTrackId(event.target.value)}>
          <option value="">选择 ID</option>
          {tracks.map((id) => <option key={id} value={id}>{id}</option>)}
        </select>
      </label>
      <label>耳标或稳定个体编号
        <input value={animalId} maxLength={40} required onChange={(event) => setAnimalId(event.target.value)} placeholder="例如 C-023" />
      </label>
      <button type="submit" disabled={saving || trackId === "" || !animalId.trim()}>{saving ? "关联中…" : "确认关联"}</button>
    </form> : <p>本次结果没有可关联的 Track ID。</p>}
    {error && <p role="alert">{error}</p>}
    {links.map((link) => <div key={link.track_id} className="animal-link-actions">
      <button className="animal-link-row" type="button" onClick={() => showProfile(link.animal_id)}>
        视频内 ID {link.track_id} → {link.animal_id} · 查看档案
      </button>
      <button type="button" onClick={() => unlink(link.track_id)} aria-label={`解除视频内 ID ${link.track_id} 的关联`}>解除关联</button>
    </div>)}
    {profile && <div className="animal-profile">
      <strong>{profile.animal_id} · {profile.species === "sheep" ? "羊" : "牛"} · {profile.visits.length} 次视频记录</strong>
      <AnimalTrend profile={profile} />
      {profile.visits.map((visit) => <article key={`${visit.job_id}:${visit.track_id}`}>
        <span>{new Date(visit.recorded_at).toLocaleString("zh-CN")} · 视频内 ID {visit.track_id}</span>
        {visit.health_evidence
          ? <small>规则风险分 {visit.health_evidence.risk_score} · {visit.health_evidence.observations?.length || 0} 条观察证据</small>
          : <small>仅有检测追踪记录，暂无经验证的健康评分</small>}
        <small>人工复核 {visit.reviews.length} 条</small>
      </article>)}
      <h4>现场回访与诊疗记录</h4>
      <p>这里保存人工录入的信息，尚未核验来源；不会据此自动生成疾病预测。</p>
      {(profile.followups || []).map((followup) => <article key={followup.id}>
        <strong>{followup.kind === "veterinary_diagnosis" ? "录入的兽医结论" : "现场观察"} · {followup.observed_at}</strong>
        <span>{followup.note}</span>
        {followup.diagnosis && <small>录入诊断：{followup.diagnosis} · 来源：{followup.source_reference}</small>}
        <small>来源状态：用户录入，未独立核验</small>
      </article>)}
      <form onSubmit={submitFollowup}>
        <label>回访类型
          <select value={followupKind} onChange={(event) => setFollowupKind(event.target.value as typeof followupKind)}>
            <option value="field_observation">现场观察</option>
            <option value="veterinary_diagnosis">兽医结论记录</option>
          </select>
        </label>
        <label>回访日期
          <input type="date" required value={observedAt} onChange={(event) => setObservedAt(event.target.value)} />
        </label>
        <label>回访说明
          <input required maxLength={1000} value={followupNote} onChange={(event) => setFollowupNote(event.target.value)} />
        </label>
        {followupKind === "veterinary_diagnosis" && <>
          <label>兽医诊断
            <input required maxLength={200} value={diagnosis} onChange={(event) => setDiagnosis(event.target.value)} />
          </label>
          <label>诊疗记录出处
            <input required maxLength={300} value={sourceReference} onChange={(event) => setSourceReference(event.target.value)} />
          </label>
        </>}
        <button type="submit" disabled={saving || !observedAt || !followupNote.trim()}>{saving ? "保存中…" : "保存回访记录"}</button>
      </form>
    </div>}
  </section>;
}
