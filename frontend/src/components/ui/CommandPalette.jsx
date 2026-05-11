import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, ScanSearch, Brain, Clock, Folder, Settings,
  Users, LogOut, Sun, Moon, Search, ArrowRight, Shield, Briefcase,
  Globe, Activity,
} from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { useThemeStore } from '../../store/themeStore'
import api from '../../utils/api'

const NAV_COMMANDS = [
  { id: 'dashboard',    label: 'Go to Dashboard',      icon: LayoutDashboard, path: '/dashboard' },
  { id: 'projects',     label: 'Cases',                 icon: Briefcase,       path: '/projects' },
  { id: 'search',       label: 'New Image Search',      icon: ScanSearch,      path: '/search' },
  { id: 'research',     label: 'Go to Research',        icon: Brain,           path: '/research' },
  { id: 'faces',        label: 'Face Database',         icon: Users,           path: '/faces' },
  { id: 'history',      label: 'Search History',        icon: Clock,           path: '/history' },
  { id: 'collections',  label: 'Collections',           icon: Folder,          path: '/collections' },
  { id: 'settings',     label: 'Settings',              icon: Settings,        path: '/settings' },
  { id: 'system',       label: 'System Health',         icon: Activity,        path: '/system' },
]

const RESULT_TYPE_ICONS = { project: Briefcase, search: ScanSearch, collection: Folder, chat: Brain }

function Kbd({ children }) {
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded font-medium mono"
      style={{ background: 'var(--surface-4)', color: 'var(--text-tertiary)', border: '1px solid var(--border)' }}
    >
      {children}
    </span>
  )
}

function CommandItem({ item, active, onSelect }) {
  const Icon = item.icon
  return (
    <button
      onClick={onSelect}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-[10px] text-left transition-all duration-100"
      style={{
        background: active ? 'var(--ios-blue, #0A84FF)' : 'transparent',
        color: active ? '#fff' : 'var(--text-primary)',
      }}
    >
      <Icon size={16} style={{ opacity: active ? 1 : 0.6 }} />
      <span className="flex-1 text-sm font-medium">{item.label}</span>
      {item.shortcut && (
        <div className="flex gap-1 items-center">
          {item.shortcut.map((k, i) => <Kbd key={i}>{k}</Kbd>)}
        </div>
      )}
      {active && <ArrowRight size={14} className="opacity-60" />}
    </button>
  )
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const [globalResults, setGlobalResults] = useState([])
  const inputRef = useRef(null)
  const abortRef = useRef(null)
  const navigate = useNavigate()
  const { logout, isGuest } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()

  const COMMANDS = [
    ...NAV_COMMANDS,
    {
      id: 'theme',
      label: theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode',
      icon: theme === 'dark' ? Sun : Moon,
      action: toggleTheme,
    },
    {
      id: 'logout',
      label: 'Log Out',
      icon: LogOut,
      action: () => { logout(); window.location.href = '/login' },
    },
  ]

  const navFiltered = query.trim()
    ? COMMANDS.filter(c => c.label.toLowerCase().includes(query.toLowerCase()))
    : COMMANDS

  const apiResults = globalResults.map(r => ({
    id: `global-${r.type}-${r.id}`,
    label: r.label,
    icon: RESULT_TYPE_ICONS[r.type] || Globe,
    path: r.url,
    badge: r.type,
  }))

  const filtered = query.trim() && !isGuest()
    ? [...apiResults, ...navFiltered]
    : navFiltered

  const openPalette = useCallback(() => {
    setOpen(true)
    setQuery('')
    setSelected(0)
  }, [])

  // Expose globally for the sidebar ⌘K button
  useEffect(() => {
    window.__commandPaletteOpen = openPalette
    return () => { delete window.__commandPaletteOpen }
  }, [openPalette])

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(o => {
          if (!o) { setQuery(''); setSelected(0) }
          return !o
        })
      }
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50)
  }, [open])

  useEffect(() => { setSelected(0); setGlobalResults([]) }, [query])

  useEffect(() => {
    if (!query.trim() || query.length < 2 || isGuest()) return
    if (abortRef.current) abortRef.current.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get(`/api/search/global?q=${encodeURIComponent(query)}&limit=10`, { signal: ctrl.signal })
        setGlobalResults(data.results || [])
      } catch {
        // ignore abort/network errors
      }
    }, 250)
    return () => { clearTimeout(timer); ctrl.abort() }
  }, [query])

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, filtered.length - 1)) }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)) }
    if (e.key === 'Enter') {
      e.preventDefault()
      if (filtered[selected]) execute(filtered[selected])
    }
  }

  const execute = (cmd) => {
    setOpen(false)
    if (cmd.path) navigate(cmd.path)
    else if (cmd.action) cmd.action()
  }

  if (typeof document === 'undefined') return null

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-50"
            style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
          />

          {/* Modal */}
          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.96, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -8 }}
            transition={{ duration: 0.18, ease: [0.34, 1.2, 0.64, 1] }}
            className="fixed top-[20vh] left-1/2 z-50 -translate-x-1/2 w-full max-w-[560px] px-4"
          >
            <div
              className="rounded-xl overflow-hidden"
              style={{
                background: 'var(--surface-2)',
                border: '1px solid var(--border)',
                boxShadow: 'var(--shadow-xl)',
              }}
            >
              {/* Search input */}
              <div className="flex items-center gap-3 px-4 border-b" style={{ borderColor: 'var(--border)' }}>
                <Search size={16} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Search commands…"
                  className="flex-1 bg-transparent outline-none py-4 text-[15px]"
                  style={{ color: 'var(--text-primary)', fontFamily: 'Inter, sans-serif' }}
                />
                <Kbd>Esc</Kbd>
              </div>

              {/* Results */}
              <div className="p-2 max-h-80 overflow-y-auto">
                {filtered.length === 0 ? (
                  <p className="text-center py-6 text-sm" style={{ color: 'var(--text-tertiary)' }}>
                    No results found
                  </p>
                ) : (
                  <>
                    {query.trim() && apiResults.length > 0 && (
                      <>
                        <p className="px-3 pt-1 pb-1 text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                          Results
                        </p>
                        {apiResults.map((cmd, i) => (
                          <CommandItem key={cmd.id} item={cmd} active={selected === i} onSelect={() => execute(cmd)} />
                        ))}
                        {navFiltered.length > 0 && (
                          <p className="px-3 pt-2 pb-1 text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                            Commands
                          </p>
                        )}
                        {navFiltered.map((cmd, i) => (
                          <CommandItem key={cmd.id} item={cmd} active={selected === apiResults.length + i} onSelect={() => execute(cmd)} />
                        ))}
                      </>
                    )}
                    {(!query.trim() || apiResults.length === 0) && (
                      <>
                        {!query && (
                          <p className="px-3 pt-1 pb-1 text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                            Navigation
                          </p>
                        )}
                        {navFiltered.map((cmd, i) => (
                          <CommandItem key={cmd.id} item={cmd} active={selected === i} onSelect={() => execute(cmd)} />
                        ))}
                      </>
                    )}
                  </>
                )}
              </div>

              {/* Footer hint */}
              <div
                className="flex items-center gap-3 px-4 py-2.5 border-t"
                style={{ borderColor: 'var(--border)', color: 'var(--text-tertiary)' }}
              >
                <span className="text-[11px] flex items-center gap-1.5"><Kbd>↑↓</Kbd> navigate</span>
                <span className="text-[11px] flex items-center gap-1.5"><Kbd>↵</Kbd> select</span>
                <span className="text-[11px] flex items-center gap-1.5"><Kbd>Esc</Kbd> close</span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
}
