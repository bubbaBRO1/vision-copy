# VISION Face Search Infrastructure Brief

This file is the focused companion for face-search infrastructure.
Follow `CLAUDE_CODE_UNIFIED_MASTER_PROMPT.md` for product mission, privacy boundaries, honesty language, UI limits, and verification standards.

## Current Implemented Behavior

The codebase currently supports:
- local face index stats endpoints
- listing and labeling local indexed faces
- indexing uploads into the local FaceDB
- optional server-side folder indexing when `FACEDB_INDEX_ROOT` is configured
- searching the local face index using an uploaded query image
- searching the local face index using faces extracted from an existing search

Current API surface includes:
- `GET /api/faces/stats`
- `GET /api/faces/index/stats`
- `GET /api/faces/list`
- `POST /api/faces/index`
- `POST /api/faces/index-upload`
- `DELETE /api/faces/remove`
- `POST /api/faces/label`
- `GET /api/faces/search/{search_id}`
- `POST /api/faces/search`

The direct upload workflow is real and testable now.

## Current Search Behavior

The local upload search currently returns:
- `search_time_ms`
- `total_matches`
- ranked `matches`
- similarity-based confidence labels such as:
  - `Likely Match`
  - `Possible Match`
  - `Weak Signal`

All search and index operations must remain owner-scoped.

## Infrastructure Priorities

The next phase should improve the subsystem without pretending it already has parity.

Priority areas:
- persistent vector storage with indexed retrieval
- optional in-memory ANN acceleration
- safer and more scalable ingestion
- cleaner source metadata on matches
- measurable latency and recall improvements

## Not Yet Implemented / Do Not Overclaim

Do not present these as complete today:
- pgvector-backed production-grade embedding retrieval
- FAISS-backed in-memory parity
- large-scale crawl and ingestion parity
- robust distributed indexing workflows
- true premium face-search parity

State clearly that the current system is a useful private local face search, not a finished parity stack.

## Verification Focus

When validating this subsystem, check at minimum:

1. `POST /api/faces/search` accepts an uploaded image and returns a ranked response.
2. `GET /api/faces/index/stats` returns current index stats for the authenticated user.
3. owner scoping is enforced across search, stats, label, and remove flows.
4. similarity labels remain interpretive and do not overclaim certainty.
5. folder indexing rejects paths outside `FACEDB_INDEX_ROOT`.

Expected outcomes:
- current user only
- direct upload search works now
- stats endpoint is useful to a tester
- future parity work is described as future work, not present fact
