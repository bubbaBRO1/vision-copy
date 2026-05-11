import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Upload, Database, Loader2, ExternalLink, FolderOpen, SlidersHorizontal } from 'lucide-react'
import api from '../utils/api'
import toast from 'react-hot-toast'

function MatchCard({ match }) {
  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{match.label || 'Unknown label'}</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
            {match.confidence_label}
          </p>
        </div>
        <div className="text-right">
          <p className="text-lg font-bold" style={{ color: 'var(--blue)' }}>
            {Math.round(match.similarity_score * 100)}%
          </p>
          <p className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>match</p>
        </div>
      </div>
      <div className="space-y-1 text-xs" style={{ color: 'var(--text-secondary)' }}>
        {match.thumbnail && (
          <img src={`data:image/jpeg;base64,${match.thumbnail}`} alt={match.label || 'Match'} className="w-full rounded-lg max-h-44 object-cover mb-2" />
        )}
        {match.source_url && <p className="truncate">Source: {match.source_url}</p>}
        {match.page_url && <p className="truncate">Page: {match.page_url}</p>}
      </div>
      {match.page_url && (
        <a
          href={match.page_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs font-medium"
          style={{ color: 'var(--blue)' }}
        >
          Open source
          <ExternalLink size={12} />
        </a>
      )}
    </div>
  )
}

export default function FaceSearch() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [stats, setStats] = useState(null)
  const [topK, setTopK] = useState(20)
  const [minSimilarity, setMinSimilarity] = useState(0.35)

  const matches = useMemo(() => results?.matches || [], [results])

  useEffect(() => {
    api.get('/api/faces/index/stats')
      .then(({ data }) => setStats(data))
      .catch(() => setStats(null))
  }, [])

  const runSearch = async () => {
    if (!file) return
    const form = new FormData()
    form.append('image', file)
    form.append('top_k', String(topK))
    form.append('min_similarity', String(minSimilarity))

    setLoading(true)
    try {
      const { data } = await api.post('/api/faces/search', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResults(data)
      toast.success(`Found ${data.total_matches} local matches`)
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Face search failed')
    } finally {
      setLoading(false)
    }
  }

  const handlePick = (event) => {
    const next = event.target.files?.[0]
    if (!next) return
    setFile(next)
    setPreview(URL.createObjectURL(next))
    setResults(null)
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6 overflow-y-auto h-full">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Face Search</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          Search your private local face index with a direct upload workflow.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[360px,1fr] gap-5">
        <div className="space-y-4">
          <div className="card p-5 space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'rgba(10,132,255,0.1)' }}>
                <Search size={18} style={{ color: 'var(--blue)' }} />
              </div>
              <div>
                <p className="text-sm font-semibold">Upload query face</p>
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Uses the local FaceDB only
                </p>
              </div>
            </div>

            <label
              className="block border-2 border-dashed rounded-2xl p-5 text-center cursor-pointer transition-colors"
              style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}
            >
              <input type="file" accept="image/*" className="hidden" onChange={handlePick} />
              {preview ? (
                <img src={preview} alt="Query" className="rounded-xl max-h-64 w-full object-contain" />
              ) : (
                <div className="space-y-2">
                  <Upload size={24} className="mx-auto" style={{ color: 'var(--text-secondary)' }} />
                  <p className="text-sm font-medium">Choose a face image</p>
                  <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    JPG, PNG, WEBP, GIF, BMP, or TIFF
                  </p>
                </div>
              )}
            </label>

            <button
              onClick={runSearch}
              disabled={!file || loading}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 size={15} className="animate-spin" /> : <Database size={15} />}
              {loading ? 'Searching...' : 'Search local face index'}
            </button>

            {results && (
              <div className="rounded-xl p-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                <p className="text-xs uppercase tracking-wider font-semibold mb-2" style={{ color: 'var(--text-tertiary)' }}>
                  Search stats
                </p>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="font-semibold">{results.total_matches}</p>
                    <p style={{ color: 'var(--text-secondary)' }}>matches</p>
                  </div>
                  <div>
                    <p className="font-semibold">{results.search_time_ms} ms</p>
                    <p style={{ color: 'var(--text-secondary)' }}>latency</p>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-xl p-4 space-y-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={14} style={{ color: 'var(--text-secondary)' }} />
              <p className="text-xs uppercase tracking-wider font-semibold" style={{ color: 'var(--text-tertiary)' }}>
                Search controls
              </p>
            </div>
            <label className="space-y-1 block">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Result limit</span>
              <select className="input" value={String(topK)} onChange={(event) => setTopK(Number(event.target.value))}>
                {[5, 10, 20, 30, 50].map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 block">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Minimum similarity: {Math.round(minSimilarity * 100)}%
              </span>
              <input
                type="range"
                min="0.2"
                max="0.95"
                step="0.05"
                value={minSimilarity}
                onChange={(event) => setMinSimilarity(Number(event.target.value))}
              />
            </label>
          </div>

          <div className="rounded-xl p-4 space-y-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-2">
              <FolderOpen size={14} style={{ color: 'var(--text-secondary)' }} />
              <p className="text-xs uppercase tracking-wider font-semibold" style={{ color: 'var(--text-tertiary)' }}>
                Local face index
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="font-semibold">{stats?.total_images ?? '—'}</p>
                <p style={{ color: 'var(--text-secondary)' }}>indexed images</p>
              </div>
              <div>
                <p className="font-semibold">{stats?.known_people ?? '—'}</p>
                <p style={{ color: 'var(--text-secondary)' }}>known people</p>
              </div>
            </div>
            <Link
              to="/faces"
              className="inline-flex items-center gap-1.5 text-xs font-medium"
              style={{ color: 'var(--blue)' }}
            >
              Manage face database
              <ExternalLink size={12} />
            </Link>
          </div>
        </div>

        <div className="space-y-4">
          {results && matches.length === 0 && (
            <div className="card p-10 text-center">
              <p className="text-sm font-medium">No local matches found</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                Try a clearer face crop or add more images to the Face Database.
              </p>
            </div>
          )}

          {matches.length > 0 && (
            <>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold">Matches</p>
                  <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    Ranked by local embedding similarity
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {matches.map((match) => (
                  <MatchCard key={match.id} match={match} />
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
