import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, Bot, Brain, CheckCircle2, Clock, Download, ExternalLink, FileText,
  Filter, GitBranch, Globe, NotebookPen, Plus, ScanSearch, ShieldAlert, Sparkles,
  Trash2, User, XCircle,
} from 'lucide-react'
import api from '../utils/api'
import toast from 'react-hot-toast'
import { buildCaseReport, evidenceStatusTone, filterEvidence, normalizeWorkspace } from '../utils/caseWorkspace'

const TABS = [
  { id: 'overview', label: 'Overview', icon: GitBranch },
  { id: 'evidence', label: 'Evidence', icon: CheckCircle2 },
  { id: 'sources', label: 'Sources', icon: Globe },
  { id: 'entities', label: 'Entities', icon: GitBranch },
  { id: 'faces', label: 'Faces', icon: User },
  { id: 'timeline', label: 'Timeline', icon: Clock },
  { id: 'ai', label: 'AI', icon: Brain },
  { id: 'report', label: 'Report', icon: FileText },
  { id: 'notes', label: 'Notes', icon: NotebookPen },
]

const AI_ACTIONS = [
  { id: 'summary', label: 'Case summary' },
  { id: 'next_steps', label: 'Next steps' },
  { id: 'source_review', label: 'Source review' },
  { id: 'contradictions', label: 'Contradictions' },
  { id: 'entities', label: 'Extract entities' },
  { id: 'timeline', label: 'Timeline synthesis' },
  { id: 'what_missing', label: 'What am I missing?' },
]

function Stat({ label, value, icon: Icon, color = 'var(--blue)' }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-2" style={{ color }}>
        <Icon size={15} />
        <span className="text-[11px] font-semibold uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-2xl font-bold">{value ?? 'n/a'}</p>
    </div>
  )
}

function EvidenceBadge({ status }) {
  const tone = evidenceStatusTone(status)
  return (
    <span className="text-[11px] px-2 py-1 rounded-full font-medium" style={{ background: tone.bg, color: tone.color }}>
      {tone.label}
    </span>
  )
}

function TabButton({ tab, active, onClick }) {
  const Icon = tab.icon
  return (
    <button
      onClick={() => onClick(tab.id)}
      className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors"
      style={{ background: active ? 'var(--surface-4)' : 'transparent', color: active ? 'var(--text-primary)' : 'var(--text-secondary)' }}
    >
      <Icon size={13} /> {tab.label}
    </button>
  )
}

