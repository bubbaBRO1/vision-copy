import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Folder, FolderOpen, Plus, Trash2, ScanSearch } from 'lucide-react'
import api from '../utils/api'
import { formatDate } from '../utils/formatters'
import toast from 'react-hot-toast'

export default function Collections() {
  const [collections, setCollections] = useState([])
  const [selected, setSelected] = useState(null)
  const [searches, setSearches] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')

  const load = () =>
    api.get('/api/collections').then(r => setCollections(r.data)).finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const openCollection = async (col) => {
    setSelected(col)
    const r = await api.get(`/api/collections/${col.id}/searches`)
    setSearches(r.data)
  }

  const createCollection = async (e) => {
    e.preventDefault()
    if (!newName.trim()) return
    await api.post('/api/collections', { name: newName.trim() })
    toast.success('Collection created')
    setNewName('')
    setCreating(false)
    load()
  }

  const deleteCollection = async (id) => {
    if (!confirm('Delete collection? Searches are kept.')) return
    await api.delete(`/api/collections/${id}`)
    toast.success('Deleted')
    if (selected?.id === id) setSelected(null)
    load()
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-bold mono text-text-primary">Collections</h1>
        <button onClick={() => setCreating(v => !v)} className="btn-primary text-xs flex items-center gap-1">
          <Plus size={12} /> New
        </button>
      </div>

      {creating && (
        <form onSubmit={createCollection} className="card p-3 mb-4 flex gap-2">
          <input
            className="input flex-1 text-sm"
            placeholder="Collection name..."
            value={newName}
            onChange={e => setNewName(e.target.value)}
            autoFocus
          />
          <button type="submit" className="btn-primary text-xs px-3">Create</button>
          <button type="button" onClick={() => setCreating(false)} className="btn-secondary text-xs px-3">Cancel</button>
        </form>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Collection list */}
        <div className="space-y-1.5">
          {loading ? (
            [0,1,2].map(i => <div key={i} className="skeleton h-12 rounded-lg" />)
          ) : collections.length === 0 ? (
            <div className="card p-6 text-center col-span-3">
              <Folder size={32} className="text-text-dim mx-auto mb-2 opacity-30" />
              <p className="text-sm text-text-dim">No collections yet.</p>
            </div>
          ) : collections.map(col => (
            <div
              key={col.id}
              onClick={() => openCollection(col)}
              className={`card card-hover p-3 flex items-center gap-2 cursor-pointer ${selected?.id === col.id ? 'border-accent-cyan/40' : ''}`}
            >
              {selected?.id === col.id
                ? <FolderOpen size={14} className="text-accent-cyan flex-shrink-0" />
                : <Folder size={14} className="text-text-dim flex-shrink-0" />}
              <span className="flex-1 text-sm text-text-primary truncate">{col.name}</span>
              <span className="text-xs text-text-dim mono">{col.search_count}</span>
              <button
                onClick={e => { e.stopPropagation(); deleteCollection(col.id) }}
                className="text-text-dim hover:text-accent-red transition-colors"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>

        {/* Searches in selected collection */}
        {selected && (
          <div className="md:col-span-2 space-y-1.5">
            <p className="text-xs text-text-dim mono mb-2">{selected.name}</p>
            {searches.length === 0 ? (
              <div className="card p-6 text-center">
                <p className="text-sm text-text-dim">No searches in this collection.</p>
              </div>
            ) : searches.map(item => (
              <Link
                key={item.search_id}
                to={`/search?id=${item.search_id}`}
                className="card card-hover p-3 flex items-center gap-3 block"
              >
                <ScanSearch size={14} className="text-text-dim flex-shrink-0" />
                <span className="text-sm text-text-primary flex-1 truncate">{item.filename || 'Untitled'}</span>
                <span className={`text-xs mono ${item.status === 'done' ? 'text-accent-green' : item.status === 'failed' ? 'text-accent-red' : 'text-accent-yellow'}`}>
                  {item.status}
                </span>
                <span className="text-xs text-text-dim">{formatDate(item.created_at)}</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
