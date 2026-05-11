# Browser Assist Companion Prompt

This file is the focused companion for Browser Assist.
Follow `CLAUDE_CODE_UNIFIED_MASTER_PROMPT.md` for product mission, privacy, ownership, honesty, and verification standards.

## Current Implemented Behavior

Browser Assist currently supports:
- creating a run from an approved list of URLs
- associating a run with a search and optionally a project
- owner-scoped run retrieval
- SSE streaming for run updates
- canceling a run
- storing run logs
- storing visited URLs
- storing artifacts when persistence is allowed
- requiring explicit confirmation for incognito runs
- automatically disabling artifact persistence for incognito runs
- per-user rate limiting
- URL validation before the run starts

Current API surface:
- `POST /api/browser-assist/runs`
- `GET /api/browser-assist/runs/{run_id}`
- `GET /api/browser-assist/runs/{run_id}/stream`
- `POST /api/browser-assist/runs/{run_id}/cancel`

## Browser Assist Rules

- Every run must be explicitly initiated from approved URLs.
- Only the run owner may fetch or cancel the run.
- Invalid or unsafe URLs must fail before execution.
- Incognito mode requires explicit confirmation.
- Incognito mode must not persist artifacts.
- Run logs should remain understandable to a tester.
- UI and API responses must never imply that screenshots are guaranteed in every environment.

## Artifact Expectations

Treat artifact capture as a best-effort workflow.

Current expectation:
- when the runtime supports the stronger browser path, screenshots and richer artifacts should be captured
- when that path is unavailable, the system may fall back to lighter metadata or snippet capture

Do not describe the fallback path as equivalent to full browser capture.

## Save-To-Project Behavior

If a run is associated with a project:
- the project must belong to the current user
- the run must not attach to foreign projects
- artifact persistence should remain consistent with incognito restrictions

## Tester Checklist

Use this checklist when validating Browser Assist:

1. Start a run from a search result cluster and confirm a `run_id` is returned.
2. Confirm the run stream updates status and run-log entries.
3. Cancel a run and confirm the run status becomes `cancelled`.
4. Fetch run details and confirm artifacts are only visible to the owner.
5. Attempt an incognito run without confirmation and confirm it fails.
6. Start an incognito run with confirmation and confirm `persist_artifacts` is off.
7. Attempt an invalid or disallowed URL and confirm the request fails before execution.

Expected outcomes:
- owner-only access
- explicit incognito gating
- visible run lifecycle
- honest degraded behavior when richer capture is unavailable

## Not Yet Implemented / Do Not Overclaim

Do not overstate any of the following:
- universal screenshot capture
- persistent third-party browser sessions
- unrestricted browsing across arbitrary internal or unsafe targets
- full production browser automation parity across all environments

If Playwright or the stronger capture path is unavailable, say so directly.
