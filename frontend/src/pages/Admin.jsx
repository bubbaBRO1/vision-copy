import { useState, useEffect } from 'react'
import { Users, List, BarChart2, CheckCircle, Settings, AlertTriangle, Eye, EyeOff, Save } from 'lucide-react'
import api from '../utils/api'
import toast from 'react-hot-toast'
import { formatDate } from '../utils/formatters'

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: BarChart2 },
  { id: 'users', label: 'Users', icon: Users },
  { id: 'waitlist', label: 'Waitlist', icon: List },
  { id: 'settings', label: 'Settings', icon: Settings },
]

function AdminDashboard() {
  const [stats, setStats] = useState(null)
  useEffect(() => { api.get('/admin/dashboard').then(r => setStats(r.data)) }, [])
  if (!stats) return <div className="skeleton h-32 rounded-lg" />
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[
        { label: 'Total Users', value: stats.total_users },
        { label: 'Searches Today', value: stats.searches_today },
        { label: 'Research Jobs Today', value: stats.research_jobs_today },
        { label: 'Waitlist', value: stats.waitlist_count },
      ].map(({ label, value }) => (
        <div key={label} className="card p-4">
          <p className="text-xs text-text-dim mono">{label}</p>
          <p className="text-2xl font-bold mono text-accent-cyan mt-1">{value}</p>
        </div>
      ))}
    </div>
  )
}

