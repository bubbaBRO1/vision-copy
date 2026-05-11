import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ScanSearch, MapPin, Shield, User, Brain, LayoutGrid } from 'lucide-react'
import { ImageUpload } from '../components/search/ImageUpload'
import { SearchProgress } from '../components/search/SearchProgress'
import { ChatPanel } from '../components/ai/ChatPanel'
import { GeoMap } from '../components/geo/GeoMap'
import { ConfidenceGauge } from '../components/ui/ConfidenceGauge'
import { FaceGallery } from '../components/results/FaceGallery'
import { BrowserAssistPanel } from '../components/search/BrowserAssistPanel'
import { ResultClusterCard } from '../components/search/ResultClusterCard'
import { ResultInspectorPanel } from '../components/search/ResultInspectorPanel'
import { useSearchStore } from '../store/searchStore'
import { useSearch } from '../hooks/useSearch'
import { useSSE } from '../hooks/useSSE'
import api from '../utils/api'
import toast from 'react-hot-toast'

const TABS = [
  { id: 'results', label: 'Results', icon: LayoutGrid },
  { id: 'geo', label: 'Location', icon: MapPin },
  { id: 'forensics', label: 'Forensics', icon: Shield },
  { id: 'faces', label: 'Faces', icon: User },
]

function ThreatBand({ score }) {
  let color = 'var(--green)'
  if (score >= 80) color = 'var(--red)'
  else if (score >= 60) color = 'var(--orange)'
  else if (score >= 40) color = 'var(--yellow)'
  return <div className="h-1 rounded-t-xl w-full" style={{ background: color }} />
}

