# Delta for Backend (`backend`)

**Change**: `fase-16-performance` · **Date**: 2026-08-18
**Slice**: S5b — ETag/304 on snapshot read endpoints (observable HTTP behavior).

## ADDED Requirements

### REQ-13: ETag/304 on Snapshot Read Endpoints

Read endpoints over immutable snapshots (statistics, probability, graph, ML, backtest) SHALL derive an `ETag` from the snapshot checksum/version and SHALL honor `If-None-Match`: a matching header SHALL return `304 Not Modified` with no body. The ETag SHALL change when the snapshot version changes (immutability — no write-through invalidation). A cached response MUST be byte-identical to a fresh response for the same snapshot version (golden check). This adds observable HTTP behavior to the REQ-11 read endpoints; it MUST NOT change the envelope on 200 responses or trigger any recompute.

#### Scenario: If-None-Match → 304 no body

- GIVEN a client holding the current `ETag` of a snapshot read
- WHEN it re-requests with `If-None-Match: <etag>`
- THEN the server returns `304 Not Modified` with an empty body

#### Scenario: cache hit equals fresh response byte-identical

- GIVEN a snapshot read served from cache
- WHEN the same snapshot is read fresh from the DB
- THEN both responses are byte-identical

#### Scenario: version bump invalidates the ETag

- GIVEN a cached snapshot read with ETag `v3`
- WHEN a new snapshot version `v4` is generated and read
- THEN the response is 200 with a new ETag `v4`, never a stale 304

#### Scenario: reads never recompute

- GIVEN a snapshot read request with a valid ETag
- WHEN the server answers 304 or 200
- THEN no generation or recompute is triggered (REQ-11 preserved)