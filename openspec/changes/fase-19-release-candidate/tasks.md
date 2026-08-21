# Tasks — fase-19-release-candidate

## S0 — Dependency reconciliation (RC-001)
| ID | Task | Gate |
|---|---|---|
| T-S0-01 | Install declared deps (deap==1.4.1, optuna) into backend/.venv; regenerate/align uv.lock with pyproject.toml | `import optuna, deap` OK |
| T-S0-02 | Full backend suite from backend/ | 0 failed (5 optuna failures gone, no skips added) |

## S1 — Frontend stability (RC-002)
| ID | Task | Gate |
|---|---|---|
| T-S1-01 | Reproduce flakes: 2–3 full vitest runs, capture failing tests + error shapes | Reproduction documented |
| T-S1-02 | Fix nondeterminism in App.test.tsx / Experiments.test.tsx / History.test.tsx (async waits, deterministic fixtures; NO sleeps/skips) | Diffs show wait-based fixes |
| T-S1-03 | 3 consecutive fully-green frontend runs | 3× green |

## S2 — Release audit (RC-003)
| ID | Task | Gate |
|---|---|---|
| T-S2-01 | Run existing gates: ruff, backend pytest(+cov), frontend vitest, E2E availability check, hygiene greps | Outputs captured |
| T-S2-02 | Verify mypy/bandit configuration status; record as post-1.0 debt if unconfigured | Documented |
| T-S2-03 | Write audit-report.md with findings classified per rule 9 | Artifact exists |

## S3 — Critical audit fixes (RC-004)
| ID | Task | Gate |
|---|---|---|
| T-S3-01 | Fix critical/major findings that are local+objective; defer rest with justification | Suites re-run green |

## S4 — Performance validation (RC-005)
| ID | Task | Gate |
|---|---|---|
| T-S4-01 | Investigate cold_start: importtime measurement ×N, harness methodology review, box-noise assessment | Evidence recorded |
| T-S4-02 | Verdict + action: fix regression OR recalibrate baselines with evidence; final harness run report | Report artifact |

## S5 — Functional release validation (RC-006)
| ID | Task | Gate |
|---|---|---|
| T-S5-01 | Clean validation session: backend, frontend, E2E, coverage | All green |
| T-S5-02 | Write RELEASE_VALIDATION.md (date, HEAD, commands, outcomes, coverage vs F17) | Artifact exists |

## S6 — Release freeze (RC-007)
| ID | Task | Gate |
|---|---|---|
| T-S6-01 | Bump versions to 1.0.0 (pyproject + package.json); PROJECT_STATUS RC state + freeze statement | Manifests consistent |
| T-S6-02 | Commit freeze; tag v1.0.0-rc.1; push with tag | Tag on remote |

## S7 — Changelog / release notes (RC-008, RC-009)
| ID | Task | Gate |
|---|---|---|
| T-S7-01 | Generate CHANGELOG.md from real git history (F1→F19) | Traceable to log/tags |
| T-S7-02 | Draft RELEASE_NOTES.md for v1.0.0-rc.1 | Draft exists |
| T-S7-03 | LICENSE decision → STOP and ask owner (RC-009); apply choice after answer | Owner answer |

## Progress (machine-readable checkboxes)

- [x] T-S0-01 install deap/optuna + align uv.lock
- [x] T-S0-02 backend suite 0 failed
- [x] T-S1-01 reproduce flakes
- [x] T-S1-02 stabilize 3 flaky test files
- [x] T-S1-03 three consecutive green runs
- [x] T-S2-01 run existing gates
- [x] T-S2-02 mypy/bandit status recorded
- [x] T-S2-03 audit-report.md written
- [x] T-S3-01 critical fixes applied/deferred (none required — audit F-1..F-4 fixed in S0/S1)
- [x] T-S4-01 cold_start investigation evidence
- [x] T-S4-02 perf verdict + recalibration/report
- [ ] T-S5-01 clean validation session
- [ ] T-S5-02 RELEASE_VALIDATION.md written
- [ ] T-S6-01 version bumps + PROJECT_STATUS freeze
- [ ] T-S6-02 tag v1.0.0-rc.1 pushed
- [ ] T-S7-01 CHANGELOG.md generated
- [ ] T-S7-02 RELEASE_NOTES.md drafted
- [ ] T-S7-03 LICENSE owner decision asked/applied
