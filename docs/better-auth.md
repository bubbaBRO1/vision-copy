# Better Auth Bridge

VISION currently runs authentication through the FastAPI backend. Better Auth is installed in the frontend as a bridge-ready dependency, but the active runtime login/signup flow remains the existing FastAPI JWT flow.

Why this is staged:

- The backend is Python/FastAPI, while Better Auth is a JavaScript/TypeScript auth framework.
- A safe migration needs a JS/TS auth route, database/session migration, cookie/session compatibility, and a rollback path.
- The app now defaults to open registration, so users can try VISION immediately without waitlist approval.

Installed pieces:

- `better-auth` package in `frontend/package.json`.
- `frontend/src/utils/betterAuthClient.js` with a React client scaffold.
- `VITE_BETTER_AUTH_URL` can point at a future Better Auth server.

Recommended next migration milestone:

1. Add a small Node/Hono or Next-style auth sidecar at `/api/auth/*`.
2. Configure Better Auth with Postgres and `emailAndPassword: { enabled: true }`.
3. Generate/apply Better Auth tables in a separate migration.
4. Add a compatibility adapter from Better Auth sessions to the FastAPI API.
5. Switch the React login/signup pages after end-to-end tests pass.

Do not remove the current FastAPI auth until Better Auth can create accounts, restore sessions, log out, protect API calls, and preserve existing users.
