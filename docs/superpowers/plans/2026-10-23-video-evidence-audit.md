# Video Evidence Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make uploaded-video zone and gate events reviewable against human observations and report measured error without treating video counts as herd inventory.

**Architecture:** Spatial analysis emits individual zone entries and gate crossings. A job-local audit JSON stores verdicts for the current report revision, plus human-added missed events. The API returns an audit summary; the React panel shows the event list and mobile-friendly review controls.

**Tech Stack:** Python, FastAPI, pytest, React, TypeScript, Vitest.

---

### Task 1: Emit zone-entry evidence

**Files:** `cattle_health_app/spatial_analysis.py`, `tests/test_spatial_analysis.py`.

- [x] Add a failing test that calls `zone_activity` with two tracks entering and leaving a rectangle, then checks `metrics.events` contains `track_id`, `time_seconds`, and `dwell_seconds` for each entry.
- [x] Run `python -m pytest -q tests/test_spatial_analysis.py::test_zone_entry_events_include_dwell`; confirm it fails because `events` is absent.
- [x] Extend `zone_activity` to open an event when an observed track enters, add observed frame durations while inside, and close the event on exit or end of track. Preserve existing total and hourly metrics.
- [x] Rerun `tests/test_spatial_analysis.py`; commit `feat: expose zone entry events for review`.

### Task 2: Persist verdicts and missed events

**Files:** `cattle_health_app/spatial_audit.py` (new), `cattle_health_app/api.py`, `tests/test_spatial_audit.py` (new).

- [x] Test that posting `correct`, `false_positive`, and `wrong_direction` verdicts by event index, and adding a missed event, yields the expected counts and a partial/full review flag. Test that regenerating the spatial report starts a new audit revision.
- [x] Run focused tests; confirm endpoint/logic failures.
- [x] Store audit data in `results/<job>/spatial_<kind>_audit.json` with report SHA-256, verdicts keyed by event index, missed events, reviewer and note. `GET /api/jobs/{job_id}/spatial-reports/{kind}/audit` returns current report events and summary; `POST .../audit/verdicts` saves one event verdict; `POST .../audit/missed` adds one manually observed event. Resolve the report before audit access.
- [x] Rerun focused tests; commit `feat: record spatial event audit and error summary`.

### Task 3: Review on the web

**Files:** `web/src/api.ts`, `web/src/SpatialAnalysisPanel.tsx`, `web/src/SpatialAnalysisPanel.test.tsx`, spatial panel stylesheet.

- [x] Add a failing UI test that opens a gate report, marks a crossing correct, adds a missed crossing, and sees the summary change via mocked API responses.
- [x] Run `npm test -- --run SpatialAnalysisPanel.test.tsx`; confirm failure on missing controls.
- [x] Add typed audit API methods and a compact event list with video seek buttons, verdict controls, missed-event form, and progress/precision/recall only when the report is fully reviewed. Keep the current zone trends and gate totals labeled as automatic counts.
- [x] Rerun focused and full frontend tests, run `npm run build`; commit `feat: review spatial events in video panel`.

### Task 4: Demonstrate and hand off

**Files:** `docs/2026-10-23-video-evidence-audit-acceptance.md`, `HANDOFF.md`.

- [ ] Run backend tests and frontend tests using a workspace temp directory; run a synthetic API flow with correct/false/missed/direction cases and record exact counts.
- [ ] Check the panel at phone width, including seeking a video and saving a verdict. If an existing CBVD-5 `272.mp4` result is usable, show one zone-entry example; otherwise record the exact missing artifact.
- [ ] Record measured scope, remaining need for independent long video/ledger, test output, and the next independently executable task in the six HANDOFF sections. Commit `docs: hand off video evidence audit`.
