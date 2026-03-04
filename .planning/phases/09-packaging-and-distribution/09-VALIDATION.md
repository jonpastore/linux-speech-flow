---
phase: 9
slug: packaging-and-distribution
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed in .venv) |
| **Config file** | none — uses pytest defaults |
| **Quick run command** | `pytest --tb=short -q` |
| **Full suite command** | `pytest --tb=short -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest --tb=short -q`
- **After every plan wave:** Run `pytest --tb=short -q`
- **Before `/gsd:verify-work`:** Full suite must be green + CI build job passes
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 9-01-01 | 01 | 1 | DIST-04 | smoke | `pytest --tb=short -q` (existing suite) | ✅ | ⬜ pending |
| 9-01-02 | 01 | 1 | DIST-04 | smoke | `pytest --tb=short -q` | ✅ | ⬜ pending |
| 9-02-01 | 02 | 1 | DIST-01 | smoke | `pytest --tb=short -q` | ✅ | ⬜ pending |
| 9-02-02 | 02 | 1 | DIST-01/02 | smoke | `pytest --tb=short -q` | ✅ | ⬜ pending |
| 9-03-01 | 03 | 2 | DIST-05 | manual | code review | ❌ manual only | ⬜ pending |
| 9-04-01 | 04 | 2 | DIST-04 | smoke | CI job (tag-gated) | CI only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing pytest infrastructure covers all unit tests. Packaging validation is CI-only. No new test stubs required.

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| .deb installs on clean Ubuntu 22.04 | DIST-01 | Requires VM/container with real dpkg | Install .deb in docker Ubuntu 22.04 container; verify `linux-speech-flow` runs |
| README has system dep section | DIST-05 | Documentation review | Open README.md and verify system dep section exists with all 5 deps listed |
| PyPI publish succeeds on v* tag | DIST-04 | Requires real tag push and PyPI config | Push v* tag after trusted publisher configured; verify package appears on pypi.org |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
