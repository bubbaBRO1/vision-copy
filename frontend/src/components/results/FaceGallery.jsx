import { useState, useEffect } from 'react'
import { ExternalLink, Database, AlertTriangle, ChevronDown, ChevronUp, UserCircle2, BookmarkPlus, EyeOff } from 'lucide-react'
import { Link } from 'react-router-dom'
import api from '../../utils/api'

function confidenceLabel(sim) {
  if (sim >= 70) return { text: 'High similarity', color: 'var(--green)' }
  if (sim >= 55) return { text: 'Possible match', color: 'var(--blue)' }
  if (sim >= 40) return { text: 'Low similarity', color: 'var(--orange)' }
  return { text: 'Unlikely match', color: 'var(--text-tertiary)' }
}

function AttributeTag({ label, color = 'default' }) {
  const styles = {
    default: { bg: 'var(--surface-4)', color: 'var(--text-secondary)' },
    green:   { bg: 'rgba(48,209,88,0.15)',   color: 'var(--green)' },
    blue:    { bg: 'rgba(10,132,255,0.15)',   color: 'var(--blue)' },
    orange:  { bg: 'rgba(255,159,10,0.15)',   color: 'var(--orange)' },
    purple:  { bg: 'rgba(191,90,242,0.15)',   color: 'var(--purple)' },
  }
  const s = styles[color] || styles.default
  return (
    <span
      className="text-[11px] font-medium px-2 py-0.5 rounded-full"
      style={{ background: s.bg, color: s.color }}
    >
      {label}
    </span>
  )
}

