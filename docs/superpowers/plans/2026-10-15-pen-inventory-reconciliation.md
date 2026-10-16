# Pen Inventory Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators compare a pen register with a human count tied to a completed video, then record a traced field recheck before any loss is user recorded.

**Architecture:** Store append-only inventory checks and rechecks in SQLite. Keep all status derivation in one Python module and return it through API responses. The web app shows a form beside completed video evidence and a list of checks; video Track IDs are shown only as a reference.

**Tech Stack:** Python 3.8, SQLite, FastAPI/Pydantic, React/TypeScript, pytest, Vitest.

---

### Task 1: Domain rules and persistence

**Files:** Create `cattle_health_app/inventory.py`; modify `cattle_health_app/repository.py`; create `tests/test_inventory.py`.

- [x] Write failing tests for coverage precedence, missing count versus zero, pending discrepancy, matched count, field recheck, and guarded loss registration.
- [x] Run `pytest tests/test_inventory.py -q` and confirm failures come from missing rules/repository methods.
- [x] Implement `inventory_state(check, latest_recheck)` returning `status`, `difference`, `current_count`; add append-only `inventory_checks`/`inventory_rechecks` tables and save/get/list methods.
- [x] Run the focused tests and commit `feat: store pen inventory checks and rechecks`.

### Task 2: API contracts and validation

**Files:** Modify `cattle_health_app/api.py`; create `tests/test_inventory_api.py`.

- [x] Write failing API tests for completed-video binding, species preservation, nonnegative counts, incomplete coverage, persisted list/detail, and loss registration prerequisites.
- [x] Run `pytest tests/test_inventory_api.py -q` and confirm red tests.
- [x] Add `POST/GET /api/inventory-checks`, `GET /api/inventory-checks/{id}`, and `POST /api/inventory-checks/{id}/rechecks`; derive status server-side and include `video_track_count` as reference only.
- [x] Run focused API tests and commit `feat: expose guarded pen reconciliation API`.

### Task 3: Browser workflow

**Files:** Create `web/src/InventoryPanel.tsx` and `web/src/InventoryPanel.test.tsx`; modify `web/src/api.ts`, `web/src/RecognitionStudio.tsx`, and `web/src/workspace-interactions.css`.

- [x] Write failing UI tests for the completed-video form, coverage warning, pending shortfall, and human recheck controls.
- [x] Run `npm test -- --run src/InventoryPanel.test.tsx --maxWorkers=1` in `web/` and confirm red tests.
- [x] Implement a completed-video inventory panel with an explicit Track ID disclaimer, form, persisted check list, status, and recheck form. Keep “lost” text only for `loss_user_recorded`.
- [x] Run focused and full front-end tests, `npm run build`, and commit `feat: manage pen inventory checks from video results`.

### Task 4: End-to-end verification and handoff

**Files:** Update `README.md`, `HANDOFF.md`, and an acceptance record in `docs/`.

- [x] Run `pytest -q`, `npm test -- --run --maxWorkers=1`, and `npm run build`.
- [x] Use an isolated SQLite backup and development video to create one pending discrepancy and one guarded manual outcome through Chrome; verify the live database is unchanged.
- [x] Record evidence, failure boundaries, and remaining real-farm validation requirements in docs; commit the acceptance record and `HANDOFF.md` separately.
