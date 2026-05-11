import { useState, useEffect } from 'react'
import { Key, Lock, Trash2, Download, LogOut, Brain, Plus, X } from 'lucide-react'
import api from '../utils/api'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

function Section({ title, children }) {
  return (
    <div className="card p-5 space-y-4">
      <h2 className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>{title}</h2>
      {children}
    </div>
  )
}

function MemorySection() {
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(true)
  const [newContent, setNewContent] = useState('')
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    api.get('/api/memory/')
      .then(r => setMemories(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const addMemory = async () => {
    if (!newContent.trim()) return
    setAdding(true)
    try {
      const { data } = await api.post('/api/memory/', { content: newContent.trim() })
      setMemories(m => [data, ...m])
      setNewContent('')
      toast.success('Memory saved')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save memory')
    } finally {
      setAdding(false)
    }
  }

  const deleteMemory = async (id) => {
    try {
      await api.delete(`/api/memory/${id}`)
      setMemories(m => m.filter(x => x.id !== id))
    } catch {
      toast.error('Failed to delete')
    }
  }

  const clearAll = async () => {
    if (!window.confirm('Delete all memories? Cannot be undone.')) return
    try {
      await Promise.all(memories.map(m => api.delete(`/api/memory/${m.id}`)))
      setMemories([])
      toast.success('All memories cleared')
    } catch {
      toast.error('Failed to clear')
    }
  }

  return (
    <Section title="Memory">
      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
        Persistent context injected into AI chats. Incognito sessions never read or write memory.
      </p>

      <div className="flex gap-2">
        <input
          className="input flex-1 text-sm"
          placeholder="Add a memory…"
          value={newContent}
          onChange={e => setNewContent(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') addMemory() }}
        />
        <button
          onClick={addMemory}
          disabled={adding || !newContent.trim()}
          className="btn-primary text-xs px-3 py-2 flex items-center gap-1 disabled:opacity-40"
        >
          <Plus size={12} /> Add
        </button>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1,2,3].map(i => <div key={i} className="h-10 rounded-lg skeleton" />)}
        </div>
      ) : memories.length === 0 ? (
        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>No memories yet.</p>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {memories.map(m => (
            <div
              key={m.id}
              className="flex items-start gap-2 p-2.5 rounded-lg"
              style={{ background: 'var(--surface-3)', border: '1px solid var(--border)' }}
            >
              <p className="text-xs flex-1" style={{ color: 'var(--text-primary)' }}>{m.content}</p>
              <button
                onClick={() => deleteMemory(m.id)}
                className="flex-shrink-0 p-0.5 rounded transition-colors"
                style={{ color: 'var(--text-tertiary)' }}
                title="Delete memory"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {memories.length > 0 && (
        <div className="flex items-center gap-3">
          <button
            onClick={async () => {
              const { data } = await api.get('/api/memory/export', { responseType: 'blob' })
              const url = URL.createObjectURL(data)
              const a = document.createElement('a'); a.href = url; a.download = 'vision-memory.json'; a.click()
              URL.revokeObjectURL(url)
            }}
            className="text-xs flex items-center gap-1"
            style={{ color: 'var(--blue)' }}
          >
            <Download size={11} /> Export memories
          </button>
          <button onClick={clearAll} className="text-xs flex items-center gap-1" style={{ color: 'var(--red)' }}>
            <Trash2 size={11} /> Clear all
          </button>
        </div>
      )}
    </Section>
  )
}

export default function Settings() {
  const { user, logout } = useAuthStore()
  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' })
  const [apiKey, setApiKey] = useState(user?.api_key || '')
  const [saving, setSaving] = useState(false)

  const changePassword = async (e) => {
    e.preventDefault()
    if (passwords.next !== passwords.confirm) { toast.error('Passwords do not match'); return }
    if (passwords.next.length < 8) { toast.error('Min 8 characters'); return }
    setSaving(true)
    try {
      await api.post('/auth/change-password', { current_password: passwords.current, new_password: passwords.next })
      toast.success('Password changed')
      setPasswords({ current: '', next: '', confirm: '' })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed')
    } finally {
      setSaving(false)
    }
  }

  const regenerateApiKey = async () => {
    if (!confirm('Regenerate API key? Old key stops working immediately.')) return
    const { data } = await api.post('/auth/api-key/regenerate')
    setApiKey(data.api_key)
    toast.success('New API key generated')
  }

  const exportData = async () => {
    const { data } = await api.get('/auth/export', { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = `vision-export-${user?.username}.zip`
    a.click()
    URL.revokeObjectURL(url)
  }

  const deleteAccount = async () => {
    const confirmed = prompt(`Type "${user?.username}" to confirm account deletion:`)
    if (confirmed !== user?.username) { toast.error('Cancelled'); return }
    await api.delete('/auth/account')
    logout()
    window.location.href = '/'
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-4 overflow-y-auto h-full">
      <h1 className="text-lg font-semibold tracking-tight">Settings</h1>

      <Section title="Account">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0"
            style={{ background: 'var(--blue)' }}
          >
            {user?.username?.[0]?.toUpperCase()}
          </div>
          <div>
            <p className="text-sm font-medium">{user?.username}</p>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{user?.email}</p>
            <span
              className="inline-block text-xs px-1.5 py-0.5 rounded mt-1"
              style={{
                background: user?.role === 'admin' ? 'rgba(255,69,58,0.15)' : user?.role === 'pro' ? 'rgba(10,132,255,0.15)' : 'var(--surface-3)',
                color: user?.role === 'admin' ? 'var(--red)' : user?.role === 'pro' ? 'var(--blue)' : 'var(--text-secondary)',
              }}
            >
              {user?.role}
            </span>
          </div>
        </div>
      </Section>

      {!user?.google_id && (
        <Section title="Change Password">
          <form onSubmit={changePassword} className="space-y-3">
            <input type="password" className="input text-sm" placeholder="Current password"
              value={passwords.current} onChange={e => setPasswords(p => ({ ...p, current: e.target.value }))} />
            <input type="password" className="input text-sm" placeholder="New password"
              value={passwords.next} onChange={e => setPasswords(p => ({ ...p, next: e.target.value }))} />
            <input type="password" className="input text-sm" placeholder="Confirm new password"
              value={passwords.confirm} onChange={e => setPasswords(p => ({ ...p, confirm: e.target.value }))} />
            <button type="submit" disabled={saving} className="btn-primary text-sm flex items-center gap-2">
              <Lock size={13} /> {saving ? 'Saving...' : 'Update Password'}
            </button>
          </form>
        </Section>
      )}

      <Section title="API Key">
        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Authenticate programmatic requests with this key.</p>
        <div className="flex gap-2">
          <input type="text" className="input font-mono text-xs flex-1" value={apiKey} readOnly onClick={e => e.target.select()} />
          <button onClick={regenerateApiKey} className="btn-secondary text-xs flex items-center gap-1">
            <Key size={12} /> Regenerate
          </button>
        </div>
      </Section>

      <Section title="Sessions">
        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Revoke all other active sessions.</p>
        <button
          onClick={async () => { await api.delete('/auth/sessions'); toast.success('All other sessions revoked') }}
          className="btn-secondary text-xs flex items-center gap-2"
        >
          <LogOut size={13} /> Revoke All Sessions
        </button>
      </Section>

      <MemorySection />

      <Section title="Data">
        <div className="space-y-2">
          <button onClick={exportData} className="btn-secondary text-xs flex items-center gap-2">
            <Download size={13} /> Export All Data
          </button>
          <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Downloads ZIP with searches, research jobs, and chat history.</p>
        </div>
      </Section>

      <Section title="Danger Zone">
        <div className="rounded-xl p-4 space-y-3" style={{ border: '1px solid rgba(255,69,58,0.3)' }}>
          <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Permanently delete account and all data. Cannot be undone.</p>
          <button onClick={deleteAccount} className="btn-danger text-xs flex items-center gap-2">
            <Trash2 size={13} /> Delete Account
          </button>
        </div>
      </Section>
    </div>
  )
}