function FaceCard({ face, index, onSave, onHide }) {
  const [expanded, setExpanded] = useState(false)
  const [hidden, setHidden] = useState(false)
  const conf = face.confidence ? Math.round(face.confidence * 100) : null
  const age = face.age || face.estimated_age
  const gender = face.gender || face.dominant_gender
  const emotion = face.dominant_emotion || face.emotion
  const race = face.dominant_race || face.race

  const confColor = conf >= 80 ? 'var(--green)' : conf >= 50 ? 'var(--orange)' : 'var(--red)'

  if (hidden) return null

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: 'var(--surface-3)',
        border: '1px solid var(--border)',
        borderTop: `3px solid ${confColor}`,
      }}
    >
      {/* Face crop */}
      <div className="w-full aspect-square overflow-hidden" style={{ background: 'var(--surface-4)' }}>
        {face.crop_b64 ? (
          <img
            src={`data:image/jpeg;base64,${face.crop_b64}`}
            alt={`Face ${index + 1}`}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <UserCircle2 size={40} style={{ color: 'var(--surface-5)' }} />
          </div>
        )}
      </div>

      <div className="p-3 space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold">Face #{index + 1}</p>
          {conf !== null && (
            <span className="text-xs mono font-semibold" style={{ color: confColor }}>{conf}%</span>
          )}
        </div>

        {conf !== null && (
          <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface-4)' }}>
            <div className="h-1 rounded-full" style={{ width: `${conf}%`, background: confColor, transition: 'width 0.5s' }} />
          </div>
        )}

        <div className="flex flex-wrap gap-1">
          {age && <AttributeTag label={`~${Math.round(age)}y`} color="blue" />}
          {gender && <AttributeTag label={gender} />}
          {emotion && <AttributeTag label={emotion} color="orange" />}
          {race && <AttributeTag label={race} color="purple" />}
        </div>

        {/* Quick actions */}
        <div className="flex gap-1">
          <button
            onClick={() => { onSave?.(face, index) }}
            className="flex-1 flex items-center justify-center gap-1 text-[11px] py-1 rounded-lg transition-colors"
            style={{ background: 'var(--surface-4)', color: 'var(--text-secondary)' }}
            title="Save to Face Database"
          >
            <BookmarkPlus size={10} /> Save
          </button>
          <button
            onClick={() => setHidden(true)}
            className="flex items-center justify-center gap-1 text-[11px] py-1 px-2 rounded-lg transition-colors"
            style={{ background: 'var(--surface-4)', color: 'var(--text-tertiary)' }}
            title="Hide this face"
          >
            <EyeOff size={10} />
          </button>
        </div>

        <button
          onClick={() => setExpanded(v => !v)}
          className="w-full flex items-center justify-center gap-1 text-[11px] py-1 rounded-lg transition-colors"
          style={{ color: 'var(--text-tertiary)' }}
        >
          {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
          {expanded ? 'Hide links' : 'External search'}
        </button>

        {expanded && (
          <div className="space-y-1.5 pt-1">
            {[
              { href: 'https://pimeyes.com/en', label: 'PimEyes' },
              { href: 'https://facecheck.id',   label: 'FaceCheck.ID' },
              { href: 'https://www.google.com/search?tbm=isch&q=reverse+face+search', label: 'Google Images' },
            ].map(({ href, label }) => (
              <a
                key={label}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs transition-colors"
                style={{ color: 'var(--blue)' }}
              >
                <ExternalLink size={10} /> {label}
                <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>(upload manually)</span>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function LocalDBMatches({ searchId }) {
  const [matches, setMatches] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!searchId) { setLoading(false); return }
    api.get(`/api/faces/search/${searchId}`)
      .then(r => setMatches(r.data))
      .catch(() => setMatches(null))
      .finally(() => setLoading(false))
  }, [searchId])

  if (loading) return (
    <div className="h-16 rounded-xl skeleton" />
  )

  if (!matches?.results?.length) {
    return (
      <div
        className="p-4 rounded-xl flex items-center gap-3"
        style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
      >
        <Database size={16} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
        <div>
          <p className="text-sm font-medium">No matches in local database</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            <Link to="/faces" style={{ color: 'var(--blue)' }}>Add people to your Face Database</Link>
            {' '}to enable local face search
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
        {matches.results.map((match, i) => (
        <div
          key={i}
          className="flex items-center gap-3 p-3 rounded-xl"
          style={{ background: 'var(--surface-3)', border: '1px solid var(--border)' }}
        >
          {match.thumbnail ? (
            <img src={match.thumbnail} alt={match.label} className="w-10 h-10 rounded-lg object-cover flex-shrink-0" />
          ) : (
            <div className="w-10 h-10 rounded-lg flex-shrink-0 flex items-center justify-center" style={{ background: 'var(--surface-4)' }}>
              <UserCircle2 size={20} style={{ color: 'var(--text-tertiary)' }} />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold">{match.label || 'Unknown'}</p>
            <div className="flex items-center gap-2 mt-1">
              <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface-4)' }}>
                <div
                  className="h-1 rounded-full"
                  style={{
                    width: `${match.similarity}%`,
                    background: confidenceLabel(match.similarity).color,
                    transition: 'width 0.5s',
                  }}
                />
              </div>
              <span className="text-xs mono font-semibold flex-shrink-0" style={{ color: 'var(--text-secondary)' }}>
                {match.similarity}%
              </span>
            </div>
            <p className="text-[10px] mt-0.5" style={{ color: confidenceLabel(match.similarity).color }}>
              {confidenceLabel(match.similarity).text}
            </p>
            {(match.source_url || match.page_url) && (
              <p className="text-[10px] mt-1 truncate" style={{ color: 'var(--text-tertiary)' }}>
                {match.page_url || match.source_url}
              </p>
            )}
          </div>
          <Link
            to="/faces"
            className="text-xs flex-shrink-0"
            style={{ color: 'var(--blue)' }}
          >
            View →
          </Link>
        </div>
      ))}
    </div>
  )
}

function ExternalFaceResults({ results }) {
  const faceSearch = results?.['Face Search (PimEyes/FaceCheck)']
  if (!faceSearch?.per_face?.[0]?.aggregated_matches?.length) return null

  const allMatches = faceSearch.per_face[0].aggregated_matches

  return (
    <div className="space-y-3">
      {/* OPSEC notice */}
      <div
        className="p-4 rounded-xl flex items-start gap-3"
        style={{ background: 'rgba(255,159,10,0.08)', border: '1px solid rgba(255,159,10,0.25)' }}
      >
        <AlertTriangle size={15} style={{ color: 'var(--orange)', flexShrink: 0, marginTop: 1 }} />
        <div>
          <p className="text-xs font-semibold" style={{ color: 'var(--orange)' }}>External Face Search</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            These results were obtained by submitting biometric face data to third-party services (PimEyes, FaceCheck.ID, Yandex). Review their privacy policies before use.
          </p>
        </div>
      </div>

      {allMatches.map((r, i) => (
        <div
          key={i}
          className="flex items-center gap-3 p-3 rounded-xl"
          style={{ background: 'var(--surface-3)', border: '1px solid var(--border)' }}
        >
          <span className="text-xs mono font-semibold w-5 text-center flex-shrink-0" style={{ color: 'var(--text-tertiary)' }}>{i + 1}</span>
          {r.thumbnail && (
            <img src={r.thumbnail} alt="" className="w-10 h-10 rounded-lg object-cover flex-shrink-0"
              onError={e => e.target.style.display = 'none'} />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm truncate">{r.domain || r.url || 'Unknown source'}</p>
            {r.similarity && (() => {
              const simPct = typeof r.similarity === 'number'
                ? (r.similarity <= 1 ? Math.round(r.similarity * 100) : Math.round(r.similarity))
                : null
              const cl = simPct !== null ? confidenceLabel(simPct) : null
              return (
                <p className="text-xs mt-0.5" style={{ color: cl?.color || 'var(--text-secondary)' }}>
                  {cl ? `${cl.text} (${simPct}%)` : r.similarity}
                </p>
              )
            })()}
            <span
              className="text-[11px] font-medium px-1.5 py-0.5 rounded-md"
              style={{ background: 'var(--surface-4)', color: 'var(--text-secondary)' }}
            >
              {r.engine}
            </span>
            {r.title && (
              <p className="text-[10px] mt-1 truncate" style={{ color: 'var(--text-tertiary)' }}>
                {r.title}
              </p>
            )}
          </div>
          {r.url && r.url !== 'blurred (free tier)' && r.url !== 'requires account' && (
            <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--blue)', flexShrink: 0 }}>
              <ExternalLink size={14} />
            </a>
          )}
        </div>
      ))}
    </div>
  )
}

export function FaceGallery({ results, searchId }) {
  const [savedFaces, setSavedFaces] = useState(new Set())
  const content = results?.['Face & Object Detection'] || results?.['AI Analysis (CLIP/DeepFace)'] || {}
  const faces = content.faces || content.detected_faces || []

  const handleSaveFace = async (face, index) => {
    if (!face.crop_b64 || savedFaces.has(index)) return
    try {
      const blob = await fetch(`data:image/jpeg;base64,${face.crop_b64}`).then(r => r.blob())
      const form = new FormData()
      form.append('file', blob, `face_${index}.jpg`)
      form.append('label', '')
      await api.post('/api/faces/index-upload', form)
      setSavedFaces(s => new Set([...s, index]))
    } catch { /* silent fail — user sees no change */ }
  }

  if (!faces.length) {
    return (
      <div className="text-center py-16">
        <div
          className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center"
          style={{ background: 'var(--surface-3)' }}
        >
          <UserCircle2 size={28} style={{ color: 'var(--surface-5)' }} />
        </div>
        <p className="text-sm font-medium">No faces detected</p>
        <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
          No human faces were found in this image
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Detected faces */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>
          {faces.length} Face{faces.length !== 1 ? 's' : ''} Detected
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {faces.map((face, i) => (
            <FaceCard
              key={i}
              face={face}
              index={i}
              onSave={handleSaveFace}
              saved={savedFaces.has(i)}
            />
          ))}
        </div>
      </div>

      {/* Local DB section */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Database size={13} style={{ color: 'var(--text-tertiary)' }} />
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
            Local Database
          </p>
        </div>
        <LocalDBMatches searchId={searchId} />
      </div>

      {/* External results */}
      <ExternalFaceResults results={results} />
    </div>
  )
}
