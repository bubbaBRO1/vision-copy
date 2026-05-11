import { motion } from 'framer-motion'
import { scoreToColor, scoreToLabel } from '../../utils/confidence'

export function ConfidenceGauge({ score = 0, size = 80, breakdown = null, label = true }) {
  const r = (size / 2) - 8
  const circ = 2 * Math.PI * r
  const dashoffset = circ - (score / 100) * circ * 0.75
  const color = scoreToColor(score)

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size * 0.7 }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-225deg)' }}>
          {/* Track */}
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke="var(--surface-4)" strokeWidth="6"
            strokeDasharray={`${circ * 0.75} ${circ * 0.25}`}
            strokeLinecap="round"
          />
          {/* Fill */}
          <motion.circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke={color} strokeWidth="6"
            strokeDasharray={`${circ * 0.75} ${circ * 0.25}`}
            strokeLinecap="round"
            initial={{ strokeDashoffset: circ }}
            animate={{ strokeDashoffset: dashoffset }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center" style={{ paddingTop: size * 0.05 }}>
          <span
            className="font-bold"
            style={{ fontSize: size * 0.2, color, fontFamily: 'Inter, sans-serif', fontVariantNumeric: 'tabular-nums' }}
          >
            {score}%
          </span>
        </div>
      </div>
      {label && (
        <span className="text-xs font-medium" style={{ color }}>{scoreToLabel(score)}</span>
      )}
      {breakdown && (
        <div className="text-xs mt-1 space-y-0.5 w-full">
          {Object.entries(breakdown).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-2">
              <span style={{ color: 'var(--text-secondary)' }}>{k}</span>
              <span className="font-medium mono" style={{ color }}>{v}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
