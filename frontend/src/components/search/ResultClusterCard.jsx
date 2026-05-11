import { ExternalLink, EyeOff, FolderPlus, Layers3, MonitorPlay, StickyNote } from 'lucide-react'
import { clusterIntel, laneTone } from '../../utils/resultIntel'

function domainFor(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

export function ResultClusterCard({ cluster, active, onSelect, onSaveToggle, onHideToggle, onBrowserAssist }) {
  const top = cluster.top_result
  const intel = clusterIntel(cluster)
  const score = intel.score
  const domain = top?.source_domain || domainFor(top?.url || '')
  const lane = laneTone(intel.lane)

  return (
    <button
      onClick={() => onSelect(cluster)}
      className="text-left rounded-2xl overflow-hidden transition-all duration-200"
      style={{
        background: active ? 'var(--surface-4)' : 'var(--surface-3)',
        border: `1px solid ${active ? 'var(--blue)' : 'var(--border)'}`,
        boxShadow: active ? '0 0 0 1px rgba(10,132,255,0.2)' : 'none',
      }}
    >
      <div className="aspect-[4/3] overflow-hidden" style={{ background: 'var(--surface-2)' }}>
        {top?.thumbnail ? (
          <img src={top.thumbnail} alt={top.title || top.url} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No preview
          </div>
        )}
      </div>
      <div className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold truncate">{top?.title || domain || 'Untitled result'}</p>
            <p className="text-xs truncate mt-1" style={{ color: 'var(--text-secondary)' }}>{domain || top?.url}</p>
          </div>
          <div className="text-right">
            <p className="text-lg font-bold" style={{ color: 'var(--blue)' }}>{score}</p>
            <p className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>{intel.matchLabel}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap text-[11px]" style={{ color: 'var(--text-secondary)' }}>
          <span className="inline-flex items-center gap-1">
            <Layers3 size={11} />
            {cluster.cluster_size} in cluster
          </span>
          {cluster.score_label && (
            <span className="px-2 py-0.5 rounded-full" style={{ background: 'rgba(10,132,255,0.12)', color: 'var(--blue)' }}>
              {cluster.score_label}
            </span>
          )}
          <span className="px-2 py-0.5 rounded-full" style={{ background: lane.bg, color: lane.color }}>
            {lane.label}
          </span>
          <span className="px-2 py-0.5 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
            Source {intel.credibilityLabel}
          </span>
          {cluster.saved && <span className="px-2 py-0.5 rounded-full" style={{ background: 'rgba(48,209,88,0.12)', color: 'var(--green)' }}>Saved</span>}
          {cluster.hidden && <span className="px-2 py-0.5 rounded-full" style={{ background: 'rgba(255,159,10,0.12)', color: 'var(--orange)' }}>Hidden</span>}
        </div>

        {!!intel.locationClues.length && (
          <p className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
            Location clues: {intel.locationClues.slice(0, 2).map((clue) => clue.label).join(', ')}
          </p>
        )}

        {!!cluster.engines?.length && (
          <div className="flex items-center gap-1.5 flex-wrap text-[11px]">
            {cluster.engines.slice(0, 3).map((engine) => (
              <span key={engine} className="px-2 py-0.5 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
                {engine.replace('Scraper', '')}
              </span>
            ))}
          </div>
        )}

        {!!cluster.ranking_reasons?.length && (
          <p className="text-[11px] line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
            {cluster.ranking_reasons.join(' · ')}
          </p>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          <a
            href={top?.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(event) => event.stopPropagation()}
            className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg"
            style={{ background: 'var(--surface-2)', color: 'var(--text-primary)' }}
          >
            <ExternalLink size={12} />
            Open
          </a>
          <button
            onClick={(event) => {
              event.stopPropagation()
              onBrowserAssist(cluster)
            }}
            className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg"
            style={{ background: 'rgba(10,132,255,0.1)', color: 'var(--blue)' }}
          >
            <MonitorPlay size={12} />
            Browser Assist
          </button>
          <button
            onClick={(event) => {
              event.stopPropagation()
              onSaveToggle(cluster)
            }}
            className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg"
            style={{ background: 'var(--surface-2)', color: cluster.saved ? 'var(--green)' : 'var(--text-primary)' }}
          >
            <FolderPlus size={12} />
            {cluster.saved ? 'Saved' : 'Save'}
          </button>
          <button
            onClick={(event) => {
              event.stopPropagation()
              onHideToggle(cluster)
            }}
            className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg"
            style={{ background: 'var(--surface-2)', color: cluster.hidden ? 'var(--orange)' : 'var(--text-primary)' }}
          >
            <EyeOff size={12} />
            {cluster.hidden ? 'Unhide' : 'Hide'}
          </button>
          {cluster.note && (
            <span className="inline-flex items-center gap-1 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
              <StickyNote size={11} />
              Has note
            </span>
          )}
        </div>
      </div>
    </button>
  )
}
