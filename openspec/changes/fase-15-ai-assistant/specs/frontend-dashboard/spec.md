# Delta — Frontend Dashboard: IA page becomes AI Assistant

**Change**: `fase-15-ai-assistant` · **Store**: `openspec` · **Date**: 2026-08-16
**Artifact**: delta spec — MODIFIED R14 on the existing `frontend-dashboard` capability (F14 delta, still live). All other requirements (R1–R13, R15–R25) and NFR-1, NFR-3, NFR-5–8 remain unchanged. **NFR-2 and NFR-4 remain binding**: once F15 ships the five `/assistant/*` endpoints, "IA backend" is no longer a nonexistent path; the panel SHALL call only those five endpoints and the page SHALL keep rendering (NFR-4).

## MODIFIED Requirements

### Requirement: R14: IA (AI Assistant)

| Field | Value |
|-------|-------|
| **ID** | R14 |
| **RFC** | MUST |

The IA page SHALL render the current status sections — system health/version (`GET /api/v1/health`, `GET /api/v1/version`), active ML snapshot + top metrics (`GET /api/v1/ml/models`, `GET /api/v1/ml/metrics`), and recent probability rows (`GET /api/v1/probability/{code}/probabilities?last=5`) — preserving existing behavior (D4) — AND an assistant panel. The assistant panel SHALL provide a free-text question input bound to the global lottery selector (R4) and SHALL call exactly the five assistant endpoints: `GET /api/v1/assistant/explain`, `GET /api/v1/assistant/interpret`, `GET /api/v1/assistant/report`, `POST /api/v1/assistant/summarize`, `POST /api/v1/assistant/assist`. Assistant responses SHALL render as text; loading SHALL use skeletons, failures SHALL use `ErrorState` with retry, and empty-data text responses SHALL render as content, not as errors (R20). Panel inputs SHALL meet R22 (associated labels, visible focus, WCAG AA). The panel SHALL call ONLY these five endpoints (NFR-2) and the page SHALL continue to render under all states (NFR-4).
(Previously: stub page rendering an empty-state message "Fase 15 — AI Assistant"; SHALL NOT call any backend endpoint.)

#### Scenario: IA status sections render (unchanged)

- GIVEN the global lottery is set and the backend responds
- WHEN the IA page mounts
- THEN system health/version, ML snapshot + top metrics, and recent probabilities render as today

#### Scenario: assistant question via panel (new)

- GIVEN the global lottery is set
- WHEN the user submits a question in the panel
- THEN `POST /api/v1/assistant/assist` is called with `{question, lottery_code}`
- AND the generated Spanish text renders in the panel

#### Scenario: panel loading and error states (new)

- GIVEN an assistant request in flight
- WHEN the response is pending or fails
- THEN skeletons render while loading, and `ErrorState` with retry renders on failure (R20)

#### Scenario: no nonexistent endpoints (new)

- GIVEN the IA page fully rendered
- WHEN the page and panel complete all their calls
- THEN every call targets an existing endpoint (`/assistant/*`, `/health`, `/version`, `/ml/*`, `/probability/*`)
- AND no request returns 404 to a nonexistent path (NFR-2)