function AdminUsers() {
  const [users, setUsers] = useState([])
  const [search, setSearch] = useState('')
  useEffect(() => { api.get(`/admin/users?search=${search}`).then(r => setUsers(r.data)) }, [search])

  const update = async (id, payload) => {
    await api.patch(`/admin/users/${id}`, payload)
    toast.success('Updated')
    api.get('/admin/users').then(r => setUsers(r.data))
  }

  return (
    <div className="space-y-3">
      <input className="input max-w-sm" placeholder="Search users..." value={search} onChange={e => setSearch(e.target.value)} />
      <div className="space-y-1.5">
        {users.map(u => (
          <div key={u.id} className="card p-3 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm mono font-medium text-text-primary truncate">{u.username}</p>
              <p className="text-xs text-text-dim truncate">{u.email}</p>
            </div>
            <select
              value={u.role}
              onChange={e => update(u.id, { role: e.target.value })}
              className="text-xs mono bg-bg-secondary border border-border-color rounded px-2 py-1 text-text-primary"
            >
              {['admin', 'pro', 'user', 'waitlist'].map(r => <option key={r} value={r}>{r}</option>)}
            </select>
            <button
              onClick={() => update(u.id, { is_banned: !u.is_banned })}
              className={`text-xs px-2 py-1 rounded border transition-colors ${u.is_banned ? 'border-accent-green text-accent-green hover:bg-accent-green/10' : 'border-accent-red text-accent-red hover:bg-accent-red/10'}`}
            >
              {u.is_banned ? 'Unban' : 'Ban'}
            </button>
            <span className="text-xs text-text-dim">{formatDate(u.created_at)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function AdminWaitlist() {
  const [entries, setEntries] = useState([])
  const [selected, setSelected] = useState(new Set())
  useEffect(() => { api.get('/admin/waitlist').then(r => setEntries(r.data)) }, [])

  const approve = async (id) => {
    await api.post(`/admin/waitlist/approve/${id}`)
    toast.success('Approved & invite sent')
    setEntries(e => e.map(x => x.id === id ? { ...x, approved: true } : x))
  }

  const bulkApprove = async () => {
    await api.post('/admin/waitlist/bulk-approve', [...selected])
    toast.success(`Approved ${selected.size}`)
    setSelected(new Set())
    api.get('/admin/waitlist').then(r => setEntries(r.data))
  }

  return (
    <div className="space-y-3">
      {selected.size > 0 && (
        <button onClick={bulkApprove} className="btn-primary text-sm">
          Approve {selected.size} selected
        </button>
      )}
      <div className="space-y-1.5">
        {entries.map((e, i) => (
          <div key={e.id} className={`card p-3 flex items-center gap-3 ${e.approved ? 'opacity-50' : ''}`}>
            <input
              type="checkbox"
              checked={selected.has(e.id)}
              onChange={ev => {
                const s = new Set(selected)
                ev.target.checked ? s.add(e.id) : s.delete(e.id)
                setSelected(s)
              }}
              disabled={e.approved}
            />
            <span className="text-xs text-text-dim mono w-8">#{e.position}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-text-primary truncate">{e.name} <span className="text-text-dim">({e.email})</span></p>
              {e.use_case && <p className="text-xs text-text-dim truncate">{e.use_case}</p>}
            </div>
            <span className="text-xs text-text-dim mono">{e.referral_count} refs</span>
            {e.approved ? (
              <span className="text-xs text-accent-green mono flex items-center gap-1"><CheckCircle size={12} /> approved</span>
            ) : (
              <button onClick={() => approve(e.id)} className="text-xs btn-primary px-2 py-1">Approve</button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

const GROUP_LABELS = {
  auth: 'Authentication',
  email: 'Email / SMTP',
  frontend: 'Frontend',
  api_keys: 'API Keys',
  security: 'Security (requires restart)',
}

function SettingField({ name, meta, onSave }) {
  const [val, setVal] = useState(meta.masked ? '' : meta.value)
  const [show, setShow] = useState(false)
  const [saving, setSaving] = useState(false)
  const isSecret = meta.masked || name.toLowerCase().includes('password') || name.toLowerCase().includes('secret') || name.toLowerCase().includes('key') || name.toLowerCase().includes('token')
  const isBool = name === 'OPEN_REGISTRATION'

  const save = async () => {
    setSaving(true)
    try {
      const { data } = await api.post('/admin/settings', { key: name, value: val })
      toast.success(data.restart_required ? `Saved — restart Docker to apply` : 'Saved')
      onSave(name, val)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1">
        {isBool ? (
          <div className="flex items-center gap-2">
            <button
              onClick={() => { const nv = val === 'true' || val === true ? 'false' : 'true'; setVal(nv); }}
              className={`relative w-10 h-5 rounded-full transition-colors ${(val === 'true' || val === true) ? 'bg-accent-green' : 'bg-bg-primary border border-border-color'}`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${(val === 'true' || val === true) ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </button>
            <span className="text-xs text-text-dim mono">{(val === 'true' || val === true) ? 'enabled' : 'disabled'}</span>
          </div>
        ) : (
          <div className="flex gap-1">
            <input
              type={isSecret && !show ? 'password' : 'text'}
              value={val}
              onChange={e => setVal(e.target.value)}
              placeholder={meta.masked ? '(unchanged — type to overwrite)' : ''}
              className="input text-xs font-mono flex-1"
              onKeyDown={e => e.key === 'Enter' && save()}
            />
            {isSecret && (
              <button onClick={() => setShow(s => !s)} className="text-text-dim hover:text-text-primary px-2">
                {show ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
            )}
          </div>
        )}
      </div>
      <button
        onClick={save}
        disabled={saving}
        className="btn-secondary text-xs px-2 py-1 flex items-center gap-1 shrink-0"
      >
        <Save size={11} /> {saving ? '…' : 'Save'}
      </button>
      {meta.restart_required && (
        <span title="Requires Docker restart to take effect" className="text-amber-400 shrink-0">
          <AlertTriangle size={13} />
        </span>
      )}
    </div>
  )
}

function AdminSettings() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/admin/settings').then(r => { setData(r.data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const handleSave = (key, val) => {
    setData(d => ({
      ...d,
      settings: {
        ...d.settings,
        [key]: { ...d.settings[key], value: val, masked: false },
      },
    }))
  }

  if (loading) return <div className="skeleton h-64 rounded-lg" />
  if (!data) return <p className="text-xs text-accent-red mono">Failed to load settings.</p>

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded text-xs text-amber-400 mono">
        <AlertTriangle size={13} />
        Changes write to <code className="bg-bg-primary px-1 rounded">.env</code> on disk. Fields marked <AlertTriangle size={11} className="inline" /> require Docker restart.
      </div>

      {Object.entries(data.groups).map(([group, keys]) => (
        <div key={group} className="card p-4 space-y-3">
          <h3 className="text-xs font-semibold mono text-text-dim uppercase tracking-wider">{GROUP_LABELS[group]}</h3>
          {keys.map(key => (
            <div key={key}>
              <label className="text-xs text-text-primary mono mb-1 block">{key}</label>
              <SettingField name={key} meta={data.settings[key]} onSave={handleSave} />
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

export default function Admin() {
  const [tab, setTab] = useState('dashboard')

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <h1 className="text-lg font-bold mono text-accent-red">Admin Panel</h1>

      <div className="flex gap-1 border-b border-border-color">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs mono border-b-2 transition-colors -mb-px ${tab === id ? 'border-accent-cyan text-accent-cyan' : 'border-transparent text-text-dim hover:text-text-primary'}`}
          >
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>

      {tab === 'dashboard' && <AdminDashboard />}
      {tab === 'users' && <AdminUsers />}
      {tab === 'waitlist' && <AdminWaitlist />}
      {tab === 'settings' && <AdminSettings />}
    </div>
  )
}
