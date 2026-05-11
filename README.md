# VISION

VISION is a self-hosted visual intelligence and OSINT workstation. It is built around cases: collect image-search leads, browser-assist artifacts, notes, AI summaries, timelines, evidence, and reports in one local workspace.

## What Is Included

- React/Vite frontend with case workspace, search, research, face database, collections, admin, settings, and system health.
- FastAPI backend with auth, search orchestration, browser assist, case evidence, AI insights, exports, and health diagnostics.
- Postgres, Redis, Ollama, backend, frontend, and nginx services through Docker Compose.
- Prompt/spec references used to shape the product:
  - `CLAUDE_CODE_UNIFIED_MASTER_PROMPT.md`
  - `BROWSER_ASSIST_MASTER_PROMPT.md`
  - `PIMEYES_LIKE_RESULTS_MASTER_PROMPT.md`
  - `VISION_FACE_PARITY_PROMPT.md`
  - `Already used prompts/VISION_MASTER_PROMPT_V2.md`

## Quick Start

Copy `.env.example` to `.env`, then set a real `JWT_SECRET` and any optional API keys you want to use.

```powershell
cd C:\Users\bubba\Desktop\vision-copy
docker compose up --build
```

Open:

```text
http://localhost
```

For frontend-only development:

```powershell
cd C:\Users\bubba\Desktop\vision-copy\frontend
npm install
npm run dev
```

## Verification

Backend tests:

```powershell
cd C:\Users\bubba\Desktop\vision-copy
backend\venv\Scripts\python.exe -m pytest backend\tests -q
```

Frontend tests:

```powershell
cd C:\Users\bubba\Desktop\vision-copy\frontend
npm test
```

Frontend build:

```powershell
npm run build
```

Docker config:

```powershell
cd C:\Users\bubba\Desktop\vision-copy
docker compose config
```

## Case Workflow

1. Create a case from the Cases page.
2. Run an image search.
3. Review clustered results and choose a case in the inspector.
4. Promote useful results into case evidence.
5. Verify, reject, tag, and annotate evidence.
6. Run AI analyst actions for summaries, next steps, source review, contradictions, entity extraction, and timeline synthesis.
7. Export Markdown, HTML, JSON, or ZIP reports with provenance.

## Safety Notes

- AI outputs are investigative aids, not proof.
- External search and face matching results can be incomplete or wrong.
- Keep `.env`, local uploads, face databases, and generated artifacts out of git.
- Do not expose this publicly until secrets, registration, rate limits, and nginx/TLS settings are reviewed.
