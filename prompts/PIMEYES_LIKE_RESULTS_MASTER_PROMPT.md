# Premium Results Workspace Companion Prompt

This file is the focused companion for the search-results workspace.
Follow `CLAUDE_CODE_UNIFIED_MASTER_PROMPT.md` for product-wide safety, honesty, ownership, and verification rules.

## Current Implemented Behavior

The current results workspace supports:
- clustered reverse-search results grouped by normalized URL
- result ordering by strongest similarity signal in each cluster
- filter by free-text query
- filter by score floor
- strong-only toggle
- hidden-result toggle
- per-result save state
- per-result hidden state
- per-result notes
- inspector panel for the selected cluster
- Browser Assist launch from a cluster
- Browser Assist artifact display in the inspector when a matching source URL exists

Current backend interfaces:
- `GET /api/search/{search_id}/results`
- `PATCH /api/search/{search_id}/results/state`

Current UI expectations:
- the results tab is a clustered triage workspace, not a flat dump
- the selected cluster drives the inspector view
- save, hide, and note state are stored per user and per search

## Result Presentation Rules

- Prefer one cluster per normalized source URL.
- Show the best result first within each cluster.
- Keep filters fast and easy to verify by a tester.
- Hidden items must stay hidden by default unless the tester opts in to show them.
- Notes should be editable from the inspector and persist after reload.
- Browser Assist integration should feel attached to a selected evidence cluster, not to the whole search blindly.

## Location And Evidence Language

When the results workspace surfaces location-related context:
- present it as evidence, not proof
- avoid `Exact` unless directly evidenced
- distinguish between metadata clues, visual clues, and reverse-search context
- prefer `Likely`, `Possible`, `Low confidence`, or `Unknown`

## Tester Checklist

Use this checklist when validating the current results workspace:

1. Upload an image and wait for search completion.
2. Open the results tab and confirm clustered cards render.
3. Adjust the score floor and confirm clusters are filtered.
4. Toggle strong-only and confirm weaker clusters disappear.
5. Hide a cluster and confirm it disappears until `Show hidden` is enabled.
6. Save a cluster and confirm the saved state persists.
7. Add a note in the inspector, save it, and confirm it persists after reload.
8. Launch Browser Assist from a cluster and confirm related artifacts appear in the inspector when available.

Expected outcomes:
- cluster-first result triage
- owner-scoped state persistence
- straightforward filtering
- evidence-first inspector behavior

## Future-State / Not Yet Implemented

The following may still be desirable, but should not be described as fully complete today:
- richer premium clustering signals beyond normalized URL grouping
- more advanced evidence pinning and comparison workflows
- broader inspector media previews
- stronger cross-engine result reconciliation
- full premium-provider UX parity

Keep future-state ideas clearly separated from the current implementation.
