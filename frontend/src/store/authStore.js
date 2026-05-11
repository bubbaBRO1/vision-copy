import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,

      setUser: (user) => set({ user }),
      setAccessToken: (token) => set({ accessToken: token }),

      login: (user, token) => set({ user, accessToken: token }),

      logout: () => {
        set({ user: null, accessToken: null })
      },

      isAuthenticated: () => !!get().user,
      isAdmin: () => get().user?.role === 'admin',
      isPro: () => ['admin', 'pro'].includes(get().user?.role),
      isGuest: () => get().user?.role === 'guest',
    }),
    { name: 'vision-auth', partialize: (s) => ({ user: s.user }) }
  )
)
