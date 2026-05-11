import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Eye, Scan, MapPin, Brain, Shield, Zap, Users, Github, ChevronRight, Check } from 'lucide-react'
import api from '../utils/api'
import toast from 'react-hot-toast'

const FEATURES = [
  {
    icon: Scan,
    label: 'Reverse Image Search',
    desc: '10+ engines: Google Lens, Yandex, TinEye, SauceNAO, Bing Visual, and more',
    color: 'var(--blue)',
    bg: 'rgba(10,132,255,0.12)',
  },
  {
    icon: MapPin,
    label: 'Geolocation Engine',
    desc: 'GPS EXIF, CLIP embeddings, sun angle analysis, and landmark detection',
    color: 'var(--green)',
    bg: 'rgba(48,209,88,0.12)',
  },
  {
    icon: Shield,
    label: 'Image Forensics',
    desc: 'Error Level Analysis, deepfake detection, steganography, clone detection',
    color: 'var(--orange)',
    bg: 'rgba(255,159,10,0.12)',
  },
  {
    icon: Brain,
    label: 'AI Assistant',
    desc: 'Local LLM via Ollama with 35+ OSINT slash commands and Claude support',
    color: 'var(--indigo)',
    bg: 'rgba(94,92,230,0.12)',
  },
  {
    icon: Shield,
    label: 'Deep Research',
    desc: 'Multi-source pipeline: Wikipedia, arXiv, Reddit, HackerNews, and web',
    color: 'var(--teal)',
    bg: 'rgba(64,203,224,0.12)',
  },
  {
    icon: Users,
    label: 'DIY Face Database',
    desc: 'Build a local face index and search any image against it — free PimEyes alternative',
    color: 'var(--purple)',
    bg: 'rgba(191,90,242,0.12)',
  },
]

const STEPS = [
  { n: '01', title: 'Upload an Image', desc: 'Drop, paste, or link any image. JPEG, PNG, WebP, GIF up to 50MB.' },
  { n: '02', title: '17 Stages Run', desc: 'Reverse search, geolocation, forensics, face detection, AI analysis — all in parallel.' },
  { n: '03', title: 'Review the Report', desc: 'Intel score, matched sources, map, face gallery, and export to PDF or JSON.' },
]

const TRUST = [
  'Free & open-source',
  'Self-hostable',
  'No data retention',
  '17-stage analysis pipeline',
  'Local AI via Ollama',
  'Local face database',
]

