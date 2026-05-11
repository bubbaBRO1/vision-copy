import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Briefcase, Archive, ChevronRight, ScanSearch, MessageSquare, Folder } from 'lucide-react'
import api from '../utils/api'
import toast from 'react-hot-toast'

function NewProjectModal({ onClose, onCreated }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    try {
      const { data } = await api.post('/api/projects/', { name: name.trim(), description: description.trim() || null })
      onCreated(data)
      onClose()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.6)' }} onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl p-6 space-y-4"
        style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-xl)' }}
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold">New Case</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Name</label>
            <input
              className="input mt-1"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Case: Subject Alpha"
              autoFocus
              required
            />
          </div>
          <div>
            <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Description (optional)</label>
            <textarea
              className="input mt-1 resize-none"
              rows={2}
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Brief objective, source, or question..."
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2 rounded-xl text-sm" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>
              Cancel
            </button>
            <button type="submit" disabled={loading || !name.trim()} className="flex-1 btn-primary py-2 text-sm">
              {loading ? 'Creating...' : 'Create Case'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function ProjectList() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    api.get('/api/projects/')
      .then(({ data }) => setProjects(data))
      .catch(() => toast.error('Failed to load projects'))
      .finally(() => setLoading(false))
  }, [])

  const handleArchive = async (e, id) => {
    e.preventDefault()
    e.stopPropagation()
    try {
      await api.post(`/api/projects/${id}/archive`)
      setProjects(ps => ps.map(p => p.id === id ? { ...p, status: 'archived' } : p))
    } catch {
      toast.error('Failed to archive')
    }
  }

  const active = projects.filter(p => p.status === 'active')
  const archived = projects.filter(p => p.status === 'archived')

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold">Cases</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Investigation workspaces for searches, evidence, AI notes, timelines, and reports
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="btn-primary flex items-center gap-2 px-4 py-2 text-sm"
        >
          <Plus size={14} /> New Case
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1,2,3].map(i => (
            <div key={i} className="h-20 rounded-xl animate-pulse" style={{ background: 'var(--surface-3)' }} />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="text-center py-16" style={{ color: 'var(--text-tertiary)' }}>
          <Briefcase size={36} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">No cases yet</p>
          <button onClick={() => setShowModal(true)} className="mt-3 text-sm font-medium" style={{ color: 'var(--blue)' }}>
            Create your first case &rarr;
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {active.length > 0 && (
            <div className="space-y-2">
              {active.map(p => <ProjectCard key={p.id} project={p} onArchive={handleArchive} />)}
            </div>
          )}
          {archived.length > 0 && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: 'var(--text-tertiary)' }}>Archived</p>
              <div className="space-y-2">
                {archived.map(p => <ProjectCard key={p.id} project={p} onArchive={handleArchive} />)}
              </div>
            </div>
          )}
        </div>
      )}

      {showModal && (
        <NewProjectModal
          onClose={() => setShowModal(false)}
          onCreated={p => setProjects(ps => [p, ...ps])}
        />
      )}
    </div>
  )
}

function ProjectCard({ project: p, onArchive }) {
  return (
    <Link
      to={`/projects/${p.id}`}
      className="flex items-center gap-4 p-4 rounded-xl group transition-all duration-150"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
    >
      <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(10,132,255,0.12)' }}>
        <Briefcase size={18} style={{ color: 'var(--blue)' }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium truncate">{p.name}</p>
          {p.status === 'archived' && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-md font-medium" style={{ background: 'var(--surface-4)', color: 'var(--text-tertiary)' }}>
              Archived
            </span>
          )}
        </div>
        {p.description && (
          <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--text-tertiary)' }}>{p.description}</p>
        )}
        <div className="flex items-center gap-3 mt-1.5 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
          <span className="flex items-center gap-1"><ScanSearch size={10} /> {p.search_count} searches</span>
          <span className="flex items-center gap-1"><MessageSquare size={10} /> {p.chat_count} chats</span>
          <span className="flex items-center gap-1"><Folder size={10} /> {p.collection_count} collections</span>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {p.status === 'active' && (
          <button
            onClick={(e) => onArchive(e, p.id)}
            title="Archive"
            className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
            style={{ color: 'var(--text-tertiary)' }}
          >
            <Archive size={14} />
          </button>
        )}
        <ChevronRight size={16} style={{ color: 'var(--text-tertiary)' }} />
      </div>
    </Link>
  )
}
