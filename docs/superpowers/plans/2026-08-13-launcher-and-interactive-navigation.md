# Launcher and Interactive Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide double-click Windows launch/stop entry points and make every visible application control produce a useful, testable response.

**Architecture:** Keep process management in the existing PowerShell scripts and use thin BAT wrappers for discoverability. Add a typed view state to the React application, render focused single-page panels from existing dashboard/alert data, and expose alert details without inventing backend APIs.

**Tech Stack:** Windows Batch and PowerShell 5+, React 19, TypeScript, Vitest, Testing Library, Vite, FastAPI/Pytest.

---

## File map

- Create `启动项目.bat`: validate the known Python, call `start_delivery.ps1`, open the web UI, and preserve failures.
- Create `停止项目.bat`: call `stop_delivery.ps1` and report the result.
- Modify `delivery_tests/test_startup_script.py`: enforce BAT wrapper contracts without launching services.
- Modify `web/src/App.tsx`: own the active view and selected alert state; connect all navigation buttons.
- Modify `web/src/styles.css`: style active navigation, focused panels, detail/empty states, and keyboard focus.
- Modify `web/src/App.test.tsx`: verify navigation, full alert view, alert detail toggling, and action focus.
- Modify `README.md`: document double-click launch and stop.

### Task 1: BAT launcher contracts

**Files:**
- Create: `启动项目.bat`
- Create: `停止项目.bat`
- Modify: `delivery_tests/test_startup_script.py`

- [ ] **Step 1: Write failing BAT contract tests**

Add tests that decode BAT files with UTF-8 and require these observable strings:

```python
def test_double_click_launcher_delegates_to_verified_delivery_script(project_root):
    text = (project_root / "启动项目.bat").read_text(encoding="utf-8")
    assert "set \"AGRINEBULA_PYTHON=F:\\deepl\\anaconda1\\envs\\pytorch\\python.exe\"" in text
    assert "start_delivery.ps1" in text
    assert "http://127.0.0.1:5173" in text
    assert "if errorlevel 1" in text.lower()

def test_double_click_stop_wrapper_delegates_to_stop_script(project_root):
    text = (project_root / "停止项目.bat").read_text(encoding="utf-8")
    assert "stop_delivery.ps1" in text
    assert "if errorlevel 1" in text.lower()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `F:\deepl\anaconda1\envs\pytorch\python.exe -m pytest delivery_tests/test_startup_script.py -q`

Expected: FAIL because both BAT files do not exist.

- [ ] **Step 3: Implement thin BAT wrappers**

`启动项目.bat` must change to `%~dp0`, check the Python path, invoke PowerShell, propagate failure, open the UI only after success, and print the manual URL. `停止项目.bat` must change to `%~dp0`, invoke the stop script, propagate failure, and pause so double-click users can see the outcome.

- [ ] **Step 4: Run tests and verify GREEN**

Run the same targeted Pytest command. Expected: all startup-script tests pass.

- [ ] **Step 5: Commit launcher files and tests**

```powershell
git add -- '启动项目.bat' '停止项目.bat' 'delivery_tests/test_startup_script.py'
git commit -m "feat: add double-click delivery launchers"
```

### Task 2: Interactive single-page navigation

**Files:**
- Modify: `web/src/App.test.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/styles.css`

- [ ] **Step 1: Write failing view-switching tests**

Add tests using accessible roles:

```tsx
it("switches every operator navigation button to a focused view", async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole("button", { name: "牛只档案" }));
  expect(screen.getByRole("heading", { name: "牛只档案" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "牛只档案" })).toHaveAttribute("aria-current", "page");
  await user.click(screen.getByRole("button", { name: "数据分析" }));
  expect(screen.getByRole("heading", { name: "数据分析" })).toBeInTheDocument();
});

