import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, XCircle, Loader2, Circle } from 'lucide-react'
import { useSearchStore } from '../../store/searchStore'
import { formatDuration } from '../../utils/formatters'

function StageIcon({ status }) {
  if (status === 'done')    return <CheckCircle size={14} style={{ color: 'var(--green)' }} />
  if (status === 'failed')  return <XCircle size={14} style={{ color: 'var(--red)' }} />
  if (status === 'running') return <Loader2 size={14} style={{ color: 'var(--blue)' }} className="animate-spin" />
  return <Circle size={14} style={{ color: 'var(--text-tertiary)' }} />
}

const STATUS_BORDER = {
  done:    'var(--green)',
  running: 'var(--blue)',
  failed:  'var(--red)',
  pending: 'var(--surface-4)',
}

export function SearchProgress({ onCancel }) {
  const { stages, progress, filename, status } = useSearchStore()
  const [elapsed, setElapsed] = useState(0)

  const done = stages.filter(s => s.status === 'done').length
  const total = stages.length || 1
  const running = stages.filter(s => s.status === 'running')

  useEffect(() => {
    if (status !== 'running') return
    const t = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(t)
  }, [status])

  const formatElapsed = (s) => {
    if (s < 60) return `${s}s`
    return `${Math.floor(s / 60)}m ${s % 60}s`
  }

  const r = 20
  const circ = 2 * Math.PI * r

  return (
    <div
      className="p-6 space-y-5 rounded-xl"
      style={{
        background: 'var(--glass-bg)',
        backdropFilter: 'blur(20px) saturate(180%)',
        border: '1px solid var(--glass-border)',
        boxShadow: 'var(--shadow-lg)',
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
            {filename || 'Analyzing image…'}
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            {done} / {total} stages · {formatElapsed(elapsed)}
          </p>
          {running.length > 0 && (
            <p className="text-xs mt-1 mono animate-pulse" style={{ color: 'var(--blue)' }}>
              {running.map(s => s.name).join(' · ')}
            </p>
          )}
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Circular progress */}
          <svg width="52" height="52" viewBox="0 0 52 52">
            <circle cx="26" cy="26" r={r} fill="none" stroke="var(--surface-4)" strokeWidth="4" />
            <motion.circle
              cx="26" cy="26" r={r} fill="none"
              stroke="var(--blue)" strokeWidth="4" strokeLinecap="round"
              strokeDasharray={circ}
              initial={{ strokeDashoffset: circ }}
              animate={{ strokeDashoffset: circ * (1 - progress / 100) }}
              style={{ transform: 'rotate(-90deg)', transformOrigin: '50% 50%' }}
              transition={{ duration: 0.5 }}
            />
            <text x="26" y="30" textAnchor="middle" fontSize="10" fill="var(--text-primary)" fontFamily="Inter, sans-serif" fontWeight="600">
              {progress}%
            </text>
          </svg>

          {status === 'running' && (
            <button
              onClick={onCancel}
              className="text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
              style={{ color: 'var(--red)' }}
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface-4)' }}>
        <motion.div
          className="h-1 rounded-full"
          style={{ background: 'var(--blue)' }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4 }}
        />
      </div>

      {/* Stage list */}
      <div className="space-y-1.5 max-h-48 overflow-y-auto">
        <AnimatePresence initial={false}>
          {stages.map((stage) => (
            <motion.div
              key={stage.name}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-2.5 text-xs py-1 pl-3 rounded-md border-l-[3px]"
              style={{
                borderColor: STATUS_BORDER[stage.status] || 'var(--surface-4)',
                color: stage.status === 'running'
                  ? 'var(--text-primary)'
                  : stage.status === 'done'
                    ? 'var(--text-secondary)'
                    : stage.status === 'failed'
                      ? 'var(--red)'
                      : 'var(--text-tertiary)',
              }}
            >
              <StageIcon status={stage.status} />
              <span className="flex-1">{stage.name}</span>
              {stage.data?.elapsed_ms && (
                <span className="mono" style={{ color: 'var(--text-tertiary)' }}>{formatDuration(stage.data.elapsed_ms)}</span>
              )}
              {stage.status === 'failed' && stage.data?.reason && (
                <span className="truncate max-w-28" style={{ color: 'var(--red)' }}>{stage.data.reason}</span>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
