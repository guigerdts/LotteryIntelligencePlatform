API_SPECIFICATION.md

Lottery Intelligence Platform (LIP)

REST API Specification

Version: 1.0

API Style: REST

Format: JSON

Authentication: None (v1)

Future: JWT + API Keys + OAuth2

---

1. API Principles

The API shall be:

- Stateless
- Versioned
- Self-documented
- Consistent
- Predictable
- Extensible

Base URL

/api/v1

---

2. Standard Response

Success

{
  "success": true,
  "data": {},
  "meta": {},
  "timestamp": "2026-08-05T12:00:00Z"
}

---

Error

{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Draw not found"
  },
  "timestamp": "2026-08-05T12:00:00Z"
}

---

3. Endpoint Reference

Auto-generated from the live OpenAPI schema by `docs/api/generate_reference.py`.
Do not edit between the markers by hand — re-run the generator instead:

    backend/.venv/bin/python docs/api/generate_reference.py

<!-- GENERATED-API-REFERENCE:START -->
### POST /api/v1/assistant/assist

- Summary: Route a free-text question to the matching generator
- Tags: assistant
- Request body: application/json — AssistRequest
- Response 200: SuccessEnvelope_AssistantResponse_

### GET /api/v1/assistant/explain

- Summary: Explain a lottery's results in Spanish
- Tags: assistant
- Parameters:
  - `lottery_code` (query, required, string)
  - `subject` (query, optional, string)
  - `context` (query, optional, string)
- Response 200: SuccessEnvelope_AssistantResponse_

### GET /api/v1/assistant/interpret

- Summary: Interpret the chart data in Spanish
- Tags: assistant
- Parameters:
  - `lottery_code` (query, required, string)
- Response 200: SuccessEnvelope_AssistantResponse_

### GET /api/v1/assistant/report

- Summary: Render a scoped Spanish plain-text report
- Tags: assistant
- Parameters:
  - `lottery_code` (query, required, string)
  - `scope` (query, optional, string)
- Response 200: SuccessEnvelope_AssistantResponse_

### POST /api/v1/assistant/summarize

- Summary: Summarize an experiment comparison in Spanish
- Tags: assistant
- Request body: application/json — SummarizeRequest
- Response 200: SuccessEnvelope_AssistantResponse_

### GET /api/v1/backtesting/history

- Summary: List backtest snapshots for a lottery (read-only)
- Tags: backtesting
- Parameters:
  - `lottery_id` (query, required, integer)
- Response 200: SuccessEnvelope_list_BtHistoryEntry__

### GET /api/v1/backtesting/results

- Summary: Get detailed backtest results (read-only)
- Tags: backtesting
- Parameters:
  - `lottery_id` (query, required, integer)
  - `snapshot_id` (query, optional, integer)
- Response 200: SuccessEnvelope_BtResultResponse_

### POST /api/v1/backtesting/run

- Summary: Execute a backtest on demand (manual-only, BTE-12)
- Tags: backtesting
- Request body: application/json — BtRunRequest
- Response 200: SuccessEnvelope_BtRunResponse_

### GET /api/v1/draws

- Summary: List Draws
- Tags: draws
- Parameters:
  - `lottery` (query, optional, string)
  - `date_from` (query, optional, string)
  - `date_to` (query, optional, string)
  - `order` (query, optional, string)
  - `page` (query, optional, integer)
  - `page_size` (query, optional, integer)
- Response 200: SuccessEnvelope_list_DrawRead__

### POST /api/v1/draws/import

- Summary: Import draw history from a server-side source path
- Tags: draws
- Request body: application/json — ImportDrawsRequest
- Response 200: SuccessEnvelope_dict_

### POST /api/v1/draws/upload

- Summary: Import draw history from an uploaded CSV file
- Tags: draws
- Request body: multipart/form-data — Body_upload_draws_api_v1_draws_upload_post
- Response 200: SuccessEnvelope_dict_

### GET /api/v1/draws/{draw_id}

