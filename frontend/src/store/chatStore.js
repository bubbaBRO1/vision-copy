import { create } from 'zustand'

export const CHAT_MODES = [
  { id: 'investigation', label: 'Investigation', description: 'OSINT investigation assistant' },
  { id: 'research',      label: 'Research',      description: 'Deep research with citations' },
  { id: 'location',      label: 'Location',      description: 'Geolocation inference analysis' },
  { id: 'face',          label: 'Face Analysis', description: 'Face search result reasoning' },
  { id: 'incognito',     label: 'Incognito',     description: 'Ephemeral — nothing stored' },
]

export const useChatStore = create((set, get) => ({
  sessions: [],
  activeSessionId: null,
  messages: [],
  isStreaming: false,
  model: 'llama3:8b',
  mode: 'investigation',
  isIncognito: false,

  setModel: (model) => set({ model }),
  setMode: (mode) => set({ mode, isIncognito: mode === 'incognito' }),
  setIncognito: (v) => set({ isIncognito: v, mode: v ? 'incognito' : 'investigation' }),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  appendToLast: (token) => set((s) => {
    const msgs = [...s.messages]
    if (msgs.length && msgs[msgs.length - 1].role === 'assistant') {
      msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], content: msgs[msgs.length - 1].content + token }
    } else {
      msgs.push({ role: 'assistant', content: token })
    }
    return { messages: msgs }
  }),

  setStreaming: (v) => set({ isStreaming: v }),

  newSession: (sessionId) => set({ activeSessionId: sessionId, messages: [] }),

  clearMessages: () => set({ messages: [], activeSessionId: null }),
}))
