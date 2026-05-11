import { useState, useEffect, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Database, Upload, Trash2, Pencil, Check, X,
  ChevronDown, ChevronUp, UserCircle2, FolderOpen, Loader2
} from 'lucide-react'
import api from '../utils/api'
import toast from 'react-hot-toast'

function StatPill({ label, value, color }) {
  return (
    <div
      className="flex items-center gap-2 px-4 py-3 rounded-xl"
      style={{ background: 'var(--surface-3)', border: '1px solid var(--border)' }}
    >
      <span className="text-2xl font-bold tracking-tight" style={{ color }}>{value ?? '—'}</span>
      <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{label}</span>
    </div>
  )
}

function BackendStatus({ backend }) {
  const colors = {
    insightface: 'var(--green)',
    deepface:    'var(--blue)',
    none:        'var(--red)',
  }
  const labels = {
    insightface: 'InsightFace (ArcFace) — Best accuracy',
    deepface:    'DeepFace — Good accuracy',
    none:        'No face backend installed',
  }
  const color = colors[backend] || colors.none
  return (
    <div className="flex items-center gap-2">
      <div className="w-2 h-2 rounded-full" style={{ background: color }} />
      <span className="text-xs" style={{ color }}>{labels[backend] || 'Unknown backend'}</span>
    </div>
  )
}

