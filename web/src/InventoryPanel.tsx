import { FormEvent, useEffect, useState } from "react";
import { createInventoryCheck, createInventoryRecheck, fetchInventoryChecks, fetchInventoryPage,
  type InventoryCheck, type InventoryRecheck, type VideoJob } from "./api";

const pageSize = 20;

const statusLabel: Record<InventoryCheck["status"], string> = {
  coverage_needed: "覆盖不足：先补拍并重新盘点",
  count_needed: "覆盖完整，待人工清点",
  preliminary_match: "数量初步相符，待复核",
  discrepancy_pending: "数量有差额，待复点",
  verified_match: "人工复点相符",
  shortfall_pending: "复点仍有差额，继续核查",
  surplus_pending: "复点数量超出登记，核查台账",
  loss_user_recorded: "人工登记丢失",
};

type Props = {
  selectedJob?: VideoJob | null;
  onOpenVideo?: (jobId: string) => void;
  openingJobId?: string | null;
  videoOpenError?: string;
};

export default function InventoryPanel({
  selectedJob,
  onOpenVideo,
  openingJobId,
  videoOpenError,
}: Props) {
  const [checks, setChecks] = useState<InventoryCheck[]>([]);
  const [penFilter, setPenFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pen, setPen] = useState("");
  const [expected, setExpected] = useState("");
  const [source, setSource] = useState("");
  const [observed, setObserved] = useState("");
  const [coverage, setCoverage] = useState<InventoryCheck["coverage"]>("unknown");
  const [coverageNote, setCoverageNote] = useState("");
  const [operator, setOperator] = useState("");
  const [recheckId, setRecheckId] = useState<string | null>(null);
  const [counted, setCounted] = useState("");
  const [outcome, setOutcome] = useState<InventoryRecheck["outcome"]>("shortfall_pending");
  const [lost, setLost] = useState("");
  const [movement, setMovement] = useState(false);
  const [field, setField] = useState(false);
  const [rechecker, setRechecker] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    let active = true;
    setChecks([]);
    setTotal(0);
    setError("");
    setLoading(true);
    const request = selectedJob
      ? fetchInventoryChecks(selectedJob.id).then((rows) => {
          if (!Array.isArray(rows)) throw new Error("盘点记录响应格式无效");
          return { items: rows, total: rows.length };
        })
      : fetchInventoryPage({ limit: pageSize, offset, penId: penFilter.trim(), status: statusFilter });
    request.then((page) => {
      if (!Array.isArray(page.items) || !Number.isInteger(page.total) || page.total < 0) {
        throw new Error("盘点记录响应格式无效");
      }
      if (active) { setChecks(page.items); setTotal(page.total); }
    }).catch((cause) => { if (active) setError(String(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selectedJob, penFilter, statusFilter, offset, refreshKey]);

  const selectedChecks = selectedJob
    ? checks.filter((row) => row.job_id === selectedJob.id)
    : checks;
  const ready = selectedJob?.status === "completed" && !!selectedJob.result;

  async function saveCheck(event: FormEvent) {
    event.preventDefault();
    if (!ready || !selectedJob) return;
    setBusy(true); setError("");
    try {
      const row = await createInventoryCheck({
        job_id: selectedJob.id, pen_id: pen.trim(), expected_count: Number(expected),
        baseline_source: source.trim(), observed_count: observed === "" ? null : Number(observed),
        coverage, coverage_note: coverageNote.trim(), operator_name: operator.trim(),
        observed_at: new Date().toISOString(),
      });
      setChecks((old) => [row, ...old.filter((item) => item.id !== row.id)]);
      setPen(""); setExpected(""); setSource(""); setObserved(""); setCoverage("unknown");
      setCoverageNote(""); setOperator("");
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  }

  async function saveRecheck(event: FormEvent) {
    event.preventDefault();
    if (!recheckId) return;
    setBusy(true); setError("");
    try {
      const row = await createInventoryRecheck(recheckId, {
        counted_count: Number(counted), outcome, lost_count: outcome === "loss_user_recorded" ? Number(lost) : null,
        movement_records_checked: movement, field_search_complete: field,
        operator_name: rechecker.trim(), note: note.trim(),
      });
      if (selectedJob) setChecks((old) => old.map((item) => item.id === row.id ? row : item));
      else setRefreshKey((value) => value + 1);
      setRecheckId(null); setCounted(""); setLost(""); setMovement(false); setField(false);
      setRechecker(""); setNote("");
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  }

  const lossValid = outcome !== "loss_user_recorded" ||
    (Number(lost) >= 1 && movement && field);
  const recheckReady = counted !== "" && rechecker.trim() && note.trim() && lossValid;

  return <section className="inventory-panel" aria-label="圈舍存栏核对">
    <header><div><h3>圈舍存栏核对</h3><p>登记数与人工清点数核对，差额先由现场复点。</p></div></header>
    <p className="inventory-disclaimer">视频内 Track ID 仅供定位画面，不能作为存栏数或永久身份；此处结论均为人工记录。</p>
    {error && <p role="alert">{error}</p>}
    {ready && <form onSubmit={saveCheck}>
      <label>圈舍编号<input required value={pen} onChange={(e) => setPen(e.target.value)} /></label>
      <label>登记存栏数<input required type="number" min="0" value={expected} onChange={(e) => setExpected(e.target.value)} /></label>
      <label>登记来源<input required value={source} onChange={(e) => setSource(e.target.value)} /></label>
      <label>人工清点数<input type="number" min="0" value={observed} onChange={(e) => setObserved(e.target.value)} placeholder="未清点可留空，0 表示确认清点为零" /></label>
      <label>拍摄覆盖<select value={coverage} onChange={(e) => setCoverage(e.target.value as InventoryCheck["coverage"])}>
        <option value="unknown">未确认</option><option value="partial">部分覆盖</option><option value="complete">完整覆盖</option>
      </select></label>
      <label>覆盖说明<input required value={coverageNote} onChange={(e) => setCoverageNote(e.target.value)} /></label>
      <label>操作人<input required value={operator} onChange={(e) => setOperator(e.target.value)} /></label>
      <button disabled={busy}>保存盘点</button>
    </form>}
    {!ready && <p>打开一段已完成的视频后可建立盘点记录。</p>}
    {videoOpenError && <p role="alert">{videoOpenError}</p>}
    {!selectedJob && <div className="inventory-history-controls">
      <label>筛选圈舍编号<input value={penFilter} onChange={(event) => {
        setPenFilter(event.target.value); setOffset(0);
      }} /></label>
      <label>筛选盘点状态<select value={statusFilter} onChange={(event) => {
        setStatusFilter(event.target.value); setOffset(0);
      }}>
        <option value="">全部状态</option>
        {Object.entries(statusLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
    </div>}
    <div className="inventory-list">
      {!loading && !error && selectedChecks.length === 0 && <p>暂无盘点记录。</p>}
      {selectedChecks.map((row) => <article key={row.id}>
        <h4>{row.pen_id} · {row.species === "sheep" ? "羊" : "牛"}</h4>
        <p>登记 {row.expected_count}，人工清点 {row.current_count ?? "未填"}；视频内 Track ID {row.video_track_count ?? "未知"} 个（仅参考）。</p>
        <p>{row.status === "discrepancy_pending" && row.difference !== null
          ? `差额 ${Math.abs(row.difference)}，待复点` : statusLabel[row.status]}</p>
        {row.status === "loss_user_recorded" && <p>人工登记丢失 {row.lost_count}；记录人和核查过程见复核记录。</p>}
        <small>登记来源：{row.baseline_source}；覆盖：{row.coverage_note}；操作人：{row.operator_name}</small>
        {row.rechecks.map((item) => <small key={item.id}>复核：{item.operator_name}，{item.note}</small>)}
        {onOpenVideo && !selectedJob && <button type="button"
          disabled={openingJobId === row.job_id} onClick={() => onOpenVideo(row.job_id)}>
          {openingJobId === row.job_id ? "正在打开…" : "打开视频证据"}
        </button>}
        {row.coverage === "complete" && row.observed_count !== null && <button type="button" onClick={() => setRecheckId(recheckId === row.id ? null : row.id)}>填写人工复核</button>}
        {recheckId === row.id && <form onSubmit={saveRecheck}>
          <label>复点数量<input type="number" min="0" required value={counted} onChange={(e) => setCounted(e.target.value)} /></label>
          <label>复核结论<select value={outcome} onChange={(e) => setOutcome(e.target.value as InventoryRecheck["outcome"])}>
            <option value="shortfall_pending">数量仍少，继续核查</option>
            <option value="surplus_pending">数量超出登记</option>
            <option value="resolved">数量相符</option>
            <option value="loss_user_recorded">人工登记丢失</option>
          </select></label>
          {outcome === "loss_user_recorded" && <>
            <label>人工登记丢失数量<input type="number" min="1" required value={lost} onChange={(e) => setLost(e.target.value)} /></label>
            <label className="inventory-check"><input type="checkbox" checked={movement} onChange={(e) => setMovement(e.target.checked)} />已核对出入栏记录</label>
            <label className="inventory-check"><input type="checkbox" checked={field} onChange={(e) => setField(e.target.checked)} />已完成现场查找</label>
          </>}
          <label>复核操作人<input required value={rechecker} onChange={(e) => setRechecker(e.target.value)} /></label>
          <label>复核说明<input required value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <button disabled={busy || !recheckReady}>保存复核</button>
        </form>}
      </article>)}
    </div>
    {!selectedJob && <div className="inventory-history-pagination">
      <p>{`第 ${Math.floor(offset / pageSize) + 1} / ${Math.max(1, Math.ceil(total / pageSize))} 页 · 共 ${total} 条`}</p>
      <button type="button" disabled={loading || offset === 0} onClick={() => setOffset((value) => value - pageSize)}>上一页</button>
      <button type="button" disabled={loading || offset + pageSize >= total} onClick={() => setOffset((value) => value + pageSize)}>下一页</button>
    </div>}
  </section>;
}
