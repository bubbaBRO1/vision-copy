import { useState, useRef, useEffect } from 'react'
import { Brain, ChevronDown } from 'lucide-react'
import api from '../utils/api'
import toast from 'react-hot-toast'

const DEPTHS = [
  { id: 'quick', label: 'Quick', desc: '~2 min · 2 queries · 5 sources' },
  { id: 'standard', label: 'Standard', desc: '~5 min · 5 queries · 15 sources' },
  { id: 'deep', label: 'Deep', desc: '~15 min · 10 queries · 30 sources' },
]

function renderMarkdown(text) {
  return text
    .replace(/^## (.+)$/gm, '<h2 class="text-accent-cyan font-bold text-base mt-4 mb-2">$1</h2>')
    .replace(/^### (.+)$/gm, '<h3 class="text-accent-green font-semibold text-sm mt-3 mb-1">$1</h3>')
    .replace(/\*\*(.*?)\*\*/g, '<strong class="text-text-primary">$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="bg-bg-secondary px-1 py-0.5 rounded font-mono text-xs text-accent-cyan">$1</code>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 text-xs text-text-dim leading-relaxed">• $1</li>')
    .replace(/\[(\d+)\]/g, '<sup class="text-accent-cyan cursor-pointer">[$1]</sup>')
    .replace(/\n/g, '<br/>')
}

export default function Research() {
  const [query, setQuery] = useState('')
  const [depth, setDepth] = useState('standard')
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState('')
  const reportRef = useRef(null)

  useEffect(() => {
    reportRef.current?.scrollTo(0, reportRef.current.scrollHeight)
  }, [report])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setRunning(true)
    setReport('')
    try {
      const { data } = await api.post('/api/research', { query, depth })
      const jobId = data.job_id

      const token = JSON.parse(localStorage.getItem('vision-auth') || '{}').state?.accessToken || ''
      const es = new EventSource(`/api/research/${jobId}/stream?token=${token}`)
      es.onmessage = (e) => {
        if (e.data === '[DONE]') { es.close(); setRunning(false); return }
        setReport(r => r + e.data)
      }
      es.onerror = () => { es.close(); setRunning(false); toast.error('Research stream failed') }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to start research')
      setRunning(false)
    }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-4">
      {/* Input */}
      <form onSubmit={handleSubmit} className="card p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Brain size={18} className="text-accent-cyan" />
          <h2 className="text-sm font-semibold mono text-accent-cyan">Deep Research</h2>
        </div>
        <input
          className="input text-sm"
          placeholder="Research topic or question..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          disabled={running}
        />
        <div className="flex gap-2 items-end">
          <div className="flex gap-2 flex-1">
            {DEPTHS.map(d => (
              <button
                key={d.id}
                type="button"
                onClick={() => setDepth(d.id)}
                className={`text-xs px-3 py-1.5 rounded border transition-all ${depth === d.id ? 'border-accent-cyan text-accent-cyan bg-accent-cyan/10' : 'border-border-color text-text-dim hover:border-text-dim'}`}
              >
                {d.label}
              </button>
            ))}
          </div>
          <button type="submit" disabled={running || !query.trim()} className="btn-primary text-sm px-4 py-1.5">
            {running ? 'Researching...' : 'Research'}
          </button>
        </div>
        <p className="text-xs text-text-dim">{DEPTHS.find(d => d.id === depth)?.desc}</p>
      </form>

      {/* Report */}
      {(report || running) && (
        <div
          ref={reportRef}
          className="card p-6 flex-1 overflow-y-auto"
        >
          {running && !report && (
            <div className="flex items-center gap-2 text-text-dim text-sm animate-pulse">
              <div className="flex gap-1">
                {[0,1,2].map(i => <div key={i} className="w-1.5 h-1.5 bg-accent-cyan rounded-full animate-bounce" style={{ animationDelay: `${i*0.15}s` }} />)}
              </div>
              Starting research pipeline...
            </div>
          )}
          {report && (
            <div
              className="prose-vision"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(report) }}
            />
          )}
          {running && report && (
            <span className="inline-block w-1.5 h-4 bg-accent-green animate-pulse ml-0.5" />
          )}
        </div>
      )}
    </div>
  )
}
