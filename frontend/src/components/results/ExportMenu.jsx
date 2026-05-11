import { useState, useRef } from 'react'
import { Download, FileJson, FileText, File, Globe, ChevronDown } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import toast from 'react-hot-toast'

const FORMATS = [
  { key: 'json', label: 'JSON (raw)', icon: FileJson, mime: 'application/json' },
  { key: 'md', label: 'Markdown report', icon: FileText, mime: 'text/markdown' },
  { key: 'pdf', label: 'PDF', icon: File, mime: 'application/pdf' },
  { key: 'html', label: 'HTML archive', icon: Globe, mime: 'text/html' },
]

export function ExportMenu({ searchId, filename }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(null)
  const menuRef = useRef(null)
  const token = useAuthStore(s => s.accessToken)

  async function doExport(format) {
    setLoading(format.key)
    setOpen(false)
    try {
      const res = await fetch(`/api/search/${searchId}/export?format=${format.key}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Export failed (${res.status})`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const baseName = filename?.replace(/\.[^.]+$/, '') || 'vision-report'
      const ext = format.key === 'md' ? 'md' : format.key
      a.href = url
      a.download = `${baseName}-report.${ext}`
      a.click()
      URL.revokeObjectURL(url)
      toast.success(`Exported as ${format.label}`)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded border border-border-color hover:border-accent/60 transition-colors"
      >
        <Download size={14} />
        Export
        <ChevronDown size={12} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 bg-surface-2 border border-border-color rounded-lg shadow-xl z-50 w-44 py-1">
          {FORMATS.map(fmt => {
            const Icon = fmt.icon
            return (
              <button
                key={fmt.key}
                onClick={() => doExport(fmt)}
                disabled={loading === fmt.key}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-surface-3 transition-colors disabled:opacity-50"
              >
                <Icon size={14} className="text-text-secondary" />
                {loading === fmt.key ? 'Exporting…' : fmt.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
