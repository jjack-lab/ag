# Cosmic Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the existing home, module hub, and workspace a coherent multicolor space palette while preserving behavior and readability.

**Architecture:** Add one last-loaded CSS file with scoped visual overrides and color tokens. Keep React structure and Python API untouched.

**Tech Stack:** React, CSS, Vitest, Vite.

---

### Task 1: Palette tokens and homepage

**Files:** `web/src/App.tsx`, new `web/src/cosmic-palette.css`

- [ ] Import the palette file last.
- [ ] Add navy base, blue/violet ambient light, orange portal emphasis, and mint status color.
- [ ] Check the home screenshot at desktop width and a narrow viewport.

### Task 2: Module hub and workspace

**Files:** `web/src/cosmic-palette.css`

- [ ] Style module cards with eight distinguishable accents and readable labels.
- [ ] Restyle workspace background, nav, metrics, and primary controls with scoped overrides.
- [ ] Ensure risk labels retain semantic risk colors.

### Task 3: Verification and handoff

**Files:** `HANDOFF.md`

- [ ] Run `npm test` and `npm run build` in `web/`.
- [ ] Inspect home, module hub, and at least one workspace page in browser.
- [ ] Commit implementation and update `HANDOFF.md`; integrate into `integration`.
