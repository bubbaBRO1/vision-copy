import { ExternalLink, Globe, MonitorPlay, Shield, Square } from 'lucide-react'

export function BrowserAssistPanel({
  cluster,
  projects = [],
  options,
  onOptionsChange,
  onStart,
  run,
  onCancel,
}) {
  const canStart = !!cluster?.items?.some((item) => item.url)

  return (
    <div className="card p-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MonitorPlay size={16} style={{ color: 'var(--blue)' }} />
          <div>
            <p className="text-sm font-semibold">Browser Assist</p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              {run ? `Latest run: ${run.status}` : 'Open selected cluster pages in a controlled follow-up run'}
            </p>
          </div>
        </div>
        {run && run.status !== 'completed' && run.status !== 'cancelled' && (
          <button
            onClick={onCancel}
            className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg"
            style={{ background: 'rgba(255,69,58,0.1)', color: 'var(--red)' }}
          >
            <Square size={11} />
            Stop
          </button>
        )}
      </div>

      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
              Mode
            </span>
            <select
              className="input"
              value={options.mode}
              onChange={(event) => onOptionsChange({ mode: event.target.value })}
            >
              <option value="isolated">Isolated</option>
              <option value="profile">Profile</option>
            </select>
          </label>

          <label className="space-y-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
              Max pages
            </span>
            <select
              className="input"
              value={String(options.max_pages)}
              onChange={(event) => onOptionsChange({ max_pages: Number(event.target.value) })}
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="space-y-1.5 block">
          <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
            Save to project
          </span>
          <select
            className="input"
            value={options.project_id || ''}
            onChange={(event) => onOptionsChange({ project_id: event.target.value || null })}
          >
            <option value="">No project</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>{project.name}</option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={options.screenshot}
            onChange={(event) => onOptionsChange({ screenshot: event.target.checked })}
          />
          Capture screenshots when available
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={options.persist_artifacts}
            onChange={(event) => onOptionsChange({ persist_artifacts: event.target.checked })}
            disabled={options.is_incognito}
          />
          Persist artifacts to the run
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={options.is_incognito}
            onChange={(event) => onOptionsChange({ is_incognito: event.target.checked })}
          />
          Run in incognito mode
        </label>

        {options.is_incognito && (
          <div className="rounded-xl p-3 space-y-2" style={{ background: 'rgba(255,159,10,0.08)', border: '1px solid rgba(255,159,10,0.2)' }}>
            <div className="flex items-start gap-2">
              <Shield size={14} style={{ color: 'var(--orange)', marginTop: 1 }} />
              <div>
                <p className="text-xs font-semibold" style={{ color: 'var(--orange)' }}>Incognito requires confirmation</p>
                <p className="text-[11px] mt-1" style={{ color: 'var(--text-secondary)' }}>
                  Persisted artifacts are disabled for incognito runs.
                </p>
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={options.confirm_incognito}
                onChange={(event) => onOptionsChange({ confirm_incognito: event.target.checked })}
              />
              I understand this run will not persist artifacts
            </label>
          </div>
        )}

        <button
          onClick={onStart}
          disabled={!canStart}
          className="btn-primary w-full inline-flex items-center justify-center gap-2"
        >
          <MonitorPlay size={14} />
          {canStart ? 'Start Browser Assist' : 'Select a cluster first'}
        </button>
      </div>

      {run && (
        <>
          {!!run.approved_urls?.length && (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                Approved URLs
              </p>
              <div className="space-y-1.5">
                {run.approved_urls.map((url) => (
                  <div key={url} className="rounded-lg p-2.5 text-[11px] break-all" style={{ background: 'var(--surface-2)' }}>
                    {url}
                  </div>
                ))}
              </div>
            </div>
          )}

          {!!run.visited_urls?.length && (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                Visited URLs
              </p>
              <div className="space-y-1.5">
                {run.visited_urls.map((url, index) => (
                  <div key={`${url}-${index}`} className="rounded-lg p-2.5 text-[11px] break-all" style={{ background: 'var(--surface-2)' }}>
                    {url}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
              Run log
            </p>
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {(run.run_log || []).map((entry, index) => (
                <div key={`${entry.ts || index}-${index}`} className="rounded-lg p-2.5" style={{ background: 'var(--surface-2)' }}>
                  <p className="text-xs font-medium">{entry.message}</p>
                  {entry.url && (
                    <p className="text-[11px] truncate mt-1" style={{ color: 'var(--text-secondary)' }}>
                      {entry.url}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {!!run.error && (
            <div className="rounded-xl p-3 text-xs" style={{ background: 'rgba(255,69,58,0.08)', color: 'var(--red)' }}>
              {run.error}
            </div>
          )}

          {!!run.artifacts?.length && (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                Captured evidence
              </p>
              <div className="grid grid-cols-1 gap-3">
                {run.artifacts.map((artifact) => (
                  <div key={artifact.id} className="rounded-xl p-3 space-y-3" style={{ background: 'var(--surface-2)' }}>
                    {artifact.screenshot_path && (
                      <img
                        src={`/api/browser-assist/runs/${run.id}/artifacts/${artifact.id}/screenshot`}
                        alt={artifact.title || artifact.final_url || artifact.source_url}
                        className="w-full rounded-lg border object-cover max-h-48"
                        style={{ borderColor: 'var(--border)' }}
                      />
                    )}
                    <div className="space-y-1.5">
                      <p className="text-xs font-medium">{artifact.title || artifact.final_url || artifact.source_url}</p>
                      {artifact.snippet && (
                        <p className="text-[11px] line-clamp-4" style={{ color: 'var(--text-secondary)' }}>
                          {artifact.snippet}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {(artifact.final_url || artifact.source_url) && (
                        <a
                          href={artifact.final_url || artifact.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] font-medium"
                          style={{ color: 'var(--blue)' }}
                        >
                          <ExternalLink size={11} />
                          Open page
                        </a>
                      )}
                      {artifact.metadata?.capture && (
                        <span className="inline-flex items-center gap-1 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                          <Globe size={11} />
                          {artifact.metadata.capture}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
