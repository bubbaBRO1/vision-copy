import { create } from 'zustand'

export const useSearchStore = create((set, get) => ({
  currentSearchId: null,
  status: 'idle', // idle | uploading | running | done | failed
  stages: [],     // [{name, status, elapsed_ms, data}]
  results: null,
  filename: null,
  progress: 0,

  startSearch: (searchId, filename) => set({
    currentSearchId: searchId,
    status: 'running',
    stages: [],
    results: null,
    filename,
    progress: 0,
  }),

  updateStage: (name, status, data) => set((state) => {
    const existing = state.stages.find(s => s.name === name)
    const stages = existing
      ? state.stages.map(s => s.name === name ? { ...s, status, data } : s)
      : [...state.stages, { name, status, data }]
    const done = stages.filter(s => s.status === 'done').length
    const progress = Math.round((done / Math.max(stages.length, 1)) * 100)
    return { stages, progress }
  }),

  setResults: (results) => set({ results, status: 'done' }),
  setError: (error) => set({ status: 'failed', error }),
  reset: () => set({ currentSearchId: null, status: 'idle', stages: [], results: null, progress: 0 }),
}))
