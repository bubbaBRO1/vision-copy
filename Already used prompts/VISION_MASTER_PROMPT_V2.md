# VISION — Master Build Prompt v3.0
# Full-Stack Excellence Pass · Production-Grade · Real Multi-Module Product

---

## Project Location

You are working in `C:\Users\bubba\vision`.

---

## Mission

Transform this codebase into a **10/10 production-ready platform**: secure, fast, deeply useful, and deployable to a public URL where real users can sign up and use it.

This is not a cleanup pass. This is a full product transformation focused on adding real product depth (Projects, Chats, Search, Memory, Hosting) while keeping the codebase cohesive and safe.

You must improve and expand the product across:
- backend architecture and security
- frontend UX and workflows (do not restyle/rebrand the visual direction)
- authentication (Google OAuth, guest login) and session lifecycle
- privacy features (incognito chat mode)
- multi-module product surface (not just image search)
- projects, chats, global search, and workspace organization
- persistent memory and context continuity (per-user, controllable)
- background jobs and async reliability
- public hosting and deployment infrastructure (safe DIY)
- settings and personalization (theme + privacy + data controls)
- testing, linting, and developer experience
- observability and logging
- accessibility and responsiveness
- product completeness and depth

---

## Non-Negotiable Outcome

When you are done, this platform must feel:
- premium (like a serious product)
- trustworthy (secure, private, honest about limits)
- fast (snappy UI and efficient backend)
- expansive (a full investigation/workspace product)
- self-hostable (owner can run it locally and expose a public URL safely)
- multi-user ready (accounts, Google OAuth, guest sessions, incognito mode)

Do not make it merely larger. Make it better.

---

## Operating Rules

- Do not ask for permission for obvious improvements.
- Do not stop after analysis — inspect, plan, execute.
- Prefer high-leverage changes over broad sloppy rewrites.
- Preserve working behavior unless a change fixes a real flaw.
- Fix anything insecure, unreliable, or weakly designed.
- Add the smallest solid baseline of missing tooling and wire it in properly.
- Improve tangled architecture carefully without breaking the product.
- Verify changes with real commands.
- Do not add fake enterprise complexity or marketing claims the product cannot support.

---

## Product Vision: What This Must Become

VISION is a **DIY visual intelligence and investigation workspace** with multiple modules, unified navigation, and project-based organization.

Think less “single reverse-image page” and more “professional workspace with modes”.

### Required Modules (Sidebar / Taskbar)

Each module is a distinct route and sidebar entry:
- **Dashboard**: overview, recent activity, quick actions
- **Projects (Cases)**: case folders that organize searches/chats/evidence/notes
- **Search**: reverse image search + aggregation + ranking + evidence
- **Chats**: project-scoped chats + “New chat” from anywhere
- **Research**: long-form investigation and structured pipelines
- **History**: searchable activity log and replay
- **Collections**: saved evidence, organized and shareable
- **Settings**: theme + privacy + memory + account + exports
- **Admin (if role=admin)**: user management and audit tooling

### Core UX: Panelized App (No Restyle)

Do not rebrand or redesign the visual style direction. Keep the current UI language.

You may improve information architecture and layout so it feels like a real panelized app:
- left: projects + navigation + “New …” actions
- center: current workspace (search/chat/research)
- right (optional): inspector panel (evidence, metadata, map, confidence, timeline)

Add a **global search** UI that can search across:
- projects
- searches
- collections/evidence
- non-incognito chats

---

## Authentication and Accounts (Harden, Don’t Churn)

### Keep FastAPI Auth Unless Proven Inadequate

Do not migrate auth just because a different framework exists.
Do not introduce a JS/TS auth sidecar unless the current FastAPI auth cannot be cleanly hardened.

If the current auth is sound:
- harden cookies/sessions/refresh lifecycle
- remove risky token persistence
- enforce ownership checks everywhere

If it is not sound:
- propose the smallest viable fix first
- only then propose a migration (and justify it)

Note on “Better Auth”:
- Only consider Better Auth if you are explicitly migrating the entire auth stack to a JS/TS backend for a clear, proven reason.
- Otherwise, keep and harden the existing FastAPI auth.

---

## Required Auth Features

### Remove Waitlist Gating

- Remove every waitlist/invite/beta gating flow from the user journey.
- Anyone can sign up and use the product immediately.
- If you keep any gating code, it must be behind an explicit environment flag and OFF by default.

### Sign Up / Sign In

Make auth fast and minimal:
- email + password
- **Google OAuth** (first-class on login and signup)
- stable session restore
- logout that truly revokes/invalidates session tokens

### Continue as Guest