- Summary: Get Draw
- Tags: draws
- Parameters:
  - `draw_id` (path, required, integer)
- Response 200: SuccessEnvelope_DrawRead_

### GET /api/v1/experiment/

- Summary: List experiments for a lottery
- Tags: experiment
- Parameters:
  - `lottery_id` (query, required, integer)
  - `status` (query, optional, string)
- Response 200: SuccessEnvelope_list_ExperimentResponse__

### POST /api/v1/experiment/create

- Summary: Create a new experiment
- Tags: experiment
- Request body: application/json — ExperimentCreateRequest
- Response 200: SuccessEnvelope_ExperimentResponse_

### GET /api/v1/experiment/{experiment_id}

- Summary: Get experiment by ID
- Tags: experiment
- Parameters:
  - `experiment_id` (path, required, integer)
- Response 200: SuccessEnvelope_ExperimentResponse_

### PATCH /api/v1/experiment/{experiment_id}

- Summary: Update experiment fields
- Tags: experiment
- Parameters:
  - `experiment_id` (path, required, integer)
- Request body: application/json — ExperimentUpdateRequest
- Response 200: SuccessEnvelope_ExperimentResponse_

### POST /api/v1/experiment/{experiment_id}/compare

- Summary: Compare runs within an experiment
- Tags: experiment
- Parameters:
  - `experiment_id` (path, required, integer)
- Request body: application/json — ComparisonRequest
- Response 200: SuccessEnvelope_ComparisonResponse_

### GET /api/v1/experiment/{experiment_id}/export

- Summary: Export experiment results as JSON or CSV
- Tags: experiment
- Parameters:
  - `experiment_id` (path, required, integer)
  - `format` (query, optional, string)
- Response 200: (no content)

### POST /api/v1/experiment/{experiment_id}/run

- Summary: Associate an engine snapshot with an experiment
- Tags: experiment
- Parameters:
  - `experiment_id` (path, required, integer)
- Request body: application/json — RunCreateRequest
- Response 200: SuccessEnvelope_RunResponse_

### POST /api/v1/feature-engine/generate

- Summary: Generate (or idempotently return) a feature snapshot
- Tags: feature-engine
- Request body: application/json — backend__app__schemas__feature_engine__GenerateRequest
- Response 200: backend__app__schemas__envelope__SuccessEnvelope_GenerateSnapshot___2

### GET /api/v1/feature-engine/{lottery_code}/features

- Summary: Read persisted features from the active snapshot (no precompute)
- Tags: feature-engine
- Parameters:
  - `lottery_code` (path, required, string)
  - `feature` (query, optional, string)
  - `last` (query, optional, integer)
- Response 200: SuccessEnvelope_FeatureList_

### GET /api/v1/gen/combinations

- Summary: Read stored combinations of a generator snapshot (no recompute)
- Tags: generator
- Parameters:
  - `lottery_id` (query, required, integer)
  - `snapshot_id` (query, optional, integer)
- Response 200: SuccessEnvelope_CombinationList_

### POST /api/v1/gen/generate

- Summary: Generate (or idempotently return) a lottery combination snapshot
- Tags: generator
- Request body: application/json — backend__app__schemas__gen__GenerateRequest
- Response 200: SuccessEnvelope_GenerationResult_

### POST /api/v1/gen/snapshot

- Summary: Transition a generator snapshot lifecycle status (GEN-007)
- Tags: generator
- Request body: application/json — SnapshotUpdateRequest
- Response 200: SuccessEnvelope_SnapshotResult_

### GET /api/v1/gen/snapshots

- Summary: List generator snapshots for a lottery (GEN-010)
- Tags: generator
- Parameters:
  - `lottery_id` (query, required, integer)
- Response 200: SuccessEnvelope_SnapshotList_

### POST /api/v1/graph/compute

- Summary: Compute a graph snapshot (idempotent)
- Tags: graph
- Request body: application/json — ComputeRequest
- Response 200: SuccessEnvelope_ComputeSnapshot_

### GET /api/v1/graph/{lottery_code}/snapshots