function ForensicsPanel({ data }) {
  const forensics = data?.['Forensics (ELA)'] || {}
  const ai = data?.['AI Analysis (CLIP/DeepFace)'] || {}
  const steg = data?.['Steganography'] || {}

  const formatSteg = (obj) => {
    if (!obj || typeof obj !== 'object') return []
    return Object.entries(obj).filter(([, v]) => v !== null && v !== undefined)
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="card p-5">
        <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>Error Level Analysis</h3>
        {forensics.ela?.manipulation_probability !== undefined ? (
          <div className="flex items-center gap-5">
            <ConfidenceGauge score={Math.round(forensics.ela.manipulation_probability * 100)} size={72} />
            <div>
              <p className="text-sm font-medium">{forensics.ela?.verdict || 'Analysis complete'}</p>
              {forensics.ela?.ela_mean !== undefined && (
                <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>ELA mean: {forensics.ela.ela_mean?.toFixed(2)}</p>
              )}
            </div>
          </div>
        ) : <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>ELA not available</p>}
      </div>

      <div className="card p-5">
        <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>AI Generation Detection</h3>
        {ai.deepfake_probability !== undefined ? (
          <div className="flex items-center gap-5">
            <ConfidenceGauge score={Math.round(ai.deepfake_probability * 100)} size={72} />
            <div>
              <p className="text-sm font-medium">{ai.verdict || ''}</p>
            </div>
          </div>
        ) : <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>AI detection not available</p>}
      </div>

      <div className="card p-5 md:col-span-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>Steganography</h3>
        {formatSteg(steg).length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {formatSteg(steg).map(([k, v]) => (
              <div key={k} className="p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                <p className="text-[11px] font-medium uppercase tracking-wider mb-1" style={{ color: 'var(--text-tertiary)' }}>{k.replace(/_/g, ' ')}</p>
                <p className="text-sm font-medium">{String(v)}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No steganography data available</p>
        )}
      </div>
    </div>
  )
}

function FacesPanel({ data, searchId }) {
  return <FaceGallery results={data} searchId={searchId} />
}

function ProjectAssigner({ searchId }) {
  const [projects, setProjects] = useState([])
  const [assigned, setAssigned] = useState(null)

  useEffect(() => {
    if (!searchId) return
    api.get('/api/projects/').then(r => setProjects(r.data)).catch(() => {})
  }, [searchId])

  const assign = async (projectId, projectName) => {
    try {
      await api.patch(`/api/search/${searchId}/project`, { project_id: projectId })
      setAssigned(projectName || null)
      toast.success(projectId ? `Assigned to ${projectName}` : 'Removed from project')
    } catch {
      toast.error('Failed to assign project')
    }
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Attach search:</span>
      {projects.slice(0, 4).map((project) => (
        <button
          key={project.id}
          onClick={() => assign(project.id, project.name)}
          className="text-xs px-3 py-1.5 rounded-lg"
          style={{ background: assigned === project.name ? 'rgba(10,132,255,0.12)' : 'var(--surface-3)', color: assigned === project.name ? 'var(--blue)' : 'var(--text-primary)' }}
        >
          {project.name}
        </button>
      ))}
      {assigned && (
        <button
          onClick={() => assign(null, null)}
          className="text-xs px-3 py-1.5 rounded-lg"
          style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}
        >
          Clear
        </button>
      )}
    </div>
  )
}

export default function Search() {
  const { status, results, currentSearchId } = useSearchStore()
  const { abort } = useSearch()
  const [tab, setTab] = useState('results')
  const [chatOpen, setChatOpen] = useState(false)
  const [clusters, setClusters] = useState([])
  const [projects, setProjects] = useState([])
  const [selectedCluster, setSelectedCluster] = useState(null)
  const [resultQuery, setResultQuery] = useState('')
  const [scoreFloor, setScoreFloor] = useState(60)
  const [includeHidden, setIncludeHidden] = useState(false)
  const [onlyStrong, setOnlyStrong] = useState(false)
  const [noteDraft, setNoteDraft] = useState('')
  const [browserRunId, setBrowserRunId] = useState(null)
  const [browserRun, setBrowserRun] = useState(null)
  const [geolocationBrief, setGeolocationBrief] = useState(null)
  const [browserOptions, setBrowserOptions] = useState({
    mode: 'isolated',
    max_pages: 5,
    screenshot: true,
    persist_artifacts: true,
    is_incognito: false,
    confirm_incognito: false,
    project_id: null,
  })

  const geoData = results?.['Geolocation'] || {}
  const primary = geolocationBrief?.primary || geoData?.primary
  const alternates = geolocationBrief?.alternates || geoData?.alternates || []
  const intelScore = results?.['Scoring & Report']?.intel_score || 0

  const loadClusters = async () => {
    if (!currentSearchId) return
    try {
      const { data } = await api.get(`/api/search/${currentSearchId}/results`, {
        params: { include_hidden: includeHidden },
      })
      setClusters(data.results || [])
      setSelectedCluster((prev) => {
        if (!prev) return data.results?.[0] || null
        return data.results?.find((item) => item.result_key === prev.result_key) || data.results?.[0] || null
      })
    } catch {
      setClusters([])
    }
  }

  useEffect(() => {
    if (status === 'done' && currentSearchId) loadClusters()
  }, [status, currentSearchId, includeHidden])

  useEffect(() => {
    api.get('/api/projects/').then((r) => setProjects(r.data)).catch(() => setProjects([]))
  }, [])

  useEffect(() => {
    if (!selectedCluster) {
      setNoteDraft('')
      return
    }
    setNoteDraft(selectedCluster.note || '')
  }, [selectedCluster])

  useEffect(() => {
    if (!currentSearchId || status !== 'done') {
      setGeolocationBrief(null)
      return
    }
    api.get(`/api/geolocate/${currentSearchId}`)
      .then(({ data }) => setGeolocationBrief(data))
      .catch(() => setGeolocationBrief(null))
  }, [currentSearchId, status])

  useSSE(browserRunId ? `/api/browser-assist/runs/${browserRunId}/stream` : null, {
    enabled: !!browserRunId,
    onMessage: async () => {
      if (!browserRunId) return
      const { data } = await api.get(`/api/browser-assist/runs/${browserRunId}`)
      setBrowserRun(data)
    },
    onDone: async () => {
      if (!browserRunId) return
      const { data } = await api.get(`/api/browser-assist/runs/${browserRunId}`)
      setBrowserRun(data)
    },
  })

  const filteredClusters = useMemo(() => {
    return clusters.filter((cluster) => {
      const top = cluster.top_result || {}
      const score = Math.round(top.similarity_pct || 0)
      const haystack = `${top.title || ''} ${top.url || ''} ${top.source_domain || ''}`.toLowerCase()
      if (onlyStrong && score < 80) return false
      if (score < scoreFloor) return false
      if (resultQuery && !haystack.includes(resultQuery.toLowerCase())) return false
      return true
    })
  }, [clusters, onlyStrong, scoreFloor, resultQuery])

  const updateClusterState = async (cluster, nextState) => {
    if (!currentSearchId) return
    await api.patch(`/api/search/${currentSearchId}/results/state`, {
      result_key: cluster.result_key,
      ...nextState,
    })
    await loadClusters()
  }

  const updateBrowserOptions = (patch) => {
    setBrowserOptions((current) => {
      const next = { ...current, ...patch }
      if (next.is_incognito) {
        next.persist_artifacts = false
      } else if (patch.is_incognito === false && !('persist_artifacts' in patch)) {
        next.persist_artifacts = true
      }
      if (!next.is_incognito) {
        next.confirm_incognito = false
      }
      return next
    })
  }

  const startBrowserAssist = async (cluster = selectedCluster) => {
    if (!cluster) return
    try {
      const payload = {
        search_id: currentSearchId,
        project_id: browserOptions.project_id || null,
        urls: cluster.items.slice(0, browserOptions.max_pages).map((item) => item.url).filter(Boolean),
        options: {
          mode: browserOptions.mode,
          max_pages: browserOptions.max_pages,
          screenshot: browserOptions.screenshot,
        },
        is_incognito: browserOptions.is_incognito,
        confirm_incognito: browserOptions.confirm_incognito,
        persist_artifacts: browserOptions.persist_artifacts,
      }
      const { data } = await api.post('/api/browser-assist/runs', payload)
      setBrowserRunId(data.run_id)
      const runDetails = await api.get(`/api/browser-assist/runs/${data.run_id}`)
      setBrowserRun(runDetails.data)
      toast.success('Browser Assist started')
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to start Browser Assist')
    }
  }

  const cancelBrowserAssist = async () => {
    if (!browserRunId) return
    await api.post(`/api/browser-assist/runs/${browserRunId}/cancel`)
    const { data } = await api.get(`/api/browser-assist/runs/${browserRunId}`)
    setBrowserRun(data)
  }

  const saveNote = async () => {
    if (!selectedCluster) return
    await updateClusterState(selectedCluster, { note: noteDraft })
    toast.success('Result note saved')
  }

  const promoteToEvidence = async (cluster = selectedCluster) => {
    if (!cluster || !browserOptions.project_id) {
      toast.error('Choose a case first')
      return
    }
    const top = cluster.top_result || {}
    try {
      await api.post(`/api/projects/${browserOptions.project_id}/evidence`, {
        search_id: currentSearchId,
        result_key: cluster.result_key,
        title: top.title || top.source_domain || top.url || 'Search result lead',
        evidence_type: 'search_result',
        status: 'needs_review',
        confidence: Math.round(top.similarity_pct || cluster.rank_score * 100 || 0),
        source_url: top.url,
        summary: cluster.ranking_reasons?.join('; ') || null,
        notes: noteDraft || null,
        tags: ['search-result', ...(cluster.engines || []).map((engine) => engine.replace('Scraper', '').toLowerCase())],
        provenance: {
          search_id: currentSearchId,
          result_key: cluster.result_key,
          engines: cluster.engines || [],
          cluster_size: cluster.cluster_size,
        },
        metadata_json: { top_result: top, items: cluster.items },
      })
      toast.success('Promoted to case evidence')
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to promote evidence')
    }
  }

  return (
    <div className="flex h-full">
      <div className={`flex-1 overflow-y-auto p-5 space-y-4 transition-all duration-300 ${chatOpen ? 'max-w-[calc(100%-380px)]' : 'w-full'}`}>
        {status === 'idle' && (
          <div className="max-w-lg mx-auto pt-10">
            <div className="text-center mb-8">
              <div className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(10,132,255,0.1)' }}>
                <ScanSearch size={28} style={{ color: 'var(--blue)' }} />
              </div>
              <h2 className="text-xl font-semibold tracking-tight">Analyze an image</h2>
              <p className="text-sm mt-2" style={{ color: 'var(--text-secondary)' }}>
                Upload once, then inspect clustered matches, location clues, forensics, and faces.
              </p>
            </div>
            <ImageUpload />
          </div>
        )}

        {(status === 'running' || status === 'uploading') && (
          <div className="max-w-lg mx-auto pt-4">
            <SearchProgress onCancel={abort} />
          </div>
        )}

        {(status === 'done' || (status === 'running' && results)) && (
          <div className="space-y-4">
            {intelScore > 0 && (
              <div className="card overflow-hidden">
                <ThreatBand score={intelScore} />
                <div className="p-5 flex items-center gap-5">
                  <ConfidenceGauge score={intelScore} size={80} />
                  <div className="flex-1">
                    <h3 className="font-semibold">Intel Score</h3>
                    <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                      Composite score across identity, source quality, authenticity, and location evidence.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {status === 'done' && currentSearchId && (
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <ProjectAssigner searchId={currentSearchId} />
                {browserRun && <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Browser Assist: {browserRun.status}</span>}
              </div>
            )}

            <div className="flex items-center gap-1 p-1 rounded-xl" style={{ background: 'var(--surface-3)' }}>
              {TABS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className="relative flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg transition-all duration-200"
                  style={{
                    background: tab === id ? 'var(--surface-4)' : 'transparent',
                    color: tab === id ? 'var(--text-primary)' : 'var(--text-secondary)',
                    boxShadow: tab === id ? 'var(--shadow-sm)' : 'none',
                  }}
                >
                  <Icon size={13} />
                  {label}
                </button>
              ))}
            </div>

            <AnimatePresence mode="wait">
              {tab === 'results' && (
                <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                  <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr),340px] gap-4 items-start">
                    <div className="space-y-4">
                      <div className="card p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
                        <input
                          className="input"
                          placeholder="Filter by domain or title…"
                          value={resultQuery}
                          onChange={(event) => setResultQuery(event.target.value)}
                        />
                        <label className="space-y-1">
                          <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                            Score floor
                          </span>
                          <input type="range" min="0" max="100" value={scoreFloor} onChange={(event) => setScoreFloor(Number(event.target.value))} />
                          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{scoreFloor}+</p>
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <input type="checkbox" checked={onlyStrong} onChange={(event) => setOnlyStrong(event.target.checked)} />
                          Only strong matches
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <input type="checkbox" checked={includeHidden} onChange={(event) => setIncludeHidden(event.target.checked)} />
                          Show hidden
                        </label>
                      </div>

                      {filteredClusters.length === 0 ? (
                        <div className="card p-10 text-center">
                          <p className="text-sm font-medium">No clustered results match these filters</p>
                          <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                            Adjust the score floor or show hidden results.
                          </p>
                        </div>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4">
                          {filteredClusters.map((cluster) => (
                            <ResultClusterCard
                              key={cluster.result_key}
                              cluster={cluster}
                              active={selectedCluster?.result_key === cluster.result_key}
                              onSelect={setSelectedCluster}
                              onSaveToggle={(target) => updateClusterState(target, { saved: !target.saved })}
                              onHideToggle={(target) => updateClusterState(target, { hidden: !target.hidden })}
                              onBrowserAssist={startBrowserAssist}
                            />
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="space-y-4">
                      <ResultInspectorPanel
                        cluster={selectedCluster}
                        note={noteDraft}
                        onNoteChange={setNoteDraft}
                        onSaveNote={saveNote}
                        browserRunId={browserRunId}
                        browserAssistArtifacts={(browserRun?.artifacts || []).filter((artifact) => selectedCluster?.items?.some((item) => item.url === artifact.source_url))}
                        projects={projects}
                        projectId={browserOptions.project_id || ''}
                        onProjectChange={(projectId) => updateBrowserOptions({ project_id: projectId })}
                        onPromoteEvidence={promoteToEvidence}
                      />
                      <BrowserAssistPanel
                        cluster={selectedCluster}
                        projects={projects}
                        options={browserOptions}
                        onOptionsChange={updateBrowserOptions}
                        onStart={() => startBrowserAssist(selectedCluster)}
                        run={browserRun}
                        onCancel={cancelBrowserAssist}
                      />
                    </div>
                  </div>
                </motion.div>
              )}

              {tab === 'geo' && (
                <motion.div key="geo" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                  {results?.['EXIF & Metadata']?.gps && (
                    <div className="flex items-start gap-3 p-3 rounded-xl" style={{ background: 'rgba(255,159,10,0.08)', border: '1px solid rgba(255,159,10,0.25)' }}>
                      <MapPin size={14} style={{ color: 'var(--orange)', flexShrink: 0, marginTop: 1 }} />
                      <div>
                        <p className="text-xs font-semibold" style={{ color: 'var(--orange)' }}>Metadata may be inaccurate</p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                          Treat EXIF GPS as a clue, not proof. Verify it against visual evidence and source context.
                        </p>
                      </div>
                    </div>
                  )}
                  {primary ? (
                    <>
                      <GeoMap primary={primary} alternates={alternates} />
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div className="card p-5">
                          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>
                            Location inference
                          </h3>
                          <p className="text-sm font-medium">{primary.address}</p>
                          <p className="text-xs mono mt-1" style={{ color: 'var(--text-secondary)' }}>{primary.lat}, {primary.lon}</p>
                          <div className="flex items-center gap-2 mt-3 flex-wrap">
                            {geolocationBrief?.confidence_label && (
                              <span className="px-2 py-1 rounded-full text-xs" style={{ background: 'rgba(10,132,255,0.12)', color: 'var(--blue)' }}>
                                {geolocationBrief.confidence_label}
                              </span>
                            )}
                            {primary.source && (
                              <span className="px-2 py-1 rounded-full text-xs" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>
                                {primary.source}
                              </span>
                            )}
                          </div>
                          {geolocationBrief?.overall_verdict && (
                            <p className="text-xs mt-3" style={{ color: 'var(--text-secondary)' }}>
                              {geolocationBrief.overall_verdict}
                            </p>
                          )}
                        </div>

                        <div className="card p-5">
                          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>
                            What to verify next
                          </h3>
                          <div className="space-y-2">
                            {(geolocationBrief?.what_to_verify_next || []).map((step) => (
                              <div key={step} className="rounded-lg p-3 text-sm" style={{ background: 'var(--surface-2)' }}>
                                {step}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>

                      {!!geolocationBrief?.evidence?.length && (
                        <div className="card p-5">
                          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>
                            Evidence
                          </h3>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {geolocationBrief.evidence.map((item) => (
                              <div key={`${item.title}-${item.detail}`} className="rounded-lg p-3" style={{ background: 'var(--surface-2)' }}>
                                <div className="flex items-center gap-2 mb-2">
                                  <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                                    {item.title}
                                  </span>
                                  <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>
                                    {item.strength}
                                  </span>
                                </div>
                                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{item.detail}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {!!geolocationBrief?.location_signals?.length && (
                        <div className="card p-5">
                          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>
                            Signals
                          </h3>
                          <div className="flex items-center gap-2 flex-wrap">
                            {geolocationBrief.location_signals.map((signal) => (
                              <span key={signal} className="px-2 py-1 rounded-full text-xs" style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
                                {signal}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="card p-10 text-center">
                      <p className="text-sm font-medium">No location inference available</p>
                      <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                        No trustworthy GPS, landmark, or contextual clues were surfaced.
                      </p>
                    </div>
                  )}
                </motion.div>
              )}

              {tab === 'forensics' && (
                <motion.div key="forensics" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <ForensicsPanel data={results} />
                </motion.div>
              )}

              {tab === 'faces' && (
                <motion.div key="faces" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <FacesPanel data={results} searchId={currentSearchId} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      <div className="relative flex-shrink-0 flex">
        <button
          onClick={() => setChatOpen((open) => !open)}
          className="absolute bottom-6 right-4 z-10 w-11 h-11 rounded-full flex items-center justify-center shadow-lg transition-all duration-200"
          style={{
            background: chatOpen ? 'var(--blue)' : 'var(--surface-3)',
            border: '1px solid var(--border)',
            boxShadow: chatOpen ? '0 4px 20px rgba(10,132,255,0.4)' : 'var(--shadow-md)',
          }}
          title="Toggle AI"
        >
          <Brain size={18} style={{ color: chatOpen ? '#fff' : 'var(--text-secondary)' }} />
        </button>

        <AnimatePresence>
          {chatOpen && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 380, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden flex-shrink-0"
              style={{ borderLeft: '1px solid var(--border)', background: 'var(--surface-2)' }}
            >
              <ChatPanel searchId={currentSearchId} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
