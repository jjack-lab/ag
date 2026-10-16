# Inventory Video Evidence Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an operator open the completed video task bound to a historical pen inventory record from the global inventory view.

**Architecture:** `InventoryPanel` emits a job ID and displays loading/error state without owning navigation. `App` fetches and validates the video job, switches to the monitor view, and passes the selected job into `RecognitionStudio`, which renders it through the existing video result path.

**Tech Stack:** React 18, TypeScript, Testing Library, Vitest, existing FastAPI video job API.

---

### Task 1: Make the recognition studio accept an externally selected video job

**Files:**
- Modify: `web/src/RecognitionStudio.tsx`
- Create: `web/src/RecognitionStudio.external-job.test.tsx`

- [ ] **Step 1: Write the failing external-job test**

Create a completed `VideoJob`, render `<RecognitionStudio requestedJob={job} />`, and assert that the component enters video mode and renders the existing result player:

```tsx
it("renders a completed video job selected by its parent", async () => {
  render(<RecognitionStudio requestedJob={completedJob} />);
  expect(await screen.findByText("视频内 Track ID：3 个")).toBeInTheDocument();
  expect(screen.getByLabelText("牛只视频追踪结果")).toHaveAttribute(
    "src", "/media/results/job-1/cattle_tracked.mp4",
  );
});
```

Mock `/api/jobs/video`, `/api/jobs/job-1/reviews`, `/api/jobs/job-1/events`, `/api/jobs/job-1/corrections`, `/api/jobs/job-1/animal-links`, and `/api/inventory-checks` with empty arrays so the test exercises the real component tree.

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
$env:TEMP='F:\new大创\web\.vite\test-temp'; $env:TMP=$env:TEMP
npm test -- --run src/RecognitionStudio.external-job.test.tsx --maxWorkers=1
```

Expected: TypeScript/Vitest failure because `RecognitionStudio` has no `requestedJob` prop and does not render the supplied task.

- [ ] **Step 3: Implement the controlled entry point**

Add the prop and synchronize it through the existing result state:

```tsx
type Props = { requestedJob?: VideoJob | null };

