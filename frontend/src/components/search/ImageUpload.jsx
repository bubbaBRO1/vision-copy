import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, Image, Link, ArrowRight } from 'lucide-react'
import { useSearch } from '../../hooks/useSearch'
import { useSearchStore } from '../../store/searchStore'
import api from '../../utils/api'
import toast from 'react-hot-toast'

export function ImageUpload() {
  const { uploadImage } = useSearch()
  const { startSearch } = useSearchStore()
  const [urlMode, setUrlMode] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const [loading, setLoading] = useState(false)

  const onDrop = useCallback(async (files) => {
    if (!files.length) return
    setLoading(true)
    try { await uploadImage(files[0]) }
    catch (e) { toast.error(e.response?.data?.detail || 'Upload failed') }
    finally { setLoading(false) }
  }, [uploadImage])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.tiff', '.bmp'] },
    maxSize: 50 * 1024 * 1024,
    multiple: false,
    disabled: loading,
  })

  const handlePaste = useCallback(async (e) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) {
          setLoading(true)
          try { await uploadImage(file) }
          catch { toast.error('Upload failed') }
          finally { setLoading(false) }
        }
      }
    }
  }, [uploadImage])

  const handleUrlSubmit = async () => {
    if (!urlInput) return
    setLoading(true)
    try {
      const { data } = await api.post('/api/search/url', { url: urlInput })
      startSearch(data.search_id, data.filename || urlInput)
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to analyze URL')
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-3" onPaste={handlePaste}>
      {/* Mode toggle */}
      <div
        className="flex rounded-lg p-1 gap-1"
        style={{ background: 'var(--surface-3)', border: '1px solid var(--border)' }}
      >
        {[
          { id: false, icon: Image, label: 'File' },
          { id: true,  icon: Link,  label: 'URL' },
        ].map(({ id, icon: Icon, label }) => (
          <button
            key={String(id)}
            onClick={() => setUrlMode(id)}
            className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-medium transition-all duration-150"
            style={{
              background: urlMode === id ? 'var(--surface-4)' : 'transparent',
              color: urlMode === id ? 'var(--text-primary)' : 'var(--text-secondary)',
              boxShadow: urlMode === id ? 'var(--shadow-sm)' : 'none',
            }}
          >
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {!urlMode ? (
          <motion.div
            key="drop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            {...getRootProps()}
            className={`relative border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all duration-200 ${loading ? 'pointer-events-none opacity-50' : ''}`}
            style={{
              borderColor: isDragActive ? 'var(--blue)' : 'var(--border)',
              background: isDragActive ? 'rgba(10,132,255,0.06)' : 'var(--surface-3)',
            }}
          >
            {/* Indeterminate loader bar */}
            {loading && (
              <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t-xl overflow-hidden">
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: 'var(--blue)', width: '40%' }}
                  animate={{ x: ['0%', '200%'] }}
                  transition={{ repeat: Infinity, duration: 1.2, ease: 'easeInOut' }}
                />
              </div>
            )}
            <input {...getInputProps()} />
            <div className="flex flex-col items-center gap-4">
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center"
                style={{ background: isDragActive ? 'rgba(10,132,255,0.15)' : 'var(--surface-4)' }}
              >
                <Upload size={24} style={{ color: isDragActive ? 'var(--blue)' : 'var(--text-secondary)' }} />
              </div>
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {loading ? 'Uploading…' : isDragActive ? 'Drop to analyze' : 'Drop image or click to upload'}
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                  JPG, PNG, WebP, GIF, TIFF — up to 50MB
                </p>
                <p className="text-xs mt-1.5" style={{ color: 'var(--text-tertiary)' }}>
                  or{' '}
                  <kbd
                    className="px-1.5 py-0.5 rounded-md text-[11px] mono"
                    style={{ background: 'var(--surface-4)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                  >
                    Ctrl+V
                  </kbd>{' '}
                  to paste
                </p>
              </div>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="url"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="relative"
          >
            <div
              className="flex items-center rounded-xl overflow-hidden"
              style={{ background: 'var(--surface-3)', border: '1px solid var(--border)' }}
            >
              <input
                className="flex-1 bg-transparent outline-none px-4 py-3.5 text-sm"
                style={{ color: 'var(--text-primary)', fontFamily: 'Inter, sans-serif' }}
                placeholder="https://example.com/image.jpg"
                value={urlInput}
                onChange={e => setUrlInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleUrlSubmit()}
                autoFocus
              />
              <button
                onClick={handleUrlSubmit}
                disabled={!urlInput || loading}
                className="flex items-center gap-1.5 px-4 py-3.5 text-sm font-medium transition-colors"
                style={{ color: urlInput ? 'var(--blue)' : 'var(--text-tertiary)' }}
              >
                {loading ? '…' : <><span>Analyze</span><ArrowRight size={14} /></>}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
