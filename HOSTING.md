# VISION Testing And Hosting Guide

This guide is optimized for someone who wants to boot VISION and test what is implemented today.
Public hosting notes are included later, but local testing comes first.

## What You Can Test Right Now

Current testable workflows:
- image upload and search execution
- clustered reverse-search results workspace
- result save, hide, and note state
- Browser Assist run creation, streaming, cancel flow, and artifact retrieval
- direct local face search from an uploaded query image
- face index stats endpoints

Current known limitation:
- `frontend` test automation is not fully runnable in this environment because `npm test` expects `vitest`, but the local install is currently missing it

## Fastest Local Start

From `C:\Users\bubba\Desktop\vision-copy`:

1. Copy `.env.example` to `.env` if needed.
2. Set `JWT_SECRET` and review database credentials.
3. Run `vision.bat`.
4. Choose one of these modes:
   - `[1] Docker` for the full stack
   - `[2] Dev` for local backend and frontend
   - `[3] Dev+DB` for local app servers with Docker Postgres and Redis

### Expected Local URLs

- Docker mode:
  - frontend: `http://localhost`
  - backend API: `http://localhost/api`
  - API docs: `http://localhost/api/docs`

- Dev mode:
  - frontend: `http://localhost:5173`
  - backend API: `http://localhost:8000`
  - API docs: `http://localhost:8000/docs`

## Required Services

Full Docker mode uses:
- frontend
- backend
- nginx
- postgres
- redis
- ollama

Dev mode expects:
- Python environment for the backend
- Node environment for the frontend
- PostgreSQL and Redis either local or provided by Docker

## Suggested Testing Order

1. Start the stack with `vision.bat`.
2. Confirm the backend docs load.
3. Create or sign in to a user account if needed.
4. Upload an image and wait for search completion.
5. Open the results tab and test clustering, filtering, save, hide, and note state.
6. Launch Browser Assist from a result cluster.
7. Open the face-search page and test direct local face search.

## Verification Commands

These are the checks currently known to be useful and truthful:

### Backend

Run from `C:\Users\bubba\Desktop\vision-copy\backend`:

```bash
pytest
python -m compileall . -q
```

Expected status:
- `pytest` should pass
- compile check should pass

### Frontend

Run from `C:\Users\bubba\Desktop\vision-copy\frontend`:

```bash
npm run lint
npm run build
```

Expected status:
- `npm run build` should pass
- `npm run lint` may still report warnings from older code, but should not fail on errors

### Known Test Blocker

```bash
npm test
```

Current blocker:
- the script expects `vitest`
- the local install is currently missing it
- this should be reported honestly instead of treated as a passing gate

## Browser Assist Notes

Browser Assist currently supports:
- explicit per-run creation from approved URLs
- owner-scoped run inspection
- SSE streaming
- cancel flow
- incognito confirmation
- persisted artifacts only when persistence is allowed

Important limitation:
- richer screenshot capture is best when the stronger browser runtime is available
- fallback artifact capture may be lighter in reduced environments

## Face Search Notes

Current local face-search testing should focus on:
- `POST /api/faces/search`
- `GET /api/faces/index/stats`

Be explicit with testers:
- direct upload search is implemented now
- full pgvector or FAISS parity is not
- larger ingestion or crawler parity is not

## Public Hosting

If you want to expose the app publicly after local testing, prefer one of these:
- Cloudflare Tunnel
- Caddy
- nginx with TLS and SSE-safe proxy settings

### Cloudflare Tunnel

1. Install `cloudflared`
2. Run `cloudflared tunnel login`
3. Run `cloudflared tunnel create vision`
4. Set in `.env`:

```env
PRODUCTION=true
FRONTEND_URL=https://your-subdomain.your-domain.com
```

5. Run:

```bash
cloudflared tunnel route dns vision your-subdomain.your-domain.com
cloudflared tunnel run vision
```

### Caddy

Use a `Caddyfile` like:

```text
your-domain.com {
    reverse_proxy localhost:80
}
```

Set in `.env`:

```env
PRODUCTION=true
FRONTEND_URL=https://your-domain.com
```

### nginx

If you use nginx, keep SSE-safe proxy settings such as:
- `proxy_buffering off`
- `proxy_cache off`
- `proxy_read_timeout 600s`

## Security Checklist Before Public Access

- set a real `JWT_SECRET`
- change the default Postgres password
- set `PRODUCTION=true`
- set `FRONTEND_URL` to the real public domain
- do not expose Redis publicly
- do not expose Ollama publicly
- keep rate limits enabled

## Environment Variables To Review

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET`
- `PRODUCTION`
- `FRONTEND_URL`
- `ANTHROPIC_API_KEY`
- `TINEYE_API_KEY`
- `GEOSPY_API_KEY`
- `SHODAN_API_KEY`
- `HCAPTCHA_SECRET`
- `FACEDB_INDEX_ROOT`

## Final Honesty Rule

Hand this project to testers as a real, partially advanced build:
- Browser Assist is usable now
- clustered results are usable now
- direct local face search is usable now
- some deeper parity work is still future work

Do not blur that line.
