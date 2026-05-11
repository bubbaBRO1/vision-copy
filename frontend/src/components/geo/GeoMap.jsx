import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'

const TILES = {
  dark: {
    url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
    attr: '© Stadia Maps © OpenMapTiles © OpenStreetMap',
  },
  street: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attr: '© OpenStreetMap contributors',
  },
}

export function GeoMap({ primary, alternates = [] }) {
  const mapRef = useRef(null)
  const instanceRef = useRef(null)
  const tileRef = useRef(null)
  const [tileMode, setTileMode] = useState('dark')

  useEffect(() => {
    if (!primary?.lat || !primary?.lon || typeof window === 'undefined' || !L) return
    if (instanceRef.current) instanceRef.current.remove()

    const map = L.map(mapRef.current, { zoomControl: false }).setView([primary.lat, primary.lon], 13)
    L.control.zoom({ position: 'bottomright' }).addTo(map)
    instanceRef.current = map

    tileRef.current = L.tileLayer(TILES[tileMode].url, { attribution: TILES[tileMode].attr }).addTo(map)

    // Primary pin — blue SVG teardrop
    const bluePin = L.divIcon({
      html: `<svg width="24" height="32" viewBox="0 0 24 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 0C5.373 0 0 5.373 0 12c0 8.314 10.5 20 12 20s12-11.686 12-20C24 5.373 18.627 0 12 0z" fill="#0A84FF"/>
        <circle cx="12" cy="12" r="5" fill="white"/>
      </svg>`,
      iconSize: [24, 32],
      iconAnchor: [12, 32],
      popupAnchor: [0, -34],
    })

    L.marker([primary.lat, primary.lon], { icon: bluePin })
      .addTo(map)
      .bindPopup(`<b style="color:#000">Primary Location</b><br><span style="color:#555">${primary.address || ''}</span><br><span style="color:#555">Confidence: ${primary.confidence || 0}%</span>`)
      .openPopup()

    if (primary.confidence) {
      const radius = Math.max(100, (100 - primary.confidence) * 500)
      L.circle([primary.lat, primary.lon], {
        radius,
        color: '#0A84FF',
        fillColor: '#0A84FF',
        fillOpacity: 0.05,
        weight: 1,
      }).addTo(map)
    }

    alternates.forEach((alt, i) => {
      if (!alt.lat || !alt.lon) return
      const color = i === 0 ? '#FF9F0A' : '#FFD60A'
      const altPin = L.divIcon({
        html: `<div style="width:12px;height:12px;background:${color};border-radius:50%;border:2px solid rgba(0,0,0,0.3);box-shadow:0 2px 4px rgba(0,0,0,0.3)"></div>`,
        iconSize: [12, 12],
        iconAnchor: [6, 6],
      })
      L.marker([alt.lat, alt.lon], { icon: altPin })
        .addTo(map)
        .bindPopup(`<b style="color:#000">Alternate ${i + 1}</b><br><span style="color:#555">${alt.address || ''}</span>`)
    })

    return () => { map.remove(); instanceRef.current = null }
  }, [primary, alternates])

  // Swap tile layer without re-creating the map
  useEffect(() => {
    const map = instanceRef.current
    if (!map || !tileRef.current) return
    map.removeLayer(tileRef.current)
    tileRef.current = L.tileLayer(TILES[tileMode].url, { attribution: TILES[tileMode].attr }).addTo(map)
  }, [tileMode])

  return (
    <div className="relative rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)', height: 380 }}>
      <div ref={mapRef} style={{ height: '100%' }} />

      {/* Tile toggle */}
      <div
        className="absolute top-3 right-3 z-[1000] flex rounded-lg overflow-hidden"
        style={{
          background: 'var(--glass-bg)',
          backdropFilter: 'blur(12px)',
          border: '1px solid var(--glass-border)',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        {(['dark', 'street'] ).map(mode => (
          <button
            key={mode}
            onClick={() => setTileMode(mode)}
            className="px-3 py-1.5 text-xs font-medium transition-colors capitalize"
            style={{
              background: tileMode === mode ? 'var(--surface-4)' : 'transparent',
              color: tileMode === mode ? 'var(--text-primary)' : 'var(--text-secondary)',
            }}
          >
            {mode}
          </button>
        ))}
      </div>
    </div>
  )
}
