# Video Inventory History Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show all inventory records bound to the selected video even after more than 100 newer global records exist.

**Architecture:** Add an optional `job_id` filter to the existing array endpoint while preserving its no-argument response. The embedded React panel passes the selected job ID; the global panel keeps using its paginated endpoint.

**Tech Stack:** SQLite, FastAPI, pytest, React, Vitest.

---

### Task 1: Backend query

**Files:** `cattle_health_app/repository.py`, `cattle_health_app/api.py`, `tests/test_inventory_api.py`.

- [ ] Write a failing API test with one older target record and 101 newer records from another video; require `?job_id=job-1` to return only the target.
- [ ] Run the focused test and confirm RED.
- [ ] Add parameterized, unbounded per-job repository query and optional API parameter. Keep no-argument `limit=100` behavior.
- [ ] Run focused tests and commit `fix: query inventory records by video job`.

### Task 2: Embedded panel

**Files:** `web/src/api.ts`, `web/src/InventoryPanel.tsx`, `web/src/InventoryPanel.test.tsx`, related mocked fetches.

- [ ] Write a failing test showing that a selected video sends its job ID and displays only returned records.
- [ ] Run the focused test and confirm RED.
- [ ] Pass job ID to the fetch helper from the embedded panel. Keep the global page request and its controls unchanged.
- [ ] Run focused and full frontend tests, build, and commit `fix: scope embedded inventory to video job`.

### Task 3: Verify and hand off

**Files:** `README.md`, `docs/2026-10-16-video-inventory-scope-acceptance.md`, `HANDOFF.md`.

- [ ] Run complete backend and frontend tests plus production build.
- [ ] Use isolated SQLite and a browser to verify an old video's inventory record remains visible beyond the global 100-record window.
- [ ] Document results and commit usage and acceptance docs.
- [ ] Update all six HANDOFF sections and commit separately.
