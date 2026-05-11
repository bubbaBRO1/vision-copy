import { useState } from 'react'
import { Camera, AlertTriangle, Archive, Lock, Globe, Clock } from 'lucide-react'

function parseTimestamp(val) {
  if (!val) return null
  const d = new Date(val)
  return isNaN(d.getTime()) ? null : d
}

function formatDate(d) {
  if (!d) return '?'
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

function collectEvents(results) {
  const events = []

  // EXIF / metadata timestamps
  const meta = results?.['EXIF & Metadata'] || {}
  const exifFields = ['DateTimeOriginal', 'DateTime', 'DateTimeDigitized', 'CreateDate', 'ModifyDate']
  for (const field of exifFields) {
    const val = meta[field] || meta?.exif?.[field]
    if (val) {
      events.push({
        date: parseTimestamp(val),
        label: `EXIF: ${field}`,
        detail: String(val),
        icon: Camera,
        color: 'text-accent',
        source: 'Metadata',
      })
    }
  }

  // GPS timestamp
  const gps = meta?.gps
  if (gps?.GPSDateStamp) {
    events.push({
      date: parseTimestamp(gps.GPSDateStamp),
      label: 'GPS Timestamp',
      detail: `${gps.GPSDateStamp} ${gps.GPSTimeStamp || ''}`,
      icon: Globe,
      color: 'text-blue-400',
      source: 'Geolocation',
    })
  }

  // Breach dates
  const leaks = results?.['Leaked Credentials'] || {}
  for (const emailData of leaks?.emails_checked || []) {
    for (const breach of emailData?.breaches || []) {
      if (breach.breach_date && !breach.error) {
        events.push({
          date: parseTimestamp(breach.breach_date),
          label: `Breach: ${breach.name}`,
          detail: `${emailData.email} — ${(breach.data_classes || []).slice(0, 3).join(', ')}`,
          icon: AlertTriangle,
          color: 'text-red-400',
          source: 'HaveIBeenPwned',
        })
      }
    }
  }

  // Archive dates
  const archive = results?.['Web Archiving'] || {}
  for (const item of [...(archive?.archived || []), ...(archive?.already_archived || [])]) {
    if (item.archived) {
      // Extract date from Wayback URL: /web/20230101120000/
      const match = item.archived.match(/\/web\/(\d{4})(\d{2})(\d{2})/)
      if (match) {
        events.push({
          date: new Date(`${match[1]}-${match[2]}-${match[3]}`),
          label: 'Web Archive',
          detail: item.url || item.archived,
          icon: Archive,
          color: 'text-purple-400',
          source: 'Wayback Machine',
        })
      }
    }
  }

  // Blockchain first/last tx
  const blockchain = results?.['Blockchain Detection'] || {}
  for (const wallet of blockchain?.wallets || []) {
    if (wallet.first_tx) {
      events.push({
        date: parseTimestamp(wallet.first_tx),
        label: `First TX: ${wallet.chain}`,
        detail: wallet.address,
        icon: Lock,
        color: 'text-yellow-400',
        source: 'Blockchain',
      })
    }
  }

  // Sort by date (nulls last)
  return events.sort((a, b) => {
    if (!a.date && !b.date) return 0
    if (!a.date) return 1
    if (!b.date) return -1
    return a.date - b.date
  })
}

export function Timeline({ results }) {
  const [expanded, setExpanded] = useState({})
  const events = collectEvents(results)

  if (!events.length) {
    return (
      <div className="text-center py-10 text-text-secondary">
        <Clock size={32} className="mx-auto mb-2 opacity-40" />
        <p>No timestamps found in analysis results.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-text-secondary mb-4">{events.length} temporal event{events.length !== 1 ? 's' : ''} found</p>
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-5 top-0 bottom-0 w-px bg-border-color" />

        <div className="space-y-4">
          {events.map((ev, i) => {
            const Icon = ev.icon
            const isOpen = expanded[i]
            return (
              <div key={i} className="flex gap-4 relative">
                {/* Icon node */}
                <div className={`w-10 h-10 rounded-full bg-surface-2 border border-border-color flex items-center justify-center shrink-0 z-10 ${ev.color}`}>
                  <Icon size={16} />
                </div>

                {/* Content */}
                <div
                  className="flex-1 bg-surface-2 border border-border-color rounded-lg p-3 cursor-pointer hover:border-accent/40 transition-colors"
                  onClick={() => setExpanded(s => ({ ...s, [i]: !s[i] }))}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium">{ev.label}</p>
                      <p className="text-xs text-text-secondary">{formatDate(ev.date)} · {ev.source}</p>
                    </div>
                    <span className="text-xs text-text-secondary shrink-0">{isOpen ? '▲' : '▼'}</span>
                  </div>
                  {isOpen && (
                    <p className="text-xs text-text-secondary mt-2 font-mono break-all">{ev.detail}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
