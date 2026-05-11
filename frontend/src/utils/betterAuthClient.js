import { createAuthClient } from 'better-auth/react'

export const betterAuthClient = createAuthClient({
  baseURL: import.meta.env.VITE_BETTER_AUTH_URL || window.location.origin,
})

export const betterAuthStatus = {
  mode: 'bridge-ready',
  runtimeAuth: 'FastAPI JWT auth remains active',
  nextStep: 'Add a JS/TS Better Auth server route before switching login/signup flows',
}
