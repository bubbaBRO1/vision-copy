import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { Eye, ScanSearch, Brain, Clock, Folder, LayoutDashboard, Shield, LogOut, Settings, Sun, Moon, Users, Briefcase, Search as SearchIcon, Activity } from 'lucide-react'
import { useAuthStore } from './store/authStore'
import { useThemeStore } from './store/themeStore'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import Research from './pages/Research'
import History from './pages/History'
import Collections from './pages/Collections'
import SettingsPage from './pages/Settings'
import Admin from './pages/Admin'
import FaceDB from './pages/FaceDB'
import FaceSearch from './pages/FaceSearch'
import ProjectList from './pages/ProjectList'
import ProjectDetail from './pages/ProjectDetail'
import SystemHealth from './pages/SystemHealth'
import CommandPalette from './components/ui/CommandPalette'
import GuestBanner from './components/ui/GuestBanner'
import api from './utils/api'

function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, isAdmin } = useAuthStore()
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  if (adminOnly && !isAdmin()) return <Navigate to="/dashboard" replace />
  return children
}

function NavItem({ to, icon: Icon, label }) {
  const { pathname } = useLocation()
  const active = pathname === to || pathname.startsWith(to + '/')
  return (
    <Link
      to={to}
      className={`flex items-center gap-2.5 px-3 py-2 rounded-[10px] text-sm font-medium transition-all duration-150 ${
        active
          ? 'bg-ios-blue/15 text-ios-blue'
          : 'text-text-secondary hover:text-text-primary hover:bg-surface-3'
      }`}
    >
      <Icon size={16} />
      <span>{label}</span>
    </Link>
  )
}

function AppLayout({ children }) {
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()

  const handleLogout = async () => {
    try { await api.post('/auth/logout') } catch { /* ignore */ }
    logout()
    window.location.href = '/login'
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface-1">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 border-r flex flex-col" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
        {/* Logo */}
        <div className="px-4 py-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-ios-blue flex items-center justify-center">
              <Eye size={14} className="text-white" />
            </div>
            <span className="font-semibold text-[15px] text-text-primary tracking-[-0.01em]">VISION</span>
          </div>
          <button
            onClick={() => window.__commandPaletteOpen?.()}
            className="text-[10px] font-medium px-1.5 py-0.5 rounded-md text-text-tertiary hover:text-text-secondary transition-colors"
            style={{ background: 'var(--surface-3)', border: '1px solid var(--border)' }}
            title="Command palette"
          >
            ⌘K
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" />
          <NavItem to="/projects" icon={Briefcase} label="Cases" />
          <NavItem to="/search" icon={ScanSearch} label="Search" />
          <NavItem to="/research" icon={Brain} label="Research" />
          <NavItem to="/faces" icon={Users} label="Face Database" />
          <NavItem to="/face-search" icon={SearchIcon} label="Face Search" />
          <NavItem to="/history" icon={Clock} label="History" />
          <NavItem to="/collections" icon={Folder} label="Collections" />
          <NavItem to="/system" icon={Activity} label="System Health" />
          {user?.role === 'admin' && (
            <>
              <div className="my-2 border-t" style={{ borderColor: 'var(--border)' }} />
              <NavItem to="/admin" icon={Shield} label="Admin" />
            </>
          )}
        </nav>

        {/* User */}
        <div className="px-3 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold text-white flex-shrink-0"
              style={{ background: 'var(--blue)' }}
            >
              {user?.username?.[0]?.toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-medium text-text-primary truncate">{user?.username}</p>
              <p className="text-[11px] text-text-tertiary truncate">{user?.role}</p>
            </div>
            <button onClick={toggleTheme} className="text-text-tertiary hover:text-text-secondary transition-colors p-1" title="Toggle theme">
              {theme === 'dark' ? <Sun size={13} /> : <Moon size={13} />}
            </button>
            <Link to="/settings" className="text-text-tertiary hover:text-text-secondary transition-colors p-1" title="Settings">
              <Settings size={13} />
            </Link>
            <button onClick={handleLogout} className="text-text-tertiary hover:text-ios-red transition-colors p-1" title="Logout">
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-hidden flex flex-col">
        <GuestBanner />
        {children}
      </main>

      <CommandPalette />
    </div>
  )
}

export default function App() {
  useEffect(() => {
    useThemeStore.getState().applyTheme()

    const { user, accessToken, setAccessToken, logout } = useAuthStore.getState()
    if (user && !accessToken) {
      api.post('/auth/refresh')
        .then(({ data }) => setAccessToken(data.access_token))
        .catch(() => logout())
    }
  }, [])

  return (
    <BrowserRouter>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'var(--surface-3)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--shadow-lg)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '13px',
            fontFamily: 'Inter, -apple-system, sans-serif',
          },
          success: { iconTheme: { primary: 'var(--green)', secondary: 'var(--surface-3)' } },
          error:   { iconTheme: { primary: 'var(--red)',   secondary: 'var(--surface-3)' } },
        }}
      />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/dashboard" element={
          <ProtectedRoute><AppLayout><Dashboard /></AppLayout></ProtectedRoute>
        } />
        <Route path="/search" element={
          <ProtectedRoute><AppLayout><Search /></AppLayout></ProtectedRoute>
        } />
        <Route path="/research" element={
          <ProtectedRoute><AppLayout><Research /></AppLayout></ProtectedRoute>
        } />
        <Route path="/faces" element={
          <ProtectedRoute><AppLayout><FaceDB /></AppLayout></ProtectedRoute>
        } />
        <Route path="/face-search" element={
          <ProtectedRoute><AppLayout><FaceSearch /></AppLayout></ProtectedRoute>
        } />
        <Route path="/history" element={
          <ProtectedRoute><AppLayout><History /></AppLayout></ProtectedRoute>
        } />
        <Route path="/collections" element={
          <ProtectedRoute><AppLayout><Collections /></AppLayout></ProtectedRoute>
        } />
        <Route path="/settings" element={
          <ProtectedRoute><AppLayout><SettingsPage /></AppLayout></ProtectedRoute>
        } />
        <Route path="/admin" element={
          <ProtectedRoute adminOnly><AppLayout><Admin /></AppLayout></ProtectedRoute>
        } />
        <Route path="/projects" element={
          <ProtectedRoute><AppLayout><ProjectList /></AppLayout></ProtectedRoute>
        } />
        <Route path="/projects/:id" element={
          <ProtectedRoute><AppLayout><ProjectDetail /></AppLayout></ProtectedRoute>
        } />
        <Route path="/system" element={
          <ProtectedRoute><AppLayout><SystemHealth /></AppLayout></ProtectedRoute>
        } />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
