import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ScanSearch, Brain, Folder, Settings, MapPin, Shield, Users, Activity, Loader2, ChevronRight } from 'lucide-react'
import { BarChart, Bar, XAxis, ResponsiveContainer, Tooltip } from 'recharts'
import api from '../utils/api'
import { useAuthStore } from '../store/authStore'
import { formatDate } from '../utils/formatters'

const STATUS_COLOR = {
  done:    'var(--green)',
  failed:  'var(--red)',
  running: 'var(--blue)',
  pending: 'var(--orange)',
}

function StatCard({ label, value, icon: Icon, color, bg }) {
  return (
    <div
      className="card p-5 flex items-start gap-3"
      style={{ borderTop: `3px solid ${color}` }}
    >
      <div
        className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: bg }}
      >
        <Icon size={16} style={{ color }} />
      </div>
      <div>
        <p className="text-2xl font-bold tracking-tight">{value ?? '—'}</p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{label}</p>
      </div>
    </div>
  )
}

function ActiveSearch({ item }) {
  const stages = item.stages || []
  const done = stages.filter(s => s.status === 'done').length
  const total = stages.length || 1
  const pct = Math.round((done / total) * 100)
  return (
    <div
      className="p-4 rounded-xl border"
      style={{
        background: 'var(--surface-3)',
        borderColor: 'rgba(10,132,255,0.3)',
        boxShadow: '0 0 0 1px rgba(10,132,255,0.1)',
      }}
    >
      <div className="flex items-center gap-2 mb-2.5">
        <Loader2 size={14} style={{ color: 'var(--blue)' }} className="animate-spin flex-shrink-0" />
        <span className="text-sm font-medium flex-1 truncate">{item.filename || 'Analyzing…'}</span>
        <span className="text-xs mono font-semibold" style={{ color: 'var(--blue)' }}>{pct}%</span>
      </div>
      <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface-4)' }}>
        <div className="h-1 rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: 'var(--blue)' }} />
      </div>
      {stages.length > 0 && (
        <p className="text-xs mt-1.5" style={{ color: 'var(--text-secondary)' }}>
          {stages.find(s => s.status === 'running')?.name || 'Processing…'}
        </p>
      )}
    </div>
  )
}

