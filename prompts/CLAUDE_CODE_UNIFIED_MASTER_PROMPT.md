# VISION Unified Master Prompt

This is the authoritative master prompt for VISION.

Use this file as the single source of truth for:
- product mission
- safety and privacy guardrails
- ownership boundaries
- honesty and confidence language
- prompt-system architecture
- implementation priorities
- verification and reporting standards

Companion prompts may add subsystem-specific detail, but they must not override this file on safety, privacy, honesty, incognito behavior, cross-user boundaries, or verification expectations.

## Mission

Build VISION into a trustworthy image-investigation workspace that helps a user:
- analyze an uploaded image
- inspect reverse-search evidence
- review location and forensic clues
- cluster and triage result quality
- run controlled Browser Assist follow-up
- search the user's private local face index

The product goal is not to impress with inflated claims.
The goal is to produce a tool a serious tester can run, inspect, and verify.

## Current Implemented Capabilities

Document and build against what the code actually supports now:

- clustered reverse-search results workspace
  - clustered by normalized result URL
  - result filtering by query, score floor, strong-only, and hidden-state toggle
  - result save, hide, and note state per user and per search
  - result inspector panel with Browser Assist artifacts when available

- Browser Assist
  - explicit run creation per approved URL set
  - owner-scoped runs
  - SSE run streaming
  - cancel flow
  - run logs
  - artifact persistence when allowed
  - incognito confirmation requirement
  - artifact persistence disabled for incognito runs
  - SSRF-style URL validation and rate limiting

- direct local face search
  - upload query image to search the local FaceDB
  - return ranked local matches
  - return search timing and total matches
  - expose face index stats endpoints

## Not Yet Implemented / Do Not Overclaim

Do not describe the following as complete unless the code truly earns it:

- full pgvector-backed persistent face-search storage
- FAISS-backed in-memory ANN parity
- large-scale ingestion or public-web crawler parity
- broad premium-provider parity across all reverse-search and face-search workflows
- guaranteed Browser Assist screenshots in all environments

If a capability exists only as a direction, roadmap item, or partial implementation, say so plainly.

## Non-Negotiable Guardrails

- Never mix data across users.
- Never bypass owner checks for searches, projects, Browser Assist runs, or face index data.
- Never describe inferred location as exact unless directly evidenced.
- Never imply third-party biometric or external-provider parity without measured proof.
- Never silently persist artifacts from incognito Browser Assist runs.
- Never turn a partial clue into a certainty claim.
- Never hide missing dependencies or degraded fallbacks from the tester.

## Ownership And Privacy Rules

- User-owned searches remain owner-scoped unless the implementation explicitly supports broader visibility.
- Browser Assist runs, artifacts, and result-state records must stay owner-scoped.
- Incognito behavior must be explicit.
  - incognito requires confirmation
  - persisted artifacts must be off for incognito
  - logs and UI wording must not imply hidden persistence
- Local face search operates on the current user's private face index.
- If a feature depends on server-side folder indexing, that path must remain restricted by configured server-side limits.

## Honesty And Confidence Language

Use only the following confidence language unless a subsystem requires a more specific label:

- `Likely`
- `Possible`
- `Low confidence`
- `Unknown`

Use `Exact` only when directly supported by verifiable evidence such as:
- explicit coordinates from trusted metadata
- direct canonical source records
- exact deterministic identifiers

For face search, local similarity labels should remain obviously interpretive, not absolute proof.

For geolocation, treat metadata, visual cues, and reverse-search context as evidence tiers, not certainty shortcuts.

## Prompt System Architecture

Prompt logic must be centralized and role-based, not scattered across hardcoded strings.

Required prompt roles:
- core system / product authority
- chat or assistant reasoning
- image analysis
- reverse-search and result triage
- geolocation reasoning
- dossier or report generation
- Browser Assist or evidence follow-up
- face-search infrastructure reasoning

Implementation rules:
- one authoritative master prompt
- focused companion prompts for subsystem detail
- explicit prompt selection by workflow
- no hidden prompt concatenation from scattered literals
- fallback to the unified prompt plus the smallest relevant companion when a specialized prompt is missing
- version prompts as real project assets, not ad hoc inline text blobs

## Priority Order

Prioritize work in this order unless a concrete bug or blocker changes the order:

1. trust, privacy, owner scoping, and anti-overclaim fixes
2. testable end-to-end workflows
3. result quality and triage clarity
4. Browser Assist stability and evidence handling
5. local face-search usefulness and performance
6. future parity architecture such as pgvector, FAISS, and larger ingestion systems

## Companion Prompt Contract

Use the companion prompts only for their subsystem-specific detail:

- `prompts/BROWSER_ASSIST_MASTER_PROMPT.md`
  - Browser Assist workflow, safeguards, and tester checks
- `prompts/PIMEYES_LIKE_RESULTS_MASTER_PROMPT.md`
  - clustered results workspace behavior and testing expectations
- `prompts/VISION_FACE_PARITY_PROMPT.md`
  - local face-search infrastructure, current-state truth, and future parity direction

`CLAUDE_CODE_MASTER_PROMPT.md` is a compatibility shim only.

Precedence order:
1. this unified master prompt
2. the relevant companion prompt
3. current codebase facts and implementation constraints

## Verification Standard

Do not claim a feature is done because the design sounds right.
Verify it against the code and against runnable checks when possible.

For this project, verification should prefer:
- backend `pytest`
- backend compile/import checks
- frontend `npm run build`
- frontend `npm run lint`
- direct manual testing of Browser Assist, clustered results, and local face search

If a check is blocked, report the blocker exactly.
Example: frontend `npm test` expects `vitest`, but the local install is currently missing it.

## Reporting Standard

When summarizing work:
- state what is implemented now
- state what is still partial or missing
- name degraded modes and fallbacks
- report actual verification results
- avoid promising parity, precision, or production-hardening that has not been measured

This file is the only prompt that defines the global product contract.
