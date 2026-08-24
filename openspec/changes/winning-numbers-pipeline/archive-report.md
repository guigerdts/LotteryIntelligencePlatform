# Archive Report — winning-numbers-pipeline

Status: **COMPLETE** — all three slices merged to main (HEAD 201141f)

## Final state
- **S1** (PR #65, ab44e0f): mandatory seeded superbalota + combination scores in generation output; `next_version` observation model change in `snapshot_store.py`; meta tests green.
- **S2** (PR #66, 29326b4): `POST /api/v1/pipeline/numbers` healed orchestrator (stats→features→ml→dl→backtest→rank→select→generate) with failure healing matrix (R1-R7), idempotent `source_version`, endpoint + schemas + errors + tests.
- **S3** (PR #67, 201141f): `Mis Numeros` page — one CTA, busy-hold, ordered 8-stage report, Baloto+Revancha bundled tickets, default count 5, static 8-tier prize table, honest randomness disclaimer; Generator page retired; sidebar group renamed "Números".

## Base-spec promotion (proposed, not moved)
These capabilities are stable and should be promoted to `openspec/specs/` as delta specs on next maintenance:
- `superbalota-seeded-delivery` → generation core always seeds superbalota + emits combination scores
- `pipeline-orchestrator` → numbers pipeline endpoint with healing matrix is a permanent backend capability
- `mis-numeros-page` → user-facing numbers generation flow is THE entry point (Generator retired)

## Open non-blockers
- Add `.prettierrc` (chore) to make prettier gate enforceable repo-wide.
- `next_version` observation bump publishes next cycle.

## Rollback
Revert 201141f, 29326b4, ab44e0f in order (or `git revert` each). Restores Generator page + removes Mis Números + orchestrator.

## Owner outcome
The user can now open "Mis Números", click ONE button, wait minutes, and receive rule-complete combinations for Baloto + Revancha — exactly the flow they asked to be redesigned. No manual selection_id/seed steps.
