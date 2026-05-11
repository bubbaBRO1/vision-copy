import { useState } from 'react'
import { motion } from 'framer-motion'
import { ExternalLink, ChevronDown, ChevronUp, Hash, Clock, Globe } from 'lucide-react'
import { ConfidenceGauge } from '../ui/ConfidenceGauge'
import { truncate } from '../../utils/formatters'

const ENGINE_CONFIG = {
  GoogleLensScraper: { label: 'Google Lens', color: 'var(--blue)',   bg: 'rgba(10,132,255,0.12)' },
  YandexScraper:     { label: 'Yandex',      color: 'var(--red)',    bg: 'rgba(255,69,58,0.12)' },
  TinEyeScraper:     { label: 'TinEye',      color: 'var(--orange)', bg: 'rgba(255,159,10,0.12)' },
  SauceNAOScraper:   { label: 'SauceNAO',    color: 'var(--purple)', bg: 'rgba(191,90,242,0.12)' },
  BingVisualScraper: { label: 'Bing Visual', color: 'var(--teal)',   bg: 'rgba(64,203,224,0.12)' },
  IQDBScraper:       { label: 'IQDB',        color: 'var(--indigo)', bg: 'rgba(94,92,230,0.12)' },
}

function rankReason(result) {
  const reasons = []
  if (result.similarity_pct >= 80) reasons.push('High visual similarity')
  else if (result.similarity_pct >= 50) reasons.push('Moderate visual similarity')
  if (result.engine === 'TinEyeScraper') reasons.push('TinEye exact-match index')
  if (result.earliest_crawl) reasons.push('Has timestamp data')
  if (result.title && result.title.length > 10) reasons.push('Descriptive title')
  if (result.page_context) reasons.push('Has page context')
  if (result.image_hash) reasons.push('Image hash matched')
  return reasons.length ? reasons.join(' · ') : 'Ranked by source reliability'
}

export function ResultCard({ result, index }) {
  const [expanded, setExpanded] = useState(false)
  const similarity = result.similarity_pct ? Math.round(result.similarity_pct) : null
  const engine = ENGINE_CONFIG[result.engine] || { label: result.engine || 'Unknown', color: 'var(--text-secondary)', bg: 'var(--surface-4)' }
  const domain = result.source_domain || (result.url ? (() => { try { return new URL(result.url).hostname.replace('www.', '') } catch { return '' } })() : '')
  const initial = domain?.[0]?.toUpperCase() || '?'

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.04, 0.3) }}
      className="rounded-xl overflow-hidden"
      style={{ background: 'var(--surface-3)', border: '1px solid var(--border)' }}
    >
      {/* Main row */}
      <div className="flex gap-3 p-3.5 group">
        {/* Thumbnail */}
        <div
          className="w-[72px] h-[72px] rounded-lg flex-shrink-0 flex items-center justify-center overflow-hidden"
          style={{ background: 'var(--surface-4)' }}
        >
          {result.thumbnail ? (
            <img
              src={result.thumbnail}
              alt={result.title || 'Result'}
              className="w-full h-full object-cover"
              onError={e => { e.target.style.display = 'none' }}
            />
          ) : (
            <span className="text-lg font-semibold" style={{ color: 'var(--text-tertiary)' }}>{initial}</span>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <a
            href={result.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium flex items-start gap-1 group-hover:underline"
            style={{ color: 'var(--blue)', textDecorationSkipInk: 'auto' }}
          >
            <span style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
              {result.title || result.url}
            </span>
            <ExternalLink size={11} style={{ flexShrink: 0, marginTop: 2, opacity: 0.6 }} />
          </a>

          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{domain}</span>
            <span className="text-[11px] font-medium px-1.5 py-0.5 rounded-md" style={{ background: engine.bg, color: engine.color }}>
              {engine.label}
            </span>
            {result.earliest_crawl && (
              <span className="text-[11px] flex items-center gap-0.5" style={{ color: 'var(--text-tertiary)' }}>
                <Clock size={9} /> {result.earliest_crawl}
              </span>
            )}
          </div>

          {result.page_context && (
            <p className="text-xs mt-1.5 line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
              {truncate(result.page_context, 100)}
            </p>
          )}
        </div>

        <div className="flex-shrink-0 flex flex-col items-center justify-between">
          {similarity !== null && <ConfidenceGauge score={similarity} size={52} label={false} />}
          <button
            onClick={() => setExpanded(v => !v)}
            className="mt-1 p-1 rounded transition-colors"
            style={{ color: 'var(--text-tertiary)' }}
            title="Evidence details"
          >
            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>
      </div>

      {/* Inspector panel */}
      {expanded && (
        <div
          className="px-4 pb-3 pt-1 space-y-2 border-t"
          style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}
        >
          <p className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Evidence Inspector</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
            {result.url && (
              <Row icon={Globe} label="Source URL" value={result.url} href={result.url} />
            )}
            {result.image_hash && (
              <Row icon={Hash} label="Image Hash" value={result.image_hash} mono />
            )}
            {result.earliest_crawl && (
              <Row icon={Clock} label="First Seen" value={result.earliest_crawl} />
            )}
            {similarity !== null && (
              <Row icon={null} label="Similarity" value={`${similarity}%`} />
            )}
            {result.engine && (
              <Row icon={null} label="Source Engine" value={engine.label} />
            )}
          </div>
          <div className="pt-1 border-t" style={{ borderColor: 'var(--border)' }}>
            <p className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
              <span style={{ color: 'var(--text-tertiary)' }}>Why ranked: </span>
              {rankReason(result)}
            </p>
          </div>
        </div>
      )}
    </motion.div>
  )
}

function Row({ icon: Icon, label, value, href, mono }) {
  return (
    <div className="flex items-start gap-1.5">
      {Icon && <Icon size={10} style={{ color: 'var(--text-tertiary)', marginTop: 2, flexShrink: 0 }} />}
      <span className="text-[11px] flex-shrink-0" style={{ color: 'var(--text-tertiary)', minWidth: 80 }}>{label}:</span>
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer"
          className="text-[11px] truncate" style={{ color: 'var(--blue)' }}>
          {value}
        </a>
      ) : (
        <span className={`text-[11px] truncate ${mono ? 'font-mono' : ''}`} style={{ color: 'var(--text-primary)' }}>
          {value}
        </span>
      )}
    </div>
  )
}