const QUICK_CARDS = [
  { label: 'Image Search',    icon: ScanSearch, href: '/search',      desc: 'Reverse search, geolocation, forensics', color: 'var(--blue)',   bg: 'rgba(10,132,255,0.12)' },
  { label: 'Deep Research',   icon: Brain,      href: '/research',    desc: 'Multi-source AI research pipeline',       color: 'var(--indigo)', bg: 'rgba(94,92,230,0.12)' },
  { label: 'Face Database',   icon: Users,      href: '/faces',       desc: 'Local face index — DIY PimEyes',          color: 'var(--purple)', bg: 'rgba(191,90,242,0.12)' },
  { label: 'Collections',     icon: Folder,     href: '/collections', desc: 'Saved investigations',                    color: 'var(--teal)',   bg: 'rgba(64,203,224,0.12)' },
]

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-xs" style={{ boxShadow: 'var(--shadow-md)' }}>
      <p style={{ color: 'var(--text-secondary)' }}>{label}</p>
      <p className="font-semibold mt-0.5">{payload[0].value} searches</p>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuthStore()
  const [history, setHistory] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/api/history?limit=5').catch(() => ({ data: [] })),
      api.get('/api/stats').catch(() => ({ data: null })),
    ]).then(([histRes, statsRes]) => {
      setHistory(histRes.data || [])
      setStats(statsRes.data)
    }).finally(() => setLoading(false))
  }, [])

  const active = history.filter(h => h.status === 'running' || h.status === 'pending')
  const recent = history.filter(h => h.status !== 'running' && h.status !== 'pending')

  // Generate 7-day chart data
  const chartData = Array.from({ length: 7 }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - (6 - i))
    const label = d.toLocaleDateString('en-US', { weekday: 'short' })
    const count = stats?.daily?.[d.toISOString().slice(0, 10)] || 0
    return { label, count }
  })

  const statCards = [
    { label: 'Total Searches',    value: stats?.total_searches,  icon: ScanSearch, color: 'var(--blue)',   bg: 'rgba(10,132,255,0.12)' },
    { label: 'Faces Found',       value: stats?.total_faces,     icon: Users,      color: 'var(--purple)', bg: 'rgba(191,90,242,0.12)' },
    { label: 'Locations Found',   value: stats?.total_geolocated,icon: MapPin,     color: 'var(--green)',  bg: 'rgba(48,209,88,0.12)' },
    { label: 'Threats Detected',  value: stats?.total_threats,   icon: Shield,     color: 'var(--red)',    bg: 'rgba(255,69,58,0.12)' },
  ]

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6 overflow-y-auto h-full">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight">
            Welcome back, <span style={{ color: 'var(--blue)' }}>{user?.username}</span>
          </h1>
          <div className="flex items-center gap-2 mt-1.5">
            <span
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium"
              style={{
                background: user?.role === 'admin' ? 'rgba(255,69,58,0.15)' : user?.role === 'pro' ? 'rgba(10,132,255,0.15)' : 'var(--surface-3)',
                color: user?.role === 'admin' ? 'var(--red)' : user?.role === 'pro' ? 'var(--blue)' : 'var(--text-secondary)',
              }}
            >
              {user?.role}
            </span>
          </div>
        </div>
        <Link
          to="/settings"
          className="flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg transition-colors"
          style={{ background: 'var(--surface-3)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          <Settings size={13} /> Settings
        </Link>
      </div>

      {/* Stats */}
      {(stats || loading) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {loading
            ? Array(4).fill(0).map((_, i) => (
                <div key={i} className="h-24 rounded-xl skeleton" />
              ))
            : statCards.map(s => <StatCard key={s.label} {...s} />)
          }
        </div>
      )}

      {/* Activity chart */}
      {stats && (
        <div className="card p-5">
          <h2 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
            Activity — Last 7 Days
          </h2>
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'Inter, sans-serif' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)', radius: 6 }} />
              <Bar dataKey="count" fill="var(--blue)" radius={[4, 4, 0, 0]} maxBarSize={32} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Quick access */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>Quick Access</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {QUICK_CARDS.map(({ label, icon: Icon, href, desc, color, bg }) => (
            <Link
              key={label}
              to={href}
              className="card card-hover p-4 block group min-h-[110px]"
            >
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center mb-3"
                style={{ background: bg }}
              >
                <Icon size={16} style={{ color }} />
              </div>
              <h3 className="text-sm font-semibold">{label}</h3>
              <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{desc}</p>
            </Link>
          ))}
        </div>
      </div>

      {/* Active searches */}
      {active.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Activity size={13} style={{ color: 'var(--blue)' }} />
            <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Active</h2>
          </div>
          <div className="space-y-2">
            {active.map(item => <ActiveSearch key={item.search_id} item={item} />)}
          </div>
        </div>
      )}

      {/* Recent searches */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Recent</h2>
          <Link to="/history" className="text-xs" style={{ color: 'var(--blue)' }}>View all</Link>
        </div>
        {loading ? (
          <div className="space-y-2">
            {[0, 1, 2].map(i => <div key={i} className="h-14 rounded-xl skeleton" />)}
          </div>
        ) : recent.length === 0 ? (
          <div
            className="card p-10 text-center"
            style={{ borderStyle: 'dashed' }}
          >
            <ScanSearch size={36} className="mx-auto mb-3" style={{ color: 'var(--surface-5)' }} />
            <p className="text-sm font-medium">No searches yet</p>
            <p className="text-xs mt-1 mb-4" style={{ color: 'var(--text-secondary)' }}>Upload an image to get started</p>
            <Link to="/search" className="btn-primary text-xs px-4 py-2 inline-flex items-center gap-1.5">
              Analyze an image <ChevronRight size={12} />
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {recent.map(item => (
              <Link
                key={item.search_id}
                to={`/search?id=${item.search_id}`}
                className="card card-hover p-3.5 flex items-center gap-3 block"
              >
                <div
                  className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center"
                  style={{ background: 'var(--surface-4)' }}
                >
                  <ScanSearch size={13} style={{ color: 'var(--text-secondary)' }} />
                </div>
                <span className="text-sm font-medium flex-1 truncate">{item.filename || 'Untitled'}</span>
                <span
                  className="text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0"
                  style={{
                    background: `${STATUS_COLOR[item.status] || 'var(--surface-4)'}20`,
                    color: STATUS_COLOR[item.status] || 'var(--text-secondary)',
                  }}
                >
                  {item.status}
                </span>
                <span className="text-xs flex-shrink-0" style={{ color: 'var(--text-tertiary)' }}>
                  {formatDate(item.created_at)}
                </span>
                <ChevronRight size={13} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
