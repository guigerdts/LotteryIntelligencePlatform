# Spec — Testing (`testing`)

**Change**: `fase-17-testing` · **Store**: `openspec` · **Date**: 2026-08-19

## Purpose

Repair the F16 fixture regression (P0), make backend/frontend coverage measurable, enforce ≥80%/≥70% targets report-only-then-gated, add GitHub Actions CI, Playwright E2E for the core cycle, and a reproducible performance harness.

## Requirements Overview

| ID | Requirement | Priority |
|----|-------------|----------|
| TEST-001 | Fixture regression repair | P0 |
| TEST-002 | Coverage instrumentation | P0 |
| TEST-003 | Coverage policy — report-only then gate | P0 |
| TEST-004 | CI main gate — GitHub Actions | P0 |
| TEST-005 | E2E core cycle — Playwright only | P1 |
| TEST-006 | Performance harness — reproducible | P1 |

## Requirements

### TEST-001: Fixture Regression Repair

The suite MUST pass after repairing the F16 S7 fixture regression (63 `ScopeMismatch` errors in `test_services.py`, `test_integrity.py`, `test_import_service.py`); those tests MUST NOT be skipped, xfailed, excluded, or hidden; production code MUST NOT change solely for the fixture issue; non-S7 failures MUST be reported as separate preexisting regressions.

#### Scenario: suite green after repair
- GIVEN repaired fixtures
- WHEN the full backend suite runs
- THEN all 63 pass, none skipped or excluded

#### Scenario: hiding tests rejected
- GIVEN a fix marking the 63 tests skip/xfail
- WHEN reviewed
- THEN it is rejected as non-compliant

#### Scenario: unrelated failure separated
- GIVEN a non-S7 failure during repair
- WHEN the P0 gate runs
- THEN it is reported separately, not folded into P0

### TEST-002: Coverage Instrumentation

Backend coverage MUST be measurable via pytest-cov; frontend via `@vitest/coverage-v8`; the full backend suite MUST pass before the official baseline is recorded.

#### Scenario: backend coverage measured
- GIVEN pytest-cov configured
- WHEN the backend suite runs with coverage
- THEN a backend coverage report is produced

#### Scenario: frontend coverage measured
- GIVEN `@vitest/coverage-v8` configured
- WHEN the frontend suite runs with coverage
- THEN a coverage report is produced

### TEST-003: Coverage Policy

Coverage MUST be report-only during establishment (CI MUST NOT fail on coverage alone); a hard gate MUST activate only after 3 consecutive runs with backend ≥80% AND frontend ≥70%; the frontend target MUST remain ≥70% unless documented technical evidence justifies a change.

#### Scenario: report-only during establishment
- GIVEN fewer than 3 qualifying CI runs
- WHEN coverage falls below target
- THEN CI passes and shortfall is reported

#### Scenario: hard gate activation
- GIVEN 3 consecutive runs meeting both targets
- WHEN a later run falls below either
- THEN CI fails on coverage

#### Scenario: frontend target change needs evidence
- GIVEN a proposal lowering frontend below 70%
- WHEN reviewed
- THEN it is rejected without documented evidence

### TEST-004: CI Main Gate

CI MUST run on GitHub Actions as main gate; the backend suite runtime (>15 min, ~1 GB peak) MUST be handled via sharding or a reduced gate subset; pre-commit MAY complement but MUST NOT be the main gate.

#### Scenario: push triggers CI
- GIVEN a push
- WHEN GitHub Actions runs
- THEN backend and frontend suites execute in CI

#### Scenario: long suite sharded
- GIVEN the full backend suite exceeds CI limits
- WHEN CI is configured
- THEN suites are sharded or a reduced subset runs

#### Scenario: pre-commit is not the gate
- GIVEN pre-commit hooks configured
- WHEN local hooks are bypassed
- THEN CI still enforces the gate

### TEST-005: E2E Core Cycle

E2E MUST use Playwright and MUST cover only the core cycle (create lottery → import draws → generate statistics → view dashboard); AI Assistant E2E MUST NOT be in scope.

#### Scenario: core cycle green
- GIVEN a running app with seeded data
- WHEN a user runs the full core cycle
- THEN each step completes and the dashboard renders the statistics

#### Scenario: AI Assistant out of scope
- GIVEN an E2E proposal for the AI Assistant flow
- WHEN scope is reviewed
- THEN it is excluded from this change

### TEST-006: Performance Harness

A reproducible performance harness MUST exist with repeated measurements, explicit baseline, target, and tolerances; `pytest-benchmark` MUST NOT be introduced; functional timing tests MUST NOT count as benchmarks.

#### Scenario: reproducible measurement
- GIVEN the harness with baseline, target, tolerance configured
- WHEN it runs repeated measurements
- THEN results report variance and flag outliers

#### Scenario: no pytest-benchmark
- GIVEN the performance slice
- WHEN dependencies are added
- THEN pytest-benchmark is not among them