- Summary: List graph snapshots for a lottery
- Tags: graph
- Parameters:
  - `lottery_code` (path, required, string)
  - `graph_type` (query, optional, string)
- Response 200: SuccessEnvelope_GraphSnapshotList_

### GET /api/v1/graph/{lottery_code}/snapshots/{snapshot_id}

- Summary: Read graph values from a specific snapshot
- Tags: graph
- Parameters:
  - `lottery_code` (path, required, string)
  - `snapshot_id` (path, required, integer)
- Response 200: SuccessEnvelope_GraphValuesResponse_

### GET /api/v1/health

- Summary: Health
- Tags: system
- Response 200: SuccessEnvelope_dict_str__str__

### GET /api/v1/lotteries

- Summary: List Lotteries
- Tags: lotteries
- Parameters:
  - `page` (query, optional, integer)
  - `page_size` (query, optional, integer)
- Response 200: SuccessEnvelope_list_LotteryRead__

### POST /api/v1/lotteries

- Summary: Create Lottery
- Tags: lotteries
- Request body: application/json — LotteryCreate
- Response 201: SuccessEnvelope_LotteryRead_

### DELETE /api/v1/lotteries/{lottery_id}

- Summary: Delete Lottery
- Tags: lotteries
- Parameters:
  - `lottery_id` (path, required, integer)
- Response 204: (no content)

### GET /api/v1/lotteries/{lottery_id}

- Summary: Get Lottery
- Tags: lotteries
- Parameters:
  - `lottery_id` (path, required, integer)
- Response 200: SuccessEnvelope_LotteryRead_

### PUT /api/v1/lotteries/{lottery_id}

- Summary: Update Lottery
- Tags: lotteries
- Parameters:
  - `lottery_id` (path, required, integer)
- Request body: application/json — LotteryUpdate
- Response 200: SuccessEnvelope_LotteryRead_

### POST /api/v1/meta/rank

- Summary: Compute a ranking for a lottery (META-005)
- Tags: meta
- Request body: application/json — RankRequest
- Response 200: SuccessEnvelope_RankingResult_

### GET /api/v1/meta/ranking

- Summary: Retrieve ranking snapshot (META-010)
- Tags: meta
- Parameters:
  - `lottery_id` (query, required, integer)
  - `context_hash` (query, optional, string)
- Response 200: SuccessEnvelope_RankingSnapshot_

### POST /api/v1/meta/select

- Summary: Compute a selection from the active ranking (META-006)
- Tags: meta
- Request body: application/json — SelectRequest
- Response 200: SuccessEnvelope_SelectionResult_

### GET /api/v1/meta/selection

- Summary: Retrieve selection snapshot (META-010)
- Tags: meta
- Parameters:
  - `lottery_id` (query, required, integer)
  - `context_hash` (query, optional, string)
- Response 200: SuccessEnvelope_SelectionSnapshot_

### GET /api/v1/ml/metrics

- Summary: Get ML metrics for the active snapshot
- Tags: ml
- Parameters:
  - `lottery_id` (query, required, integer)
  - `model_id` (query, optional, string)
- Response 200: SuccessEnvelope_list_dict__

### GET /api/v1/ml/models

- Summary: Get active ML snapshot metadata for a lottery
- Tags: ml
- Parameters:
  - `lottery_id` (query, required, integer)
- Response 200: SuccessEnvelope_dict_

### POST /api/v1/ml/train

- Summary: Train one or all core-5 ML families for a lottery
- Tags: ml
- Parameters:
  - `lottery_id` (query, required, integer)
  - `family` (query, optional, string)
- Response 200: SuccessEnvelope_dict_

### GET /api/v1/opt/metrics

- Summary: Get opt results for the active snapshot
- Tags: opt
- Parameters:
  - `lottery_id` (query, required, integer)
  - `optimizer` (query, optional, string)
- Response 200: SuccessEnvelope_list_dict__

### GET /api/v1/opt/models

