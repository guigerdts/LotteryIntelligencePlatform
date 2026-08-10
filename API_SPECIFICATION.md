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

3. Lottery Endpoints

List Lotteries

GET

/lotteries

---

Get Lottery

GET

/lotteries/{id}

---

Create Lottery

POST

/lotteries

---

Update Lottery

PUT

/lotteries/{id}

---

Delete Lottery

DELETE

/lotteries/{id}

---

4. Draw Endpoints

List Draws

GET

/draws

Supports:

- pagination
- filters
- ordering

---

Get Draw

GET

/draws/{id}

---

Latest Draw

GET

/draws/latest

---

Import Draws

POST

/draws/import

---

Upload CSV

POST

/draws/upload

---

5. Statistics

Summary

GET

/statistics/summary

---

Frequencies

GET

/statistics/frequencies

---

Gaps

GET

/statistics/gaps

---

Hot Numbers

GET

/statistics/hot

---

Cold Numbers

GET

/statistics/cold

---

Distribution

GET

/statistics/distribution

---

Correlations

GET

/statistics/correlation

---

6. Probability

GET

/probability/montecarlo

---

GET

/probability/bayes

---

GET

/probability/hypergeometric

---

GET

/probability/binomial

---

7. Features

GET

/features

---

GET

/features/{id}

---

POST

/features/recalculate

---

GET

/features/categories

---

8. Machine Learning

GET

/ml/models

---

POST

/ml/train

---

POST

/ml/predict

---

GET

/ml/metrics

---

GET

/ml/ranking

---

9. Deep Learning

POST

/dl/train

---

GET

/dl/models

---

GET

/dl/metrics

---

10. Backtesting

POST

/backtesting/run

---

GET

/backtesting/history

---

GET

/backtesting/results

---

11. Experiments

GET

/experiments

---

POST

/experiments

---

GET

/experiments/{id}

---

POST

/experiments/{id}/run

---

12. Generator

POST

/generator/run

Body

{
  "lottery": "baloto",
  "strategy": "ensemble_v1",
  "count": 2
}

---

GET

/generator/history

---

GET

/generator/{id}

---

13. Dashboard

GET

/dashboard/overview

---

GET

/dashboard/charts

---

GET

/dashboard/heatmap

---

GET

/dashboard/network

---

14. AI Assistant

POST

/assistant/chat

---

POST

/assistant/explain

---

POST

/assistant/analyze

---

15. Configuration

GET

/config

---

PUT

/config

---

16. Health

GET

/health

---

GET

/version

---

GET

/metrics

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
