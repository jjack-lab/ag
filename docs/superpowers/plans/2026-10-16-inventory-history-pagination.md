# Inventory History Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search and page through all pen inventory history while preserving video evidence navigation.

**Architecture:** Keep the existing array endpoint for embedded video results. Add a filtered page endpoint backed by SQLite count and limit/offset queries. The global inventory panel owns query state and ignores stale responses.

**Tech Stack:** FastAPI, SQLite, React, Vitest, pytest.

---

### Task 1: Backend page query

**Files:** `cattle_health_app/repository.py`, `cattle_health_app/api.py`, `tests/test_inventory_api.py`.

- [ ] Add an API test that creates more than 100 records and expects page 2 to expose older records and the correct total; run it and confirm RED.
- [ ] Add tests for literal pen search, latest-review status, ordering and invalid query values; run and confirm RED.
- [ ] Implement a shared SQL status expression, matched count and limited page query in the repository. Add the FastAPI route with bounds and status validation.
- [ ] Run focused backend tests, then commit `feat: page and filter inventory history API`.

### Task 2: Global history controls

**Files:** `web/src/api.ts`, `web/src/InventoryPanel.tsx`, `web/src/InventoryPanel.test.tsx`, `web/src/workspace-interactions.css`.

- [ ] Add tests for first page, next page, pen/status filtering, empty results and stale response cancellation; run and confirm RED.
- [ ] Add page API type/helper and global controls. Keep the embedded result panel on the existing array endpoint. Clear displayed rows during a new query and ignore stale responses.
- [ ] Run focused frontend tests and production build, then commit `feat: search and page inventory history`.

### Task 3: Acceptance and handoff

**Files:** `README.md`, `docs/2026-10-16-inventory-history-pagination-acceptance.md`, `HANDOFF.md`.

- [ ] Run complete backend and frontend tests and production build.
- [ ] Exercise filtering and pagination in a browser with an isolated SQLite backup; confirm formal inventory remains unchanged.
- [ ] Update usage and acceptance docs; commit `docs: verify inventory history pagination`.
- [ ] Update all six HANDOFF sections and commit separately.