- Summary: Get active opt snapshot metadata for a lottery
- Tags: opt
- Parameters:
  - `lottery_id` (query, required, integer)
  - `optimizer` (query, optional, string)
- Response 200: SuccessEnvelope_dict_

### GET /api/v1/opt/params

- Summary: Get default params for an optimizer
- Tags: opt
- Parameters:
  - `optimizer` (query, optional, string)
- Response 200: SuccessEnvelope_dict_

### POST /api/v1/opt/train

- Summary: Run one optimization pass for a lottery
- Tags: opt
- Parameters:
  - `lottery_id` (query, required, integer)
  - `optimizer` (query, optional, string)
  - `metric` (query, optional, string)
  - `direction` (query, optional, string)
  - `seed` (query, optional, integer)
- Response 200: SuccessEnvelope_dict_

### POST /api/v1/probability/generate

- Summary: Generate (or idempotently return) a probability snapshot
- Tags: probability
- Request body: application/json — backend__app__schemas__probability__GenerateRequest
- Response 200: backend__app__schemas__envelope__SuccessEnvelope_GenerateSnapshot___3

### GET /api/v1/probability/{lottery_code}/probabilities

- Summary: Read persisted probabilities from the active snapshot (no precompute)
- Tags: probability
- Parameters:
  - `lottery_code` (path, required, string)
  - `model` (query, optional, string)
  - `subject` (query, optional, string)
  - `last` (query, optional, integer)
- Response 200: SuccessEnvelope_ProbabilityList_

### POST /api/v1/statistics/generate

- Summary: Generate (or idempotently return) a statistics snapshot
- Tags: statistics
- Request body: application/json — backend__app__schemas__statistics__GenerateRequest
- Response 200: backend__app__schemas__envelope__SuccessEnvelope_GenerateSnapshot___1

### GET /api/v1/statistics/{lottery_code}/averages

- Summary: Read NULL-aware series averages from the active snapshot (no precompute)
- Tags: statistics
- Parameters:
  - `lottery_code` (path, required, string)
- Response 200: SuccessEnvelope_AverageList_

### GET /api/v1/statistics/{lottery_code}/frequencies

- Summary: Read per-number frequencies from the active snapshot (no precompute)
- Tags: statistics
- Parameters:
  - `lottery_code` (path, required, string)
  - `last` (query, optional, integer)
- Response 200: SuccessEnvelope_FrequencyList_

### GET /api/v1/statistics/{lottery_code}/gaps

- Summary: Read per-number gap summaries from the active snapshot (no precompute)
- Tags: statistics
- Parameters:
  - `lottery_code` (path, required, string)
  - `last` (query, optional, integer)
- Response 200: SuccessEnvelope_GapList_

### GET /api/v1/statistics/{lottery_code}/scalars

- Summary: Read dataset-level scalars from the active snapshot (no precompute, A-11)
- Tags: statistics
- Parameters:
  - `lottery_code` (path, required, string)
- Response 200: SuccessEnvelope_ScalarList_

### GET /api/v1/version

- Summary: Version
- Tags: system
- Response 200: SuccessEnvelope_dict_str__str__
<!-- GENERATED-API-REFERENCE:END -->

---

17. Response Codes

200 OK

201 Created

202 Accepted

204 No Content

400 Bad Request

401 Unauthorized

403 Forbidden

404 Not Found

409 Conflict

422 Validation Error

429 Too Many Requests

500 Internal Server Error

503 Service Unavailable

---

18. Pagination

{
  "page": 1,
  "page_size": 50,
  "total": 1823,
  "pages": 37
}

---

19. Filtering

Examples

?date_from=2024-01-01

?date_to=2025-01-01

?lottery=baloto

?order=desc

?page=2

---

20. Future Extensions

- GraphQL
- WebSockets
- Streaming
- Public API
- Authentication
- Rate limiting
- Multi-user support
- Plugin endpoints

---

21. Objective

Provide a stable, versioned and extensible REST API that serves as the communication layer between the backend, the dashboard, future mobile applications and external integrations while maintaining consistency across all analytical modules.