it("opens the full alerts view from 查看全部", async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole("button", { name: "查看全部" }));
  expect(screen.getByRole("heading", { name: "全部健康告警" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `npm test -- --run web/src/App.test.tsx` from `web` (or `npm test -- --run src/App.test.tsx` when Vite resolves from the web directory).

Expected: FAIL because sidebar buttons and `查看全部` do not change views.

- [ ] **Step 3: Implement typed view state and panel rendering**

Define `type WorkspaceView = "overview" | "monitor" | "alerts" | "cattle" | "analytics";`, add a single `openView(view)` handler, set `aria-current="page"` on the active navigation button, and render:

- Overview: existing metrics, recognition studio, monitor placeholder, and alert summary.
- Monitor: recognition studio plus a clear camera-input placeholder.
- Alerts: complete fetched alert list with heading `全部健康告警`.
- Cattle: unique cattle IDs derived from alerts, risk count and latest status; explicit empty state when no records exist.
- Analytics: monitored, high-risk, and open-alert counts plus high/medium/low alert distribution.

The “进入健康控制中心” button opens overview and scrolls to `#workspace`; “开始视频识别” opens monitor and scrolls to `#recognition-studio`; “查看全部” opens alerts.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run the targeted Vitest command. Expected: navigation tests and existing tests pass.

- [ ] **Step 5: Commit navigation behavior**

```powershell
git add -- 'web/src/App.tsx' 'web/src/App.test.tsx' 'web/src/styles.css'
git commit -m "feat: connect workspace navigation actions"
```

### Task 3: Alert detail interaction and button semantics

**Files:**
- Modify: `web/src/App.test.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/styles.css`

- [ ] **Step 1: Write failing alert-detail test**

```tsx
it("toggles actionable alert details", async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("button", { name: /牛 7.*持续低活动/ }));
  expect(screen.getByText("现场复核")).toBeInTheDocument();
  expect(screen.getByText("置信度 90%")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /牛 7.*持续低活动/ }));
  expect(screen.queryByText("现场复核")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests and verify RED**

Run the targeted Vitest command. Expected: FAIL because alert rows have no click handler or detail content.

- [ ] **Step 3: Implement details and button semantics**

Track `selectedAlertId: string | null`; set `aria-expanded` on alert rows; render suggestion, formatted timestamp, and rounded confidence below the selected row. Add `type="button"` to every non-submit button and preserve disabled processing state only on recognition submission.

- [ ] **Step 4: Run tests and verify GREEN**

Run targeted Vitest. Expected: all application tests pass.

- [ ] **Step 5: Commit alert interaction**

```powershell
git add -- 'web/src/App.tsx' 'web/src/App.test.tsx' 'web/src/styles.css'
git commit -m "feat: add actionable health alert details"
```

### Task 4: Documentation and full verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document double-click usage**

Add a Windows section stating that users can double-click `启动项目.bat`, browse to `http://127.0.0.1:5173`, and double-click `停止项目.bat` when finished. Retain the PowerShell commands for diagnosis.

- [ ] **Step 2: Run complete automated verification**

```powershell
F:\deepl\anaconda1\envs\pytorch\python.exe -m pytest -q
Set-Location .\web
npm test -- --run
npm run build
```

Expected: zero test failures and production build exit code 0.

- [ ] **Step 3: Run launcher and service acceptance**

Stop the currently running project, invoke `启动项目.bat` through `cmd.exe /c`, verify `/api/health` returns `status=ok` and the web root returns HTTP 200, then invoke `停止项目.bat` through `cmd.exe /c` and verify ports 8000/5173 are free.

- [ ] **Step 4: Run browser interaction acceptance**

Open the local UI and activate every header link, primary/secondary action, sidebar button, alert action, recognition tab, parameter input/select, upload input, recognition submit path, and available result/report/download link. Confirm each changes view, focus, state, content, or navigation as designed. Record any unavailable result links as conditional on completing a recognition job, then execute a real image recognition to expose and test the image result.

- [ ] **Step 5: Commit documentation**

```powershell
git add -- README.md
git commit -m "docs: add double-click launch instructions"
```

- [ ] **Step 6: Final repository audit**

Run `git status --short` and `git log -5 --oneline`. Expected: only the ignored/untracked runtime state file may remain; no implementation file is uncommitted.