Add **Continue as Guest**:
- guest sessions have real functionality (Search, Chats, Projects) but sane limits
- guest data is ephemeral by default
- support upgrading guest → real account without losing project/search/chat data

### Incognito Chat Mode (Privacy)

Add an incognito mode for chats:
- incognito chats are clearly labeled
- incognito chats do not persist chat content server-side
- incognito chats do not appear in history, exports, global search, or project reports
- incognito still respects abuse controls (rate limits, file size limits)

---

## Ethical and Legal Guardrails — REQUIRED

### Location Inference (From Images)

- Never claim “exact location” from image analysis.
- All location output includes confidence and evidence basis.
- Use wording like “Likely region” / “Possible match” / “Insufficient evidence”.
- Present uncertainty visually (radius / bands) where mapping is used.

Location inference must be a workflow:
- extract and show EXIF when present (and clearly label it as potentially untrusted)
- surface visual evidence (text/signage, landmarks, terrain, language cues)
- show sources for any external lookup
- provide “What to verify next” steps

### Identity / Face Matching

If face/person matching exists or is expanded:
- require explicit consent and clear disclosure
- show match confidence, never identity certainty
- enforce strict ownership and access control
- do not build features that enable stalking/harassment/unauthorized surveillance

### Data Privacy

- user data isolation is strict (no cross-user access)
- guest data defaults to ephemeral
- incognito data is never persisted or logged
- export and delete flows are complete and verified

---

## Projects (Cases)

Implement Projects as a first-class system:
- create/rename/archive
- project overview with recent activity
- project-scoped searches, chats, saved evidence, and notes
- simple status (open/closed) if useful
- export project as a bundle (JSON/ZIP) and/or report (PDF/HTML) if feasible

---

## Search Quality and Evidence

Strengthen reverse image search:
- improve aggregation and deduplication across sources
- improve ranking and add explainability (“why this is ranked high”)
- add an evidence inspector panel: source URL, timestamps, hashes, confidence signals
- handle failures gracefully per-source (partial results still useful)

---

## Memory (Persistent, Safe, Controllable)

Add a real memory system:
- per-user memory store with clear UI controls
- memory can be project-scoped and user-global
- retrieval is relevant and cite what memory items influenced an answer
- provide retention settings, export, and delete

Hard rules:
- incognito sessions never write to memory
- guest memory is ephemeral by default

---

## Hosting and Public URL (DIY, Safe Defaults)

Support “host on my computer” safely:
- make reverse proxy behavior correct (cookies, secure flags, origins)
- rate limiting + request size limits
- clear docs for exposing a public URL safely
- do not encourage unsafe port-forwarding without warnings

Tunnel guidance is allowed as documentation and optional scripts, but avoid hardcoding unsafe defaults.

---

## High-Priority Fixes (Execute First)

Treat these as the highest-leverage items:
1. remove waitlist gating (default OFF)
2. add Google OAuth
3. add guest mode (upgradeable)
4. add incognito chat mode (non-persisted)
5. harden cookie/session security; reduce token exposure
6. enforce ownership checks on every user data read/write
7. lock down SSE/stream authorization
8. fix background task DB session lifecycles
9. implement Projects (cases) and project-scoped organization
10. implement global search across app entities
11. improve search dedupe/ranking and evidence inspector
12. implement memory with retention + export/delete + incognito rules
13. hosting hardening and docs (public URL safely)

---

## Verification Requirements (Repo-Realistic)

Run verification steps that match this repo. Prefer these (adjust only if the repo uses different commands):

- frontend:
  - `cd frontend && npm run lint`
  - `cd frontend && npm run build`
- backend:
  - run whatever test runner exists (if none, add a minimal baseline for the auth/security-critical pieces)
  - at minimum: `python -m compileall backend`
- full stack:
  - `docker compose up --build` (or existing scripts in this repo) and confirm health endpoints

If something cannot be verified, explain exactly why and add the smallest reliable verification you can.

---

## Final Report Requirements

After completing all work, produce a structured final report:
- what changed (by category: Security / Architecture / Feature / DX)
- security risks fixed (what risk was and what changed)
- new features added (Projects, Guest, Incognito, Google, Global Search, Memory)
- how location inference works and its limits
- how memory works (storage, retrieval, retention, export/delete, incognito behavior)
- hosting setup (local + safe public URL guidance)
- what verification passed
- remaining gaps (Critical / High / Medium / Low)

---

## Standard of Judgment

Optimize for:
- trust
- clarity
- usefulness
- production readiness

Do not optimize for “looks impressive in a diff.”

Make this platform feel like something serious people rely on.
