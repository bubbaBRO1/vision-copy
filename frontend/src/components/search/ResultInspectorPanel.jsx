import { ExternalLink, Globe, Layers3, MapPin, Plus, StickyNote } from 'lucide-react'
import { clusterIntel, laneTone } from '../../utils/resultIntel'

function formatScore(item) {
  return Math.round(item?.similarity_pct || 0)
}

export function ResultInspectorPanel({
  cluster,
  note,
  onNoteChange,
  onSaveNote,
  browserAssistArtifacts = [],
  browserRunId = null,
  projects = [],
  projectId = '',
  onProjectChange,
  onPromoteEvidence,
}) {
  if (!cluster) {
    return (
      <div className="card p-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
        Select a result cluster to inspect evidence, compare duplicates, and save notes.
      </div>
    )
  }

  const top = cluster.top_result
  const intel = clusterIntel(cluster)
  const lane = laneTone(intel.lane)

  return (
    <div className="card p-4 space-y-4 sticky top-0">
      <div>
        <p className="text-sm font-semibold">{top?.title || 'Selected result'}</p>
        <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
          Score {formatScore(top)} · {cluster.cluster_size} clustered result{cluster.cluster_size !== 1 ? 's' : ''}
        </p>
        {!!cluster.ranking_reasons?.length && (
          <p className="text-[11px] mt-2" style={{ color: 'var(--text-secondary)' }}>
            {cluster.ranking_reasons.join(' · ')}
          </p>
        )}
        <div className="flex items-center gap-2 mt-3 flex-wrap text-[11px]">
          <span className="px-2 py-1 rounded-full" style={{ background: lane.bg, color: lane.color }}>
            {lane.label}
          </span>
          <span className="px-2 py-1 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
            Match: {intel.matchLabel}
          </span>
          <span className="px-2 py-1 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
            Source: {intel.credibilityLabel}{intel.credibilityScore !== null ? ` ${intel.credibilityScore}` : ''}
          </span>
        </div>
      </div>

      <div className="space-y-2 text-xs">
        {top?.url && (
          <a href={top.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5" style={{ color: 'var(--blue)' }}>
            <ExternalLink size={12} />
            Open source
          </a>
        )}
        <div className="flex items-start gap-2">
          <Globe size={12} style={{ color: 'var(--text-tertiary)', marginTop: 2 }} />
          <span className="break-all">{top?.url}</span>
        </div>
        <div className="flex items-start gap-2">
          <Layers3 size={12} style={{ color: 'var(--text-tertiary)', marginTop: 2 }} />
          <span>{cluster.items.length} duplicate or near-duplicate hits grouped under this key.</span>
        </div>
        {top?.source_domain && (
          <div className="flex items-start gap-2">
            <MapPin size={12} style={{ color: 'var(--text-tertiary)', marginTop: 2 }} />
            <span>{top.source_domain}</span>
          </div>
        )}
        {!!cluster.engines?.length && (
          <div className="flex items-start gap-2">
            <Layers3 size={12} style={{ color: 'var(--text-tertiary)', marginTop: 2 }} />
            <span>Engines: {cluster.engines.map((engine) => engine.replace('Scraper', '')).join(', ')}</span>
          </div>
        )}
      </div>

      <div className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
          Analyst brief
        </p>
        <div className="grid grid-cols-1 gap-2 text-xs">
          {intel.source_credibility?.basis && (
            <div className="rounded-lg p-2.5" style={{ background: 'var(--surface-2)' }}>
              {intel.source_credibility.basis}
            </div>
          )}
          {!!intel.nextSteps.length && intel.nextSteps.slice(0, 4).map((step) => (
            <div key={step} className="rounded-lg p-2.5" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
              {step}
            </div>
          ))}
        </div>
      </div>

      {(!!intel.locationClues.length || !!intel.contradictionHints.length) && (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
            Clues and contradictions
          </p>
          {!!intel.locationClues.length && (
            <div className="flex items-center gap-2 flex-wrap">
              {intel.locationClues.slice(0, 6).map((clue) => (
                <span key={`${clue.type}-${clue.label}`} className="px-2 py-1 rounded-full text-[11px]" style={{ background: 'rgba(10,132,255,0.12)', color: 'var(--blue)' }}>
                  {clue.label}
                </span>
              ))}
            </div>
          )}
          {intel.contradictionHints.map((hint) => (
            <div key={hint} className="rounded-lg p-2.5 text-xs" style={{ background: 'rgba(255,159,10,0.1)', color: 'var(--orange)' }}>
              {hint}
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
          Provenance
        </p>
        <div className="rounded-lg p-2.5 text-[11px] space-y-1 break-all" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
          <p>Source: {intel.provenance.source_url || top?.url || 'n/a'}</p>
          <p>Domain: {intel.provenance.source_domain || top?.source_domain || 'n/a'}</p>
          <p>Cluster: {intel.provenance.cluster_size || cluster.cluster_size || 1} hit(s)</p>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
          Cluster items
        </p>
        <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
          {cluster.items.map((item, index) => (
            <div key={`${item.url}-${index}`} className="rounded-lg p-2.5 space-y-1.5" style={{ background: 'var(--surface-2)' }}>
              <div className="flex items-start justify-between gap-3">
                <p className="text-xs font-medium">{item.title || item.url}</p>
                <span className="text-[11px] font-semibold" style={{ color: 'var(--blue)' }}>
                  {formatScore(item)}
                </span>
              </div>
              <p className="text-[11px] line-clamp-2 break-all" style={{ color: 'var(--text-secondary)' }}>
                {item.url}
              </p>
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[11px] font-medium"
                style={{ color: 'var(--blue)' }}
              >
                <ExternalLink size={11} />
                Open item
              </a>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        {!!projects.length && (
          <select className="input" value={projectId || ''} onChange={(event) => onProjectChange?.(event.target.value || null)}>
            <option value="">Choose case for evidence</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        )}
        <button disabled={!projectId} onClick={() => onPromoteEvidence?.(cluster)} className="btn-secondary w-full disabled:opacity-40">
          <span className="inline-flex items-center gap-1.5">
            <Plus size={13} />
            Promote to case evidence
          </span>
        </button>
        <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
          Note
        </p>
        <textarea
          className="input min-h-[120px] py-3"
          value={note}
          onChange={(event) => onNoteChange(event.target.value)}
          placeholder="Add evidence notes for this result cluster..."
        />
        <button onClick={onSaveNote} className="btn-primary w-full">
          <span className="inline-flex items-center gap-1.5">
            <StickyNote size={13} />
            Save note
          </span>
        </button>
      </div>

      {!!browserAssistArtifacts.length && (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
            Browser Assist evidence
          </p>
          <div className="space-y-2">
            {browserAssistArtifacts.map((artifact) => (
              <div key={artifact.id} className="rounded-lg p-3 space-y-2" style={{ background: 'var(--surface-2)' }}>
                {artifact.screenshot_path && browserRunId && (
                  <img
                    src={`/api/browser-assist/runs/${browserRunId}/artifacts/${artifact.id}/screenshot`}
                    alt={artifact.title || artifact.final_url || artifact.source_url}
                    className="w-full rounded-lg border object-cover max-h-44"
                    style={{ borderColor: 'var(--border)' }}
                  />
                )}
                <p className="text-xs font-medium">{artifact.title || artifact.final_url || artifact.source_url}</p>
                {artifact.snippet && (
                  <p className="text-[11px] mt-1 line-clamp-3" style={{ color: 'var(--text-secondary)' }}>
                    {artifact.snippet}
                  </p>
                )}
                {(artifact.final_url || artifact.source_url) && (
                  <a
                    href={artifact.final_url || artifact.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] font-medium"
                    style={{ color: 'var(--blue)' }}
                  >
                    <ExternalLink size={11} />
                    Open evidence
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
