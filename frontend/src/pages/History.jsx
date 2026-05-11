import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ScanSearch, Trash2, Search } from 'lucide-react'
import api from '../utils/api'
import { formatDate } from '../utils/formatters'
import toast from 'react-hot-toast'

const STATUS_COLOR = {
  done:    'var(--green)',
  failed:  'var(--red)',
  running: 'var(--blue)',
  pending: 'var(--orange)',
}

export default function History() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  const load = () => {
    setLoading(true)
    api.get('/api/history?limit=100')
      .then(r => setItems(r.data))
      .catch(() => toast.error('Failed to load history'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const del = async (id) => {
    if (!confirm('Delete this search?')) return
    await api.delete(`/api/history/${id}`)
    toast.success('Deleted')
    setItems(i => i.filter(x => x.search_id !== id))
  }

  const filtered = filter.trim()
    ? items.filter(i =>
        (i.filename || '').toLowerCase().includes(filter.toLowerCase()) ||
        i.status.toLowerCase().includes(filter.toLowerCase())
      )
    : items

  return (
    <div className="p-6 max-w-3xl mx-auto overflow-y-auto h-full">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold tracking-tight">Search History</h1>
        <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{items.length} searches</span>
      </div>

      {items.length > 0 && (
        <div className="relative mb-4">
          <input
            className="input pl-9 py-2 text-sm"
            placeholder="Filter by filename or status…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
          />
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }} />
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[0,1,2,3,4].map(i => <div key={i} className="h-12 rounded-xl skeleton" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-10 text-center">
          <ScanSearch size={28} className="mx-auto mb-3 opacity-30" style={{ color: 'var(--text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {filter ? 'No matches for that filter' : 'No search history yet.'}
          </p>
          {!filter && (
            <Link to="/search" className="btn-primary text-sm mt-3 inline-block px-4 py-2">Run a search</Link>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(item => (
            <div
              key={item.search_id}
              className="flex items-center gap-3 p-3 rounded-xl transition-all duration-150"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
            >
              <ScanSearch size={14} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
              <Link
                to={`/search?id=${item.search_id}`}
                className="flex-1 truncate text-sm font-medium transition-colors"
                style={{ color: 'var(--text-primary)' }}
              >
                {item.filename || 'Untitled'}
              </Link>
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
              <button
                onClick={() => del(item.search_id)}
                className="flex-shrink-0 p-1 rounded transition-colors"
                style={{ color: 'var(--text-tertiary)' }}
                title="Delete"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
