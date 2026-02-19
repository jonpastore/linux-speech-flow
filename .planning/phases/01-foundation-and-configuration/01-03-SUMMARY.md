---
phase: 01-foundation-and-configuration
plan: 03
subsystem: api
tags: [groq, requests, validation, unittest-mock, tdd, pytest]

requires:
  - phase: 01-foundation-and-configuration plan 01
    provides: project skeleton, venv, pyproject.toml with requests dependency

provides:
  - validate_api_key(api_key: str) -> dict in groq_client.py
  - Two-pass validation: format check then live HTTP call to Groq models endpoint
  - 12 TDD tests covering all branches, all HTTP mocked

affects:
  - setup wizard (API key page calls validate_api_key in background thread)
  - Phase 2 audio pipeline (Groq client will be used for transcription)

tech-stack:
  added: []
  patterns:
    - "Two-pass validation: cheap format check before expensive network call"
    - "unittest.mock.patch for HTTP isolation in tests; no live network in test suite"
    - "requests.get with Authorization: Bearer header and timeout=10 for Groq API calls"

key-files:
  created:
    - src/linux_speech_flow/groq_client.py
    - tests/test_groq_client.py
  modified: []

key-decisions:
  - "gsk_ prefix + min 20 chars as format check; simple and covers all real Groq keys"
  - "ConnectionError and Timeout share one message (both mean 'network not reachable' to user)"
  - "No new dependencies added; requests already in pyproject.toml"

patterns-established:
  - "Two-pass validation: format check first, HTTP call only on format pass"
  - "Mock target is linux_speech_flow.groq_client.requests.get (patch where used, not where defined)"

requirements-completed: [CONF-01]

duration: 1min
completed: 2026-02-19
---

# Phase 1 Plan 3: Groq API Key Validation Summary

**Two-pass Groq API key validation via requests: format check (gsk_ prefix + 20 char minimum) then live GET /openai/v1/models with Bearer auth, all branches covered by 12 mocked TDD tests.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-19T06:58:29Z
- **Completed:** 2026-02-19T06:59:34Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2

## Accomplishments
- `validate_api_key` implements two-pass validation: format first, HTTP only if format passes
- 401 and network errors produce distinct, user-friendly messages
- 12 tests cover all specified branches with zero live network calls
- All 22 tests pass (10 from 01-02 + 12 new)

## Task Commits

Each task was committed atomically:

1. **TDD RED: failing tests for validate_api_key** - `58d9a2e` (test)
2. **TDD GREEN: implement validate_api_key** - `7e4fb1e` (feat)

_Note: TDD tasks have two commits (test -> feat); REFACTOR not needed — implementation was clean._

## Files Created/Modified
- `src/linux_speech_flow/groq_client.py` - validate_api_key with two-pass format+HTTP validation
- `tests/test_groq_client.py` - 12 tests covering all branches, all HTTP mocked via unittest.mock

## Decisions Made
- `gsk_` prefix + minimum 20 characters chosen as format guard: simple, covers all real Groq key shapes
- `ConnectionError` and `Timeout` share the same message — both mean network unreachable from the user's perspective
- No new pyproject.toml dependencies; `requests` was already declared in 01-01

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `validate_api_key` ready for the setup wizard's API key page (Phase 3 UI work)
- Groq HTTP client pattern established for transcription calls in Phase 2

---
*Phase: 01-foundation-and-configuration*
*Completed: 2026-02-19*
