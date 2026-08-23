```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:381f04deb8ff78b406540c0234b6a156f53584b9a654a4ecb52e2bc7a55f1e5a
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 12/12
scenarios: 23/23
test_command: backend/.venv/bin/pytest tests/dl -q && backend/.venv/bin/pytest tests/test_dl_cli.py tests/test_dl_api.py -q
test_exit_code: 0
test_output_hash: sha256:8075357fa3fa8fdf8c8c385575f60fd52c95e17d69e8ba6a0b23d51994572abe
build_command: backend/.venv/bin/ruff check src/backend/app/dl src/backend/app/services/dl_service.py src/backend/app/api/v1/dl.py
build_exit_code: 0
build_output_hash: sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
```

# Verification Report — dl-snapshot-persistence

**Change**: `dl-snapshot-persistence` · **Mode**: openspec · **Evidence revision**: main @ `68d4640dc7df3e6c904fe67eaa799c457665723c` (PRs #59–63: ec9fbc7+0dae45e, 6249877, 57ddf67, 8994fd5, 68d4640)
**Strict TDD**: active (config `tdd: true`; runner `backend/.venv/bin/pytest`) · **Verdict**: **PASS WITH WARNINGS**

## 1. Artifact completeness

| Artifact | Present | Used |
|---|---|---|
| proposal.md | ✅ | ✅ |
| design.md | ✅ | ✅ |
| tasks.md | ✅ | ✅ |
| specs/backend/spec.md + specs/dl-engine/spec.md (deltas) | ✅ | ✅ |
| apply-progress (Engram #1853, topic_key sdd/dl-snapshot-persistence/apply-progress) | ✅ | ✅ |

## 2. Task completeness — 24/24 `[x]`, evidence-backed

Phases 1–6 all checked. Runtime proof this session (fresh runs): `tests/dl` **162 passed** (201–230s), `tests/test_dl_cli.py tests/test_dl_api.py` **17 passed** (68–88s), ruff check on mandated paths **exit 0**. Slice-5 sweep (recorded evidence, not re-run per orchestrator): full suite **1495 passed / 1 skipped / 0 failed (807s)**; real-data smoke `lip dl train --lottery baloto` persisted snapshot_id=1 (cut=305 R2 default of frame 382, window=10) + 2 weights (format_version=1, shared run fp) + 10 Decimal metrics (number=0); idempotent rerun → same id/fp/checksum, zero writes.

## 3. Zero-delta claim — CONFIRMED

Both delta specs declare "No Requirement Deltas" and contain coverage tables only — no ADDED/MODIFIED/REMOVED/RENAMED requirements; nothing merges at archive. Normative text verified present in main specs: `dl-engine` DLE-01..16 + DE-01/02 (DLE-08 :192, DLE-12 :284), `backend` REQ-10 dl paragraph (:136), REQ-11 dl paragraph (:188) + route-limit scenario (:220), REQ-12 CLI paragraph (:240). Authoritative totals counted from the main specs this change must conform to (cited by both delta coverage maps): **12 requirements** (DLE-01/04/05/08/09/11/12/14/16 + REQ-10/11/12) × their **23 scenarios** (18 dl-engine acceptance items + 5 backend dl-attributable scenario blocks at spec lines 158/164/210/216/256). All 23 carry passing runtime evidence: fresh `tests/dl` (162) + surface suites (17) this session, plus the recorded slice-5 full-suite sweep.

## 4. Spec compliance matrix (proposal behavior → requirement → code → passing test)

| Behavior | Req | Implementation | Covering test (passed at runtime) |
|---|---|---|---|
| Flush-only store: get_active/find_by_fingerprint(active)/next_version/metrics filter | DLE-12/01 | `dl/snapshot_store.py:39-99` | test_snapshot_store.py (21 tests) |
| Atomic tx: placeholder→train mlp→lstm→fill→metrics→weights→retire→SINGLE commit | DLE-12 | `services/dl_service.py:187-253` | test_service.py::TestSuccessTransaction (3) |
| Retire deletes old actives' weight rows in-tx | DLE-12/R1 | `snapshot_store.py:167-186` | test_retires_old_active_and_deletes_its_weights…; store retire tests |
| Failure = rollback → recreate mark_failed → ONLY terminal failed header | DLE-12 | `dl_service.py:264-287`, `snapshot_store.py:188-221` | test_engine_failure_persists_only_terminal_failed_header; store post-rollback test |
| Idempotent rerun by fingerprint, zero writes | DLE-12 | `dl_service.py:175-185` | test_fingerprint_hit_returns_existing_without_new_writes; smoke rerun |
| Weights ≤16 MiB pre-INSERT gate; format_version=1; no pickle | DLE-09/11 | `snapshot_store.py:147-157` (_MAX_WEIGHTS_SIZE) | test_oversize_blob_rejected_before_staging; roundtrip test |
| Decimal-only metrics, number=0 sentinel, sorted params_json, checksum over fam.name keys | DLE-08/01 | `dl_service.py:222-245` | TestSuccessTransaction asserts scale=-8, sentinel, sort_keys, recomputed checksum |
| Engine cut threading + TrainResult.cut + injected shared fp | DLE-05/08 | `dl/engine.py:153-271`, `opt/objective.py:115` | test_engine cut/fp tests (:115,:137,:161,:171); GF-1 e2e (7 tests byte-identical) |
| W default 10 bounds 2..20, fingerprint-affecting | DLE-04 | cli group args; compute_dl_fingerprint(window,cut) | engine window-fp test; CLI bounds test |
| POST /dl/train SuccessEnvelope, invalid lottery 404 | REQ-10 | `api/v1/dl.py:50-73` | test_dl_api.py (6 tests) |
| GET /dl/models 404 SNAPSHOT_NOT_FOUND; reads never train; no /dl/predict | REQ-11/DLE-14 | `api/v1/dl.py:76-94`; router.py:35 mounts only train/models/metrics | API 404 + route-limit tests |
| GET /dl/metrics ETag → 304 empty body | REQ-13 parity | `api/v1/dl.py:97-124` | API ETag/304 test |
| CLI lip dl train/models/metrics plain JSON, unknown lottery error | REQ-12 | `cli.py:203-231,754-783` | test_dl_cli.py (10 tests) |
| Determinism seed=DL_SEED(0), torch lazy (DLE-17), cache key ("dl:metrics",id,model) | DLE-07/17 | `dl_service.py:164-173,201,216,316`; `_DL_CACHE` ThreadSafeLRU(256) | TestTorchDeferredImport (fresh interpreter); cache-key test |
| F4 early gate before any header write | design seq | `dl_service.py:102-111` | test_missing_f4_fails_before_any_header_write |

15/15 behaviors covered by code + passing runtime tests. Zero UNTESTED scenarios (delta declares none).

## 5. Design conformance — explicit rulings

| Item | Verdict | Evidence |
|---|---|---|
| ADR-1 flush-only store, caller owns commit | **PASS** | Store ends every write in flush() only; single commit at `dl_service.py:253`; failure commit :279 |
| ADR-2 retire deletes weight rows in-tx | **PASS** | `retire_old_active` → `delete_weights_for(ids)` same tx (`snapshot_store.py:181-186`) |
| recreate-pattern mark_failed after rollback | **PASS** | Re-insert terminal header (:207); post-rollback store + service tests prove persistence |
| Single-commit sequence incl. F4 early gate + idempotent short-circuit | **PASS** | Gate precedes next_version/header (:102-113); reuse branch returns before placeholder (:175-185) |
| DLE-13 carrier conversion at composition root only | **PASS** | CLI handlers convert via _CliDrawAdapter/_CliFeatureAdapter → dl.providers carriers; API adapters yield DrawRow/FeatureRow directly (ADR-4-ratified per-surface duplication — NOT a deviation) |
| Cut threading engine→objective→service; M-A8 default len(frame)*4//5 | **PASS** (with documented refinement) | engine kw-only cut + fp override; objective passes declared cut; service computes k=len(frame)*4//5 as split INDEX then binds real_cut=train_frame[-1].draw_number and builds windows PER SIDE to avoid guaranteed straddling (splitter rejects straddle for W≥3). Faithful R2 intent; slice-3 discovery recorded; covered by explicit-cut + default-cut tests |
| Determinism: DL_SEED=0, Decimal metrics number=0, sorted params_json, shared run fp across families | **PASS** | seed passed to both engine calls; number=0 literal; json.dumps(sort_keys=True); run_fp injected into both trains + both weight rows + header |

## 6. Strict TDD compliance

| Check | Result |
|---|---|
| TDD evidence reported | ✅ apply-progress #1853: RED-first verified per slice; comment-only tasks used grep evidence + focused tests before/after (16 passed both sides) |
| All tasks have tests | ✅ 24/24 tasks map to 69 change-local tests (store 21, engine 16 incl. new cut/fp cases, GF-1 e2e 7, service 9, CLI 10, API 6); fresh runs: `tests/dl` 162 passed (incl. earlier-fase dl tests), surfaces 17 passed |
| RED confirmed (tests exist) | ✅ all listed files present on disk |
| GREEN confirmed (pass on execution) | ✅ fresh runs this session: 162 + 17 passed |
| Triangulation adequate | ✅ success/failure/idempotency/early-gate/cache/cold-start each have dedicated cases with distinct expected values |
| Safety net | ✅ full-suite sweep green post-change (1495/1 skipped/0 failed) |
| Assertion quality | ✅ 0 banned patterns across change tests (sole `staged == []` is a negative-semantics assertion behind pytest.raises with companion non-empty roundtrip) |

Test layer distribution: Unit 53 (store/engine/service/e2e-determinism) · Surface-integration 16 (CLI runner 10, TestClient 6) · E2E browser: n/a. Coverage tool: not run this phase (informational; slice-5 sweep green).

## 7. Residual rulings (orchestrator items a–d + one found)

| # | Finding | Classification | Ruling |
|---|---|---|---|
| a | `get_metrics` returns bare `Response(304)` under `SuccessEnvelope[list[dict]]` annotation (`api/v1/dl.py:120`) | **SUGGESTION** | FastAPI-legal: returned Response instances bypass response_model serialization; OpenAPI shape stays correct. mypy imprecision only. Exact house idiom mirrored from `ml.py:119`; also graph/statistics/probability/bt routers. House-wide typing debt, not introduced here. Optional follow-up: `-> SuccessEnvelope[list[dict]] \| Response`. |
| b | Adapter/train-row projection duplicated between `cli.py` and `api/v1/dl.py` | **NO ACTION** | Ratified by ADR-4 ("Adapters duplicated per surface", house convention, already true for ML). Sharing would couple surfaces across engines. Revisit only if a third DL surface appears. |
| c | `next_version` orders String version lexicographically → past v9 returns max="9", re-issues "10" → UNIQUE collision; moreover `mark_failed` inside the except path re-inserts the SAME colliding version, so that edge degrades DLE-12's terminal-failed outcome into an unhandled IntegrityError | **WARNING** | Real latent gap but inherited verbatim from the ML mirror (design mandates method-for-method mirroring), requires ≥11 generations to trigger, and no spec scenario exercises it. Follow-up (out of this change): CAST-based numeric ordering + failure-path version fallback in BOTH ml and dl stores together. |
| d | Repo-wide `ruff format --check` drift | **CONFIRMED ZERO OVERLAP** | Fresh run: exactly 10 src files fail, all under `graph/` (community, engine, metrics, snapshot_store) and `probability/` (6 files); slice-5 counted 30 incl. their tests. Change diff (`ec9fbc7~1..68d4640`) touches none of them; those modules' last commits are fase PRs (7f24bf5, dd345ef). Pre-existing legacy drift → standalone chore PR. |
| e | `dl_metric.py:1` citation flagged at slice-5 as residual "D-A7/DLE-01" | **RESOLVED IN CHANGE** | Current source cites "design Data Model, **D-A1**/DLE-01"; fase-8 design.md:14 defines D-A1 as the one-snapshot-per-run data model — correct. PR #63 (68d4640) closed it. Grep: zero stale `D-A7` citations remain. |

## 8. Issues summary

- **CRITICAL**: none.
- **WARNING**: 1 — item (c) inherited v9+ version-ordering edge (ml+dl follow-up).
- **SUGGESTION**: 2 — item (a) 304-typing idiom (house-wide); item (d) format-drift chore PR (graph/+probability/, zero overlap proven).

## 9. Command evidence (this verification)

| Command (cwd backend) | Exit | Output sha256 |
|---|---|---|
| `.venv/bin/pytest tests/dl -q` | 0 | 84d4fec9f8608b1556c6429d7125439a33c855f5621e106e72b6846a83b4a115 |
| `.venv/bin/pytest tests/test_dl_cli.py tests/test_dl_api.py -q` | 0 | 575621729e2b3a211451fad800a38c975b2cf8efe970c0f1e7c3fe30fa45b372 |
| combined test output (envelope hash) | — | 8075357fa3fa8fdf8c8c385575f60fd52c95e17d69e8ba6a0b23d51994572abe |
| `.venv/bin/ruff check src/backend/app/dl src/backend/app/services/dl_service.py src/backend/app/api/v1/dl.py` | 0 | 82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18 |

Full suite re-run intentionally skipped per orchestrator instruction; recorded slice-5 result cited in §2.

**Final verdict: PASS WITH WARNINGS** — implementation conforms to proposal/design/tasks; zero spec deltas confirmed; runtime proof green; one inherited latent warning routed to a cross-store follow-up.
