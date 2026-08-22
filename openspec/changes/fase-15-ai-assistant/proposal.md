# Proposal: Fase 15 — AI Assistant (Deterministic v1)

## Intent

Real Fase 15 engine: deterministic rule-based text generation for the 5 roadmap functions (explain/interpret/report/summarize/assist), consuming persisted outputs — no LLM, no new deps. Rewire IA page; fix R14 spec/impl mismatch.

## Scope

**In (3 slices ≤400 lines each)**
- S1 engine core: `backend/app/ai/` + generators + unit tests
- S2 API: `api/v1/assistant.py` + envelope + integration tests (+ scalars endpoint if D7)
- S3 frontend: `IA.tsx` + `services/assistant.ts` + MSW tests + R14 delta

**Out**: F16 Performance; auth/JWT; `/dashboard/*`; new stats (F3-pending); ML train/predict; schedulers; Docker/deploy; persistent sessions; LLM deps.

## Capabilities

New — `ai-assistant`: deterministic generation over persisted snapshots; `TextGenerator` seam; versioned algorithm identity.
Modified — `frontend-dashboard` (F14 delta): R14 → IA consumes assistant API; NFR-2/4 kept.

## Approach

Deterministic engine behind `TextGenerator` seam: stdlib+templates+Decimal; zero new deps (gate green); versioned identity+fingerprint; `SuccessEnvelope`; manual read-only triggers (BTE-12); config via `Settings`.

- S1 `backend/app/ai/`: `engine.py` (5 fns) · `generators.py` · `prompts.py` (D1) · `version.py` · `fingerprint.py` · `providers.py` (TextGenerator + RuleBased) · AiService · unit tests
- S2 `api/v1/assistant.py`: per-function endpoints (D3); `router.py` mount; `schemas/assistant.py`; integration tests
- S3 `IA.tsx`: sections + assistant panel (D4); `services/assistant.ts`; MSW; R14 delta (D8)

## Decisions (default = recommended)

- D1 prompts → code constants in engine pkg
- D2 report persistence → on-demand sync, manual-only
- D3 API shape → explicit per-function endpoints
- D4 IA page → keep sections + assistant panel
- D5 conversation → stateless v1
- D6 "interpretar gráficos" → client chart data, not images
- D7 entropy → add `GET /statistics/{code}/scalars`
- D8 R14 → modified in F15 delta spec

## Affected Areas

`backend/app/ai/` (new) · `api/v1/assistant.py` + `schemas/assistant.py` (new) · `api/v1/router.py` (mod) · `api/v1/statistics.py` (mod, D7) · `config/settings.py` (mod) · `frontend/src/pages/IA.tsx` (mod) · `frontend/src/services/assistant.ts` (new) · `openspec/changes/fase-15-ai-assistant/specs/` (new, 2 deltas).

## Risks

- "Asistir" overbuilt w/o LLM (Med) → intent routing over 4 functions
- D7 blocked → explain falls back to freq/avg
- R14 delta scope creep (Med) → bound to R14 block
- Determinism drift (Low) → versioned identity + golden tests

## Rollback

Delete `ai/`, assistant router/schemas; un-mount. Revert IA.tsx/service; drop R14 delta. No migrations unless D2/D5.

## Dependencies

Existing persisted snapshots (statistics/probability/ML/experiment/backtest); owner sign-off D1–D8.

## Success Criteria

- [ ] 5 functions return deterministic, envelope-wrapped output
- [ ] Zero new runtime deps (gate tests green)
- [ ] IA.tsx consumes assistant API only; NFR-2/NFR-4 hold
- [ ] R14 updated; mismatch resolved
- [ ] Backend pytest + frontend test/build green