/* Simulated browser frame showing the search UI */
function ProductFrame() {
  return (
    <div
      className="rounded-xl overflow-hidden shadow-xl select-none"
      style={{
        border: '1px solid var(--glass-border)',
        background: 'var(--surface-2)',
        boxShadow: '0 40px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.05)',
      }}
    >
      {/* Chrome bar */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b"
        style={{ background: 'var(--surface-3)', borderColor: 'var(--border)' }}
      >
        <div className="flex gap-1.5">
          {['var(--red)', 'var(--orange)', 'var(--green)'].map((c, i) => (
            <div key={i} className="w-3 h-3 rounded-full" style={{ background: 'var(--surface-4)' }} />
          ))}
        </div>
        <div
          className="flex-1 mx-3 px-3 py-1 rounded-md text-xs"
          style={{ background: 'var(--surface-2)', color: 'var(--text-tertiary)' }}
        >
          vision.local/search
        </div>
      </div>

      {/* App content simulation */}
      <div className="flex" style={{ height: 280 }}>
        {/* Fake sidebar */}
        <div className="w-40 border-r p-3 space-y-1 flex-shrink-0" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
          {['Dashboard', 'Search', 'Research', 'Face Database', 'History'].map((item, i) => (
            <div
              key={item}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs"
              style={{
                background: i === 1 ? 'rgba(10,132,255,0.15)' : 'transparent',
                color: i === 1 ? 'var(--blue)' : 'var(--text-secondary)',
              }}
            >
              <div className="w-3 h-3 rounded-sm" style={{ background: i === 1 ? 'var(--blue)' : 'var(--surface-4)' }} />
              {item}
            </div>
          ))}
        </div>

        {/* Fake main content */}
        <div className="flex-1 p-4 space-y-3" style={{ background: 'var(--surface-1)' }}>
          {/* Intel score */}
          <div className="flex items-center gap-3 p-3 rounded-lg border" style={{ background: 'var(--surface-3)', borderColor: 'var(--border)' }}>
            <div className="w-12 h-12 rounded-full border-4 flex items-center justify-center text-xs font-bold" style={{ borderColor: 'var(--green)', color: 'var(--green)' }}>82</div>
            <div>
              <div className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>Intel Score</div>
              <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>High confidence — 14 sources found</div>
            </div>
            <div className="ml-auto text-[10px] px-2 py-1 rounded-full font-medium" style={{ background: 'rgba(48,209,88,0.15)', color: 'var(--green)' }}>Complete</div>
          </div>

          {/* Fake result cards */}
          {[
            { domain: 'instagram.com', sim: 94, engine: 'Google Lens' },
            { domain: 'twitter.com',   sim: 87, engine: 'Yandex' },
            { domain: 'reddit.com',    sim: 71, engine: 'TinEye' },
          ].map((r, i) => (
            <div
              key={i}
              className="flex items-center gap-3 p-2.5 rounded-lg border"
              style={{ background: 'var(--surface-3)', borderColor: 'var(--border)' }}
            >
              <div className="w-10 h-10 rounded-md flex-shrink-0" style={{ background: 'var(--surface-4)' }} />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium truncate" style={{ color: 'var(--blue)' }}>{r.domain}</div>
                <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>{r.engine}</div>
              </div>
              <div className="text-xs font-semibold" style={{ color: r.sim > 90 ? 'var(--green)' : r.sim > 75 ? 'var(--blue)' : 'var(--orange)' }}>
                {r.sim}%
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function Landing() {
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [position, setPosition] = useState(null)
  const [referralCode, setReferralCode] = useState(null)
  const [loading, setLoading] = useState(false)
  const [count, setCount] = useState(null)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    api.get('/waitlist/count').then(r => setCount(r.data.count)).catch(() => {})
    const ref = new URLSearchParams(window.location.search).get('ref')
    if (ref) setReferralCode(ref)
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const handleJoin = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const { data } = await api.post('/waitlist/join', { email, name, referral_code: referralCode })
      setPosition(data.position)
      setReferralCode(data.referral_code)
      toast.success(data.message)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not join waitlist')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen" style={{ background: 'var(--surface-1)', color: 'var(--text-primary)' }}>
      {/* Navbar */}
      <nav
        className="sticky top-0 z-40 px-6 py-3.5 flex items-center justify-between transition-all duration-200"
        style={{
          background: scrolled ? 'var(--glass-bg)' : 'transparent',
          backdropFilter: scrolled ? 'blur(20px) saturate(180%)' : 'none',
          borderBottom: scrolled ? '1px solid var(--glass-border)' : '1px solid transparent',
        }}
      >
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-ios-blue flex items-center justify-center">
            <Eye size={15} className="text-white" />
          </div>
          <span className="font-semibold text-[16px] tracking-[-0.01em]">VISION</span>
        </div>
        <div className="flex items-center gap-2">
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors"
            style={{ color: 'var(--text-secondary)', background: 'var(--surface-3)', border: '1px solid var(--border)' }}
          >
            <Github size={14} /> GitHub
          </a>
          <Link to="/login" className="btn-ghost text-sm px-3 py-1.5">Login</Link>
          <Link to="/signup" className="btn-primary text-sm px-4 py-1.5">Get Access</Link>
        </div>
      </nav>

      {/* Hero */}
      <div className="max-w-5xl mx-auto px-6 pt-24 pb-16 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          {/* Badge */}
          <div
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium mb-8"
            style={{ background: 'rgba(10,132,255,0.12)', border: '1px solid rgba(10,132,255,0.25)', color: 'var(--blue)' }}
          >
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--green)' }} />
            Open-source · Self-hostable · 100% free
          </div>

          <h1
            className="font-bold leading-[1.1] tracking-[-0.03em] mb-6"
            style={{ fontSize: 'clamp(40px, 6vw, 64px)' }}
          >
            Open-Source{' '}
            <span style={{ color: 'var(--blue)' }}>OSINT</span>
            <br />
            Intelligence Platform
          </h1>

          <p className="text-lg max-w-2xl mx-auto leading-relaxed mb-8" style={{ color: 'var(--text-secondary)' }}>
            Reverse image search across 10+ engines, AI-powered geolocation, image forensics, a local face database, and an OSINT AI assistant. All free. All open-source.
          </p>

          {count !== null && (
            <p className="text-sm mb-8 mono" style={{ color: 'var(--text-tertiary)' }}>
              <span style={{ color: 'var(--blue)' }}>{count.toLocaleString()}</span> researchers on the waitlist
            </p>
          )}

          {/* CTA buttons */}
          <div className="flex items-center justify-center gap-3 mb-16">
            <a href="#join" className="btn-primary text-sm px-5 py-2.5 flex items-center gap-2">
              Request Access <ChevronRight size={14} />
            </a>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm px-5 py-2.5 rounded-lg font-medium transition-colors"
              style={{ background: 'var(--surface-3)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            >
              <Github size={15} /> View on GitHub
            </a>
          </div>

          {/* Trust pills */}
          <div className="flex flex-wrap justify-center gap-2 mb-16">
            {TRUST.map(t => (
              <span
                key={t}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full"
                style={{ background: 'var(--surface-3)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              >
                <Check size={11} style={{ color: 'var(--green)' }} /> {t}
              </span>
            ))}
          </div>
        </motion.div>

        {/* Product screenshot */}
        <motion.div
          initial={{ opacity: 0, y: 40, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          <ProductFrame />
        </motion.div>
      </div>

      {/* How it works */}
      <div className="max-w-4xl mx-auto px-6 py-20">
        <h2 className="text-[28px] font-bold tracking-tight text-center mb-3">How it works</h2>
        <p className="text-center mb-12" style={{ color: 'var(--text-secondary)' }}>
          Upload once. Get a complete intelligence report in minutes.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
          {STEPS.map(({ n, title, desc }, i) => (
            <motion.div
              key={n}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="card p-6 relative"
            >
              <div
                className="text-[11px] font-bold mono mb-4 w-8 h-8 rounded-full flex items-center justify-center"
                style={{ background: 'rgba(10,132,255,0.15)', color: 'var(--blue)', border: '1px solid rgba(10,132,255,0.3)' }}
              >
                {n}
              </div>
              <h3 className="font-semibold mb-2">{title}</h3>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{desc}</p>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Features grid */}
      <div className="max-w-5xl mx-auto px-6 pb-20">
        <h2 className="text-[28px] font-bold tracking-tight text-center mb-3">Everything you need</h2>
        <p className="text-center mb-12" style={{ color: 'var(--text-secondary)' }}>
          A complete OSINT toolkit in one platform.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map(({ icon: Icon, label, desc, color, bg }, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.07 }}
              className="card card-hover p-5"
            >
              <div
                className="w-10 h-10 rounded-[10px] flex items-center justify-center mb-4"
                style={{ background: bg }}
              >
                <Icon size={18} style={{ color }} />
              </div>
              <h3 className="font-semibold text-sm mb-1.5">{label}</h3>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{desc}</p>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Waitlist */}
      <div id="join" className="max-w-md mx-auto px-6 pb-24">
        <h2 className="text-[28px] font-bold tracking-tight text-center mb-3">Join the waitlist</h2>
        <p className="text-center mb-8 text-sm" style={{ color: 'var(--text-secondary)' }}>
          We review applications and send invites in batches.
        </p>

        {position ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="card p-8 text-center"
          >
            <div
              className="text-[56px] font-bold mono mb-2 leading-none"
              style={{ color: 'var(--green)' }}
            >
              #{position}
            </div>
            <p className="text-sm mb-1" style={{ color: 'var(--text-primary)' }}>You're on the waitlist</p>
            <p className="text-xs mb-6" style={{ color: 'var(--text-secondary)' }}>Share your link to move up:</p>
            <div
              className="p-3 rounded-lg text-xs mono break-all mb-3"
              style={{ background: 'var(--surface-2)', color: 'var(--blue)', border: '1px solid var(--border)' }}
            >
              {window.location.origin}/?ref={referralCode}
            </div>
            <button
              onClick={() => { navigator.clipboard.writeText(`${window.location.origin}/?ref=${referralCode}`); toast.success('Copied!') }}
              className="btn-secondary text-xs w-full"
            >
              Copy referral link
            </button>
          </motion.div>
        ) : (
          <motion.form
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            onSubmit={handleJoin}
            className="card p-6 space-y-3"
          >
            <input
              required
              className="input"
              placeholder="Your name"
              value={name}
              onChange={e => setName(e.target.value)}
            />
            <input
              required
              type="email"
              className="input"
              placeholder="Email address"
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
            <button type="submit" disabled={loading} className="btn-primary w-full py-3 text-sm">
              {loading ? 'Submitting…' : 'Request Access'}
            </button>
            <p className="text-xs text-center" style={{ color: 'var(--text-tertiary)' }}>
              No spam. Invite sent when approved.
            </p>
          </motion.form>
        )}
      </div>

      {/* Footer */}
      <div
        className="border-t px-6 py-8 flex items-center justify-between max-w-5xl mx-auto"
        style={{ borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-md bg-ios-blue flex items-center justify-center">
            <Eye size={11} className="text-white" />
          </div>
          <span className="text-sm font-semibold">VISION</span>
        </div>
        <div className="flex items-center gap-5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="hover:text-text-primary transition-colors">GitHub</a>
          <a href="#" className="hover:text-text-primary transition-colors">Docs</a>
          <a href="#" className="hover:text-text-primary transition-colors">Privacy</a>
        </div>
      </div>
    </div>
  )
}
