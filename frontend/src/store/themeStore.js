import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useThemeStore = create(
  persist(
    (set, get) => ({
      theme: 'dark',

      toggleTheme: () => {
        const next = get().theme === 'dark' ? 'light' : 'dark'
        document.documentElement.setAttribute('data-theme', next)
        set({ theme: next })
      },

      applyTheme: () => {
        document.documentElement.setAttribute('data-theme', get().theme)
      },
    }),
    { name: 'vision-theme', partialize: (s) => ({ theme: s.theme }) }
  )
)