function IndexFolder({ onSuccess }) {
  const [folder, setFolder] = useState('')
  const [label, setLabel] = useState('')
  const [loading, setLoading] = useState(false)

  const handleIndex = async () => {
    if (!folder) return
    setLoading(true)
    try {
      await api.post('/api/faces/index', { folder, label: label || undefined })
      toast.success('Folder indexed successfully')
      setFolder(''); setLabel('')
      onSuccess?.()
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Indexing failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card p-5 space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <FolderOpen size={15} style={{ color: 'var(--blue)' }} />
        <h3 className="text-sm font-semibold">Index Folder</h3>
      </div>
      <input
        className="input"
        placeholder="Server folder path, e.g. /home/user/photos"
        value={folder}
        onChange={e => setFolder(e.target.value)}
      />
      <input
        className="input"
        placeholder="Label / person name (optional)"
        value={label}
        onChange={e => setLabel(e.target.value)}
      />
      <button
        onClick={handleIndex}
        disabled={!folder || loading}
        className="btn-primary w-full flex items-center justify-center gap-2"
      >
        {loading ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}
        {loading ? 'Indexing…' : 'Index Folder'}
      </button>
      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
        Recursively finds all face images in the folder and adds embeddings to your local database.
      </p>
    </div>
  )
}

function IndexUpload({ onSuccess }) {
  const [label, setLabel] = useState('')
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState(null)

  const onDrop = useCallback(async (files) => {
    if (!files.length) return
    const file = files[0]
    setPreview(URL.createObjectURL(file))
  }, [])

  const { getRootProps, getInputProps, isDragActive, acceptedFiles } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.jpg', '.jpeg', '.png', '.webp'] },
    maxSize: 20 * 1024 * 1024,
    multiple: false,
  })

  const handleSubmit = async () => {
    const file = acceptedFiles[0]
    if (!file) return
    setLoading(true)
    const form = new FormData()
    form.append('file', file)
    if (label) form.append('label', label)
    try {
      await api.post('/api/faces/index-upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      toast.success('Image indexed')
      setLabel(''); setPreview(null)
      onSuccess?.()
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Index failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card p-5 space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <Upload size={15} style={{ color: 'var(--purple)' }} />
        <h3 className="text-sm font-semibold">Add Single Image</h3>
      </div>

      <div
        {...getRootProps()}
        className="relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all"
        style={{
          borderColor: isDragActive ? 'var(--blue)' : 'var(--border)',
          background: isDragActive ? 'rgba(10,132,255,0.06)' : preview ? 'transparent' : 'var(--surface-2)',
        }}
      >
        <input {...getInputProps()} />
        {preview ? (
          <img src={preview} alt="Preview" className="mx-auto rounded-lg max-h-40 object-contain" />
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--surface-4)' }}>
              <Upload size={18} style={{ color: 'var(--text-secondary)' }} />
            </div>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Drop a photo here</p>
          </div>
        )}
      </div>

      <input
        className="input"
        placeholder="Person name / label"
        value={label}
        onChange={e => setLabel(e.target.value)}
      />
      <button
        onClick={handleSubmit}
        disabled={!acceptedFiles.length || loading}
        className="btn-primary w-full flex items-center justify-center gap-2"
      >
        {loading ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
        {loading ? 'Adding…' : 'Add to Database'}
      </button>
    </div>
  )
}

function PersonCard({ person, onDelete, onRelabel }) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [newLabel, setNewLabel] = useState(person.label || '')

  const handleRelabel = async () => {
    try {
      await onRelabel(person.id, newLabel)
      setEditing(false)
    } catch { toast.error('Failed to update label') }
  }

  return (
    <div className="card overflow-hidden">
      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Thumbnail */}
          <div
            className="w-12 h-12 rounded-xl flex-shrink-0 overflow-hidden flex items-center justify-center"
            style={{ background: 'var(--surface-4)' }}
          >
            {person.thumbnail ? (
              <img src={`data:image/jpeg;base64,${person.thumbnail}`} alt={person.label} className="w-full h-full object-cover" />
            ) : (
              <UserCircle2 size={24} style={{ color: 'var(--surface-5)' }} />
            )}
          </div>

          <div className="flex-1 min-w-0">
            {editing ? (
              <div className="flex items-center gap-1.5">
                <input
                  className="input py-1 text-sm flex-1"
                  value={newLabel}
                  onChange={e => setNewLabel(e.target.value)}
                  autoFocus
                  onKeyDown={e => { if (e.key === 'Enter') handleRelabel(); if (e.key === 'Escape') setEditing(false) }}
                />
                <button onClick={handleRelabel} className="p-1.5 rounded-lg" style={{ background: 'rgba(48,209,88,0.15)', color: 'var(--green)' }}>
                  <Check size={12} />
                </button>
                <button onClick={() => setEditing(false)} className="p-1.5 rounded-lg" style={{ background: 'var(--surface-4)', color: 'var(--text-secondary)' }}>
                  <X size={12} />
                </button>
              </div>
            ) : (
              <p className="font-semibold text-sm">{person.label || <span style={{ color: 'var(--text-tertiary)' }}>Unlabeled</span>}</p>
            )}
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
              {person.face_count} face{person.face_count !== 1 ? 's' : ''} · indexed {person.indexed_at ? new Date(person.indexed_at).toLocaleDateString() : 'recently'}
            </p>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={() => setEditing(true)}
              className="p-1.5 rounded-lg transition-colors"
              style={{ color: 'var(--text-tertiary)' }}
              title="Edit label"
            >
              <Pencil size={13} />
            </button>
            <button
              onClick={() => onDelete(person.id)}
              className="p-1.5 rounded-lg transition-colors"
              style={{ color: 'var(--text-tertiary)' }}
              title="Delete"
            >
              <Trash2 size={13} />
            </button>
            <button
              onClick={() => setExpanded(v => !v)}
              className="p-1.5 rounded-lg transition-colors"
              style={{ color: 'var(--text-tertiary)' }}
            >
              {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
          </div>
        </div>

        <AnimatePresence>
          {expanded && person.crops?.length > 0 && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                {person.crops.map((crop, i) => (
                  <img
                    key={i}
                    src={`data:image/jpeg;base64,${crop}`}
                    alt={`${person.label} crop ${i + 1}`}
                    className="w-14 h-14 rounded-lg object-cover"
                    style={{ border: '1px solid var(--border)' }}
                  />
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

export default function FaceDB() {
  const [stats, setStats] = useState(null)
  const [persons, setPersons] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [statsRes, listRes] = await Promise.all([
        api.get('/api/faces/stats').catch(() => ({ data: null })),
        api.get('/api/faces/list').catch(() => ({ data: [] })),
      ])
      setStats(statsRes.data)
      setPersons(listRes.data || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const handleDelete = async (id) => {
    try {
      await api.delete('/api/faces/remove', { data: { image_hash: id } })
      toast.success('Removed from database')
      fetchData()
    } catch { toast.error('Failed to remove') }
  }

  const handleRelabel = async (id, label) => {
    await api.post('/api/faces/label', { image_hash: id, label })
    fetchData()
  }

  const labeled = persons.filter(p => p.label)
  const unlabeled = persons.filter(p => !p.label)

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6 overflow-y-auto h-full">
      {/* Header */}
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Face Database</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          Your local, private face recognition database — a free alternative to PimEyes.
        </p>
      </div>

      {/* Stats */}
      <div className="flex flex-wrap gap-3">
        <StatPill label="Total images" value={stats?.total_images} color="var(--blue)" />
        <StatPill label="Labeled faces" value={stats?.labeled_faces} color="var(--green)" />
        <StatPill label="Known people" value={stats?.known_people} color="var(--purple)" />
        <div className="flex items-center px-4 py-3 rounded-xl" style={{ background: 'var(--surface-3)', border: '1px solid var(--border)' }}>
          <BackendStatus backend={stats?.backend} />
        </div>
      </div>

      {/* Index section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <IndexFolder onSuccess={fetchData} />
        <IndexUpload onSuccess={fetchData} />
      </div>

      {/* Persons gallery */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[0, 1, 2, 3, 4, 5].map(i => <div key={i} className="h-24 rounded-xl skeleton" />)}
        </div>
      ) : persons.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{ background: 'var(--surface-3)' }}>
            <Database size={28} style={{ color: 'var(--surface-5)' }} />
          </div>
          <p className="text-sm font-medium">No faces indexed yet</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
            Use the forms above to add photos to your database
          </p>
        </div>
      ) : (
        <>
          {labeled.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>
                Known Persons ({labeled.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {labeled.map(p => (
                  <PersonCard key={p.id} person={p} onDelete={handleDelete} onRelabel={handleRelabel} />
                ))}
              </div>
            </div>
          )}

          {unlabeled.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>
                Unlabeled ({unlabeled.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {unlabeled.map(p => (
                  <PersonCard key={p.id} person={p} onDelete={handleDelete} onRelabel={handleRelabel} />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