export default function RecognitionStudio({ requestedJob = null }: Props) {
  // existing state
  useEffect(() => {
    if (!requestedJob) return;
    runToken.current += 1;
    setMode("video");
    setFile(null);
    setResult({ kind: "video", data: requestedJob });
    setStatus("idle");
    setMessage("已打开该盘点绑定的视频证据。");
  }, [requestedJob]);
```

Keep all existing result, review, correction, event, health graph, and inventory rendering paths unchanged.

- [ ] **Step 4: Run the focused test and commit**

Expected: the new test passes.

```powershell
git add web/src/RecognitionStudio.tsx web/src/RecognitionStudio.external-job.test.tsx
git commit -m "feat: open externally selected video jobs"
```

### Task 2: Connect inventory cards to the monitor workspace

**Files:**
- Modify: `web/src/InventoryPanel.tsx`
- Modify: `web/src/InventoryPanel.test.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/App.test.tsx`

- [ ] **Step 1: Write failing inventory callback tests**

Extend the inventory component test with a global-view record and callback:

```tsx
const onOpenVideo = vi.fn().mockResolvedValue(undefined);
render(<InventoryPanel onOpenVideo={onOpenVideo} />);
await user.click(await screen.findByRole("button", { name: "打开视频证据" }));
expect(onOpenVideo).toHaveBeenCalledWith("video-1");
```

Also render `<InventoryPanel selectedJob={job} onOpenVideo={onOpenVideo} />` and assert that the button is absent, so the embedded panel does not offer navigation to its current task.

- [ ] **Step 2: Write the failing application navigation tests**

In `App.test.tsx`, mock one inventory row, then mock `GET /api/jobs/video-1` with a completed task. Click “圈舍盘点” then “打开视频证据” and assert:

```tsx
expect(await screen.findByRole("heading", { name: "实时监控" })).toBeInTheDocument();
expect(screen.getByLabelText("牛只视频追踪结果")).toHaveAttribute(
  "src", "/media/results/video-1/cattle_tracked.mp4",
);
```

Add a second test returning a failed or incomplete task and assert that the inventory view remains active and displays “视频任务尚未完成，暂不能打开证据”.

- [ ] **Step 3: Run both tests and confirm RED**

Run:

```powershell
$env:TEMP='F:\new大创\web\.vite\test-temp'; $env:TMP=$env:TEMP
npm test -- --run src/InventoryPanel.test.tsx src/App.test.tsx --maxWorkers=1
```

Expected: failures because inventory cards have no evidence button and `App` does not load a job from inventory.

- [ ] **Step 4: Add the inventory navigation interface**

Use explicit props:

```tsx
type Props = {
  selectedJob?: VideoJob | null;
  onOpenVideo?: (jobId: string) => void;
  openingJobId?: string | null;
  videoOpenError?: string;
};
```

Render the error near the list and render this button only in the global view:

```tsx
{onOpenVideo && !selectedJob && (
  <button type="button" disabled={openingJobId === row.job_id}
    onClick={() => onOpenVideo(row.job_id)}>
    {openingJobId === row.job_id ? "正在打开…" : "打开视频证据"}
  </button>
)}
```

- [ ] **Step 5: Add application orchestration**

In `App`, add `requestedVideoJob`, `openingInventoryJobId`, `inventoryVideoError`, and an `inventoryOpenToken` ref so a slower earlier request cannot overwrite the last click. Implement:

```tsx
async function openInventoryVideo(jobId: string) {
  const token = inventoryOpenToken.current + 1;
  inventoryOpenToken.current = token;
  setOpeningInventoryJobId(jobId);
  setInventoryVideoError("");
  try {
    const job = await fetchVideoJob(jobId);
    if (inventoryOpenToken.current !== token) return;
    if (job.status !== "completed" || !job.result) {
      throw new Error("视频任务尚未完成，暂不能打开证据");
    }
    setRequestedVideoJob(job);
    openView("monitor", "recognition-studio");
  } catch (error) {
    if (inventoryOpenToken.current !== token) return;
    setInventoryVideoError(error instanceof Error ? error.message : "视频证据加载失败");
  } finally {
    if (inventoryOpenToken.current === token) setOpeningInventoryJobId(null);
  }
}
```

Pass these values to the global `InventoryPanel`, and render `<RecognitionStudio requestedJob={requestedVideoJob} />` in the monitor view. Keep the overview studio independent so a navigation request does not duplicate the selected result.

- [ ] **Step 6: Run focused tests and commit**

Expected: inventory callback, successful navigation, and failed navigation tests pass.

```powershell
git add web/src/InventoryPanel.tsx web/src/InventoryPanel.test.tsx web/src/App.tsx web/src/App.test.tsx
git commit -m "feat: open inventory video evidence"
```

### Task 3: Verify in the browser and hand off

**Files:**
- Modify: `README.md`
- Create: `docs/2026-10-16-inventory-video-navigation-acceptance.md`
- Modify: `HANDOFF.md`

- [ ] **Step 1: Run complete verification**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest -q -p no:cacheprovider --tb=line
cd web
$env:TEMP='F:\new大创\web\.vite\test-temp'; $env:TMP=$env:TEMP
npm test -- --run --maxWorkers=1
npm run build
```

Expected: all backend and frontend tests pass, and Vite production build exits 0.

- [ ] **Step 2: Restart the delivery services and perform read-only browser acceptance**

Restart with `AGRINEBULA_PYTHON=F:\deepl\anaconda1\envs\pytorch\python.exe`. Because the formal inventory list is currently empty, use an isolated SQLite backup containing one test inventory row bound to an existing completed cattle job. In Chrome, open “圈舍盘点”, click “打开视频证据”, and verify:

- the page switches to “实时监控”;
- the bound result player and video-local Track ID count are visible;
- the video, review, correction, event, and inventory requests correspond to the same `job_id`;
- the formal database still has zero inventory rows.

- [ ] **Step 3: Document and commit acceptance**

Record the tested job ID, isolated-data boundary, screenshot path, test totals, and remaining pagination limitation. Update README usage text. Commit:

```powershell
git add README.md docs/2026-10-16-inventory-video-navigation-acceptance.md
git commit -m "docs: verify inventory video navigation"
```

- [ ] **Step 4: Update and commit handoff separately**

Update all six relevant `HANDOFF.md` sections: current stage, completed, in progress, next step, decisions/pitfalls, and interruption point. Commit:

```powershell
git add HANDOFF.md
git commit -m "docs: hand off inventory video navigation"
```