export default function ProjectDetail() {
  const { id } = useParams()
  const [workspace, setWorkspace] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('overview')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [minConfidence, setMinConfidence] = useState(0)
  const [newEvidence, setNewEvidence] = useState({ title: '', source_url: '', notes: '' })
  const [notes, setNotes] = useState('')
  const [notesDirty, setNotesDirty] = useState(false)
  const [aiLoading, setAiLoading] = useState(null)

  const loadWorkspace = async () => {
    const { data } = await api.get(`/api/projects/${id}/workspace`)
    const normalized = normalizeWorkspace(data)
    setWorkspace(normalized)
    setNotes(normalized.case.notes || '')
  }

  useEffect(() => {
    setLoading(true)
    loadWorkspace().catch(() => toast.error('Case not found')).finally(() => setLoading(false))
  }, [id])

  const filteredEvidence = useMemo(
    () => filterEvidence(workspace?.evidence || [], { query, status, minConfidence }),
    [workspace, query, status, minConfidence]
  )

  const createEvidence = async (event) => {
    event.preventDefault()
    if (!newEvidence.title.trim()) return
    try {
      await api.post(`/api/projects/${id}/evidence`, {
        ...newEvidence,
        title: newEvidence.title.trim(),
        evidence_type: newEvidence.source_url ? 'url' : 'note',
        status: 'needs_review',
        tags: ['manual'],
        provenance: { created_from: 'case_workspace' },
      })
      setNewEvidence({ title: '', source_url: '', notes: '' })
      await loadWorkspace()
      toast.success('Evidence captured')
    } catch {
      toast.error('Failed to capture evidence')
    }
  }

  const updateEvidence = async (item, patch) => {
    await api.patch(`/api/evidence/${item.id}`, patch)
    await loadWorkspace()
  }

  const deleteEvidence = async (item) => {
    const confirmed = window.confirm(`Delete evidence "${item.title}"?`)
    if (!confirmed) return
    await api.delete(`/api/evidence/${item.id}`)
    await loadWorkspace()
  }

  const runAi = async (action) => {
    setAiLoading(action)
    try {
      await api.post(`/api/projects/${id}/ai/${action}`)
      await loadWorkspace()
      toast.success('AI insight added')
    } catch {
      toast.error('AI action failed')
    } finally {
      setAiLoading(null)
    }
  }

  const saveNotes = async () => {
    await api.patch(`/api/projects/${id}`, { notes })
    setNotesDirty(false)
    await loadWorkspace()
    toast.success('Notes saved')
  }

  const downloadExport = async (format) => {
    const { data } = await api.get(`/api/projects/${id}/export?format=${format}`, { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = `vision-case-${workspace.case.name.replace(/\s+/g, '_').toLowerCase()}.${format === 'zip' ? 'zip' : format}`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) return <div className="p-6 space-y-3"><div className="h-9 w-56 skeleton rounded-xl" /><div className="h-72 skeleton rounded-xl" /></div>
  if (!workspace) return <div className="flex-1 flex items-center justify-center text-sm" style={{ color: 'var(--text-tertiary)' }}>Case not found</div>

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-5 border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
        <Link to="/projects" className="inline-flex items-center gap-1.5 text-xs mb-4" style={{ color: 'var(--text-tertiary)' }}>
          <ArrowLeft size={13} /> Cases
        </Link>
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: 'rgba(10,132,255,0.12)', color: 'var(--blue)' }}>
            <ShieldAlert size={20} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-semibold tracking-tight truncate">{workspace.case.name}</h1>
              <EvidenceBadge status={workspace.case.status} />
            </div>
            <p className="text-sm mt-1 max-w-3xl" style={{ color: 'var(--text-secondary)' }}>
              {workspace.case.description || 'Personal OSINT case workspace with evidence, sources, AI assistance, timeline, and report exports.'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => downloadExport('html')} className="btn-secondary flex items-center gap-1.5 text-xs"><Download size={13} /> HTML</button>
            <button onClick={() => downloadExport('zip')} className="btn-primary flex items-center gap-1.5 text-xs"><Download size={13} /> Bundle</button>
          </div>
        </div>
        <div className="flex items-center gap-1 mt-5 p-1 rounded-xl w-fit" style={{ background: 'var(--surface-3)' }}>
          {TABS.map((item) => <TabButton key={item.id} tab={item} active={tab === item.id} onClick={setTab} />)}
        </div>
      </div>

      <div className="p-5 space-y-5">
        {tab === 'overview' && (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
              <Stat label="Searches" value={workspace.stats.searches} icon={ScanSearch} />
              <Stat label="Evidence" value={workspace.stats.evidence} icon={CheckCircle2} color="var(--green)" />
              <Stat label="Verified" value={workspace.stats.verified_evidence} icon={ShieldAlert} color="var(--green)" />
              <Stat label="Entities" value={workspace.stats.entities} icon={GitBranch} color="var(--purple)" />
              <Stat label="AI Notes" value={workspace.stats.ai_insights} icon={Bot} color="var(--indigo)" />
              <Stat label="Avg Conf." value={workspace.stats.avg_confidence ?? 'n/a'} icon={Sparkles} color="var(--orange)" />
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_.8fr] gap-4">
              <section className="card p-5">
                <h2 className="text-sm font-semibold mb-4">Recent Evidence</h2>
                <EvidenceList items={workspace.evidence.slice(0, 6)} onUpdate={updateEvidence} onDelete={deleteEvidence} />
              </section>
              <section className="card p-5">
                <h2 className="text-sm font-semibold mb-4">Case Timeline</h2>
                <Timeline items={workspace.timeline.slice(0, 8)} />
              </section>
            </div>
          </>
        )}

        {tab === 'evidence' && (
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-4">
            <section className="space-y-4">
              <div className="card p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
                <div className="md:col-span-2 relative">
                  <Filter size={14} className="absolute left-3 top-3" style={{ color: 'var(--text-tertiary)' }} />
                  <input className="input pl-9" placeholder="Filter title, tags, source..." value={query} onChange={(e) => setQuery(e.target.value)} />
                </div>
                <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="all">All statuses</option>
                  <option value="verified">Verified</option>
                  <option value="needs_review">Needs review</option>
                  <option value="rejected">Rejected</option>
                  <option value="lead">Lead</option>
                </select>
                <label className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Min confidence: {minConfidence}
                  <input type="range" min="0" max="100" value={minConfidence} onChange={(e) => setMinConfidence(Number(e.target.value))} className="w-full mt-2" />
                </label>
              </div>
              <EvidenceList items={filteredEvidence} onUpdate={updateEvidence} onDelete={deleteEvidence} />
            </section>
            <form onSubmit={createEvidence} className="card p-4 h-fit space-y-3">
              <h2 className="text-sm font-semibold flex items-center gap-2"><Plus size={14} /> Capture Evidence</h2>
              <input className="input" placeholder="Evidence title" value={newEvidence.title} onChange={(e) => setNewEvidence({ ...newEvidence, title: e.target.value })} />
              <input className="input" placeholder="Source URL" value={newEvidence.source_url} onChange={(e) => setNewEvidence({ ...newEvidence, source_url: e.target.value })} />
              <textarea className="input resize-none" rows={5} placeholder="Notes and provenance" value={newEvidence.notes} onChange={(e) => setNewEvidence({ ...newEvidence, notes: e.target.value })} />
              <button className="btn-primary w-full">Add Evidence</button>
            </form>
          </div>
        )}

        {tab === 'timeline' && <section className="card p-5"><Timeline items={workspace.timeline} /></section>}

        {tab === 'sources' && (
          <section className="card p-5">
            <h2 className="text-sm font-semibold mb-4">Source List</h2>
            {workspace.sources.length === 0 ? <Empty label="No sources captured yet." /> : (
              <div className="space-y-2">
                {workspace.sources.map((source) => (
                  <a key={source.url} href={source.url} target="_blank" rel="noreferrer" className="flex items-center gap-3 rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                    <Globe size={14} style={{ color: 'var(--blue)' }} />
                    <span className="text-sm break-all flex-1">{source.url}</span>
                    <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                      {source.evidence_count} evidence / {source.artifact_count} artifacts
                    </span>
                    <ExternalLink size={12} style={{ color: 'var(--text-tertiary)' }} />
                  </a>
                ))}
              </div>
            )}
          </section>
        )}

        {tab === 'entities' && (
          <section className="card p-5">
            <h2 className="text-sm font-semibold mb-4">Entities</h2>
            {workspace.entities.length === 0 ? <Empty label="No entities extracted yet. Run the entity extraction analyst action or Browser Assist." /> : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {workspace.entities.map((entity) => (
                  <div key={entity.id} className="rounded-xl p-3" style={{ background: 'var(--surface-2)' }}>
                    <p className="text-sm font-semibold">{entity.label}</p>
                    <p className="text-xs mt-1 capitalize" style={{ color: 'var(--text-secondary)' }}>{entity.entity_type} - {entity.confidence ?? 'n/a'} confidence</p>
                    {entity.notes && <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>{entity.notes}</p>}
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {tab === 'faces' && (
          <section className="card p-5">
            <h2 className="text-sm font-semibold mb-4">Faces</h2>
            <Empty label="Face matches remain local/private and should be promoted as evidence only after consent-aware verification." />
          </section>
        )}

        {tab === 'ai' && (
          <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-4">
            <section className="card p-4 h-fit space-y-2">
              <h2 className="text-sm font-semibold mb-3">Analyst Actions</h2>
              {AI_ACTIONS.map((action) => (
                <button key={action.id} onClick={() => runAi(action.id)} disabled={!!aiLoading} className="w-full btn-secondary flex items-center justify-between text-xs">
                  {action.label}
                  {aiLoading === action.id ? 'Running...' : <Sparkles size={13} />}
                </button>
              ))}
            </section>
            <section className="space-y-3">
              {workspace.ai_insights.length === 0 ? <Empty label="No AI insights yet. Run an analyst action to add one." /> : workspace.ai_insights.map((insight) => (
                <div key={insight.id} className="card p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Bot size={14} style={{ color: 'var(--indigo)' }} />
                    <h3 className="text-sm font-semibold capitalize">{insight.action.replace(/_/g, ' ')}</h3>
                    <span className="ml-auto text-[11px]" style={{ color: 'var(--text-tertiary)' }}>{new Date(insight.created_at).toLocaleString()}</span>
                  </div>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{insight.content}</p>
                  <p className="text-xs mt-3" style={{ color: 'var(--orange)' }}>{insight.disclaimer}</p>
                </div>
              ))}
            </section>
          </div>
        )}

        {tab === 'report' && (
          <section className="grid grid-cols-1 xl:grid-cols-[1fr_260px] gap-4">
            <pre className="card p-5 overflow-auto text-xs leading-relaxed whitespace-pre-wrap">{buildCaseReport(workspace)}</pre>
            <div className="card p-4 h-fit space-y-2">
              <button onClick={() => runAi('report')} className="btn-secondary w-full flex items-center justify-center gap-2 text-xs"><Brain size={13} /> Draft AI Report</button>
              {['md', 'html', 'json', 'zip'].map((format) => (
                <button key={format} onClick={() => downloadExport(format)} className="btn-primary w-full text-xs">Export {format.toUpperCase()}</button>
              ))}
            </div>
          </section>
        )}

        {tab === 'notes' && (
          <section className="card p-4 space-y-3">
            <textarea className="input resize-none mono" rows={16} value={notes} onChange={(e) => { setNotes(e.target.value); setNotesDirty(true) }} placeholder="Investigation notes, hypotheses, leads, and caveats..." />
            <button disabled={!notesDirty} onClick={saveNotes} className="btn-primary disabled:opacity-40">Save Notes</button>
          </section>
        )}
      </div>
    </div>
  )
}

function EvidenceList({ items, onUpdate, onDelete }) {
  if (!items.length) return <Empty label="No evidence matches this view." />
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <article key={item.id} className="card p-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: 'var(--surface-4)', color: 'var(--blue)' }}>
              {item.source_url ? <Globe size={15} /> : <FileText size={15} />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-sm font-semibold truncate">{item.title}</h3>
                <EvidenceBadge status={item.status} />
                {item.confidence !== null && item.confidence !== undefined && <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>{item.confidence}% confidence</span>}
              </div>
              {item.source_url && (
                <a href={item.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs mt-1" style={{ color: 'var(--blue)' }}>
                  {item.source_url} <ExternalLink size={11} />
                </a>
              )}
              {(item.summary || item.notes) && <p className="text-sm mt-2 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{item.summary || item.notes}</p>}
              {!!item.tags?.length && <div className="flex gap-1.5 mt-3 flex-wrap">{item.tags.map((tag) => <span key={tag} className="text-[11px] px-2 py-1 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>{tag}</span>)}</div>}
            </div>
            <div className="flex items-center gap-1">
              <button title="Verify" onClick={() => onUpdate(item, { status: 'verified' })} className="p-1.5 rounded-lg" style={{ color: 'var(--green)' }}><CheckCircle2 size={15} /></button>
              <button title="Reject" onClick={() => onUpdate(item, { status: 'rejected' })} className="p-1.5 rounded-lg" style={{ color: 'var(--red)' }}><XCircle size={15} /></button>
              <button title="Delete" onClick={() => onDelete(item)} className="p-1.5 rounded-lg" style={{ color: 'var(--text-tertiary)' }}><Trash2 size={15} /></button>
            </div>
          </div>
        </article>
      ))}
    </div>
  )
}

function Timeline({ items }) {
  if (!items.length) return <Empty label="No timeline events yet." />
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={`${item.kind}-${item.id}-${item.at}`} className="flex gap-3">
          <div className="w-2 h-2 rounded-full mt-2" style={{ background: item.kind === 'evidence' ? 'var(--green)' : item.kind === 'ai' ? 'var(--indigo)' : 'var(--blue)' }} />
          <div className="flex-1 min-w-0 pb-3 border-b" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium truncate">{item.title}</p>
              <span className="text-[11px] capitalize" style={{ color: 'var(--text-tertiary)' }}>{item.kind}</span>
            </div>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>{new Date(item.at).toLocaleString()} · {item.status}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

function Empty({ label }) {
  return (
    <div className="text-center py-10 rounded-xl border border-dashed" style={{ color: 'var(--text-tertiary)', borderColor: 'var(--border)' }}>
      <p className="text-sm">{label}</p>
    </div>
  )
}
