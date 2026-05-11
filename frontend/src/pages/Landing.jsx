import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Brain, Check, ChevronRight, Eye, Github, MapPin, Scan, Shield, Users } from 'lucide-react'

const FEATURES = [
  { icon: Scan, label: 'Reverse Image Search', desc: 'Cluster image matches, source pages, engine signals, and provenance in one review surface.', color: 'var(--blue)', bg: 'rgba(10,132,255,0.12)' },
  { icon: MapPin, label: 'Location Lab', desc: 'Compare EXIF, visual clues, OCR, source context, and confidence bands without overclaiming.', color: 'var(--green)', bg: 'rgba(48,209,88,0.12)' },
  { icon: Shield, label: 'Evidence Workspace', desc: 'Promote leads into case evidence with status, confidence, tags, notes, source URLs, and provenance.', color: 'var(--orange)', bg: 'rgba(255,159,10,0.12)' },
  { icon: Brain, label: 'AI Analyst Layer', desc: 'Generate summaries, next steps, contradiction scans, entity extraction, timelines, and report drafts.', color: 'var(--indigo)', bg: 'rgba(94,92,230,0.12)' },
  { icon: Users, label: 'Local Face Database', desc: 'Keep face workflows local/private and treat every match as a lead, not identity proof.', color: 'var(--purple)', bg: 'rgba(191,90,242,0.12)' },
  { icon: Eye, label: 'Browser Assist', desc: 'Visit approved URLs, capture artifacts, and extract emails, handles, domains, and location clues.', color: 'var(--teal)', bg: 'rgba(64,203,224,0.12)' },
]

const TRUST = [
  'Self-hosted',
  'Open registration',
  'Private by default',
  'Case-based workflow',
  'Provenance-first reports',
  'Local AI ready',
]

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
      <div className="flex items-center gap-2 px-4 py-3 border-b" style={{ background: 'var(--surface-3)', borderColor: 'var(--border)' }}>
        <div className="flex gap-1.5">
          {[0, 1, 2].map((i) => <div key={i} className="w-3 h-3 rounded-full" style={{ background: 'var(--surface-4)' }} />)}
        </div>
        <div className="flex-1 mx-3 px-3 py-1 rounded-md text-xs" style={{ background: 'var(--surface-2)', color: 'var(--text-tertiary)' }}>
          vision.local/search
        </div>
      </div>

      <div className="flex" style={{ height: 280 }}>
        <div className="w-40 border-r p-3 space-y-1 flex-shrink-0" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
          {['Dashboard', 'Search', 'Cases', 'Evidence', 'Reports'].map((item, i) => (
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

        <div className="flex-1 p-4 space-y-3" style={{ background: 'var(--surface-1)' }}>
          <div className="flex items-center gap-3 p-3 rounded-lg border" style={{ background: 'var(--surface-3)', borderColor: 'var(--border)' }}>
            <div className="w-12 h-12 rounded-full border-4 flex items-center justify-center text-xs font-bold" style={{ borderColor: 'var(--green)', color: 'var(--green)' }}>82</div>
            <div>
              <div className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>Intel Score</div>
              <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>High confidence - 14 sources found</div>
            </div>
            <div className="ml-auto text-[10px] px-2 py-1 rounded-full font-medium" style={{ background: 'rgba(48,209,88,0.15)', color: 'var(--green)' }}>Complete</div>
          </div>

          {[
            { domain: 'source-page.com', sim: 94, engine: 'Google Lens' },
            { domain: 'archive.org', sim: 87, engine: 'Browser Assist' },
            { domain: 'map context', sim: 71, engine: 'Location Lab' },
          ].map((result) => (
            <div key={result.domain} className="flex items-center gap-3 p-2.5 rounded-lg border" style={{ background: 'var(--surface-3)', borderColor: 'var(--border)' }}>
              <div className="w-10 h-10 rounded-md flex-shrink-0" style={{ background: 'var(--surface-4)' }} />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium truncate" style={{ color: 'var(--blue)' }}>{result.domain}</div>
                <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>{result.engine}</div>
              </div>
              <div className="text-xs font-semibold" style={{ color: result.sim > 90 ? 'var(--green)' : result.sim > 75 ? 'var(--blue)' : 'var(--orange)' }}>
                {result.sim}%
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function Landing() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="min-h-screen" style={{ background: 'var(--surface-1)', color: 'var(--text-primary)' }}>
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
          <a href="https://github.com/bubbaBRO1/vision-copy" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors" style={{ color: 'var(--text-secondary)', background: 'var(--surface-3)', border: '1px solid var(--border)' }}>
            <Github size={14} /> GitHub
          </a>
          <Link to="/login" className="btn-ghost text-sm px-3 py-1.5">Login</Link>
          <Link to="/signup" className="btn-primary text-sm px-4 py-1.5">Create Account</Link>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 pt-24 pb-16 text-center">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium mb-8" style={{ background: 'rgba(10,132,255,0.12)', border: '1px solid rgba(10,132,255,0.25)', color: 'var(--blue)' }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--green)' }} />
            Open-source - self-hostable - try it now
          </div>

          <h1 className="font-bold leading-[1.1] tracking-[-0.03em] mb-6" style={{ fontSize: 'clamp(40px, 6vw, 64px)' }}>
            Private <span style={{ color: 'var(--blue)' }}>OSINT</span>
            <br />
            Investigation Workstation
          </h1>

          <p className="text-lg max-w-2xl mx-auto leading-relaxed mb-8" style={{ color: 'var(--text-secondary)' }}>
            Create a case, upload an image, inspect clustered reverse-search leads, run Browser Assist, collect evidence, and export reports with provenance.
          </p>

          <div className="flex items-center justify-center gap-3 mb-16">
            <Link to="/signup" className="btn-primary text-sm px-5 py-2.5 flex items-center gap-2">
              Try VISION Now <ChevronRight size={14} />
            </Link>
            <Link to="/search" className="flex items-center gap-2 text-sm px-5 py-2.5 rounded-lg font-medium transition-colors" style={{ background: 'var(--surface-3)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}>
              Open Search
            </Link>
          </div>

          <div className="flex flex-wrap justify-center gap-2 mb-16">
            {TRUST.map((item) => (
              <span key={item} className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full" style={{ background: 'var(--surface-3)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                <Check size={11} style={{ color: 'var(--green)' }} /> {item}
              </span>
            ))}
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 40, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.6, delay: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}>
          <ProductFrame />
        </motion.div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-20">
        <h2 className="text-[28px] font-bold tracking-tight text-center mb-3">How it works</h2>
        <p className="text-center mb-12" style={{ color: 'var(--text-secondary)' }}>
          Upload once. Triage leads. Preserve proof. Export the case.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { n: '01', title: 'Create a Case', desc: 'Keep searches, notes, sources, entities, artifacts, and reports together.' },
            { n: '02', title: 'Analyze an Image', desc: 'Run reverse search, geolocation, forensics, face workflows, and AI summaries.' },
            { n: '03', title: 'Export Evidence', desc: 'Generate JSON, Markdown, HTML, and ZIP reports with source provenance.' },
          ].map((step, index) => (
            <motion.div key={step.n} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: index * 0.1 }} className="card p-6">
              <div className="text-[11px] font-bold mono mb-4 w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'rgba(10,132,255,0.15)', color: 'var(--blue)', border: '1px solid rgba(10,132,255,0.3)' }}>
                {step.n}
              </div>
              <h3 className="font-semibold mb-2">{step.title}</h3>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{step.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 pb-20">
        <h2 className="text-[28px] font-bold tracking-tight text-center mb-3">Everything you need</h2>
        <p className="text-center mb-12" style={{ color: 'var(--text-secondary)' }}>
          A private investigation workflow you can start using immediately.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map(({ icon: Icon, label, desc, color, bg }, index) => (
            <motion.div key={label} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: index * 0.07 }} className="card card-hover p-5">
              <div className="w-10 h-10 rounded-[10px] flex items-center justify-center mb-4" style={{ background: bg }}>
                <Icon size={18} style={{ color }} />
              </div>
              <h3 className="font-semibold text-sm mb-1.5">{label}</h3>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{desc}</p>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="max-w-md mx-auto px-6 pb-24 text-center">
        <h2 className="text-[28px] font-bold tracking-tight mb-3">Start investigating now</h2>
        <p className="mb-8 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Create an account, upload an image, and run the full private OSINT workflow.
        </p>
        <Link to="/signup" className="btn-primary text-sm px-5 py-3 inline-flex items-center gap-2">
          Create Free Account <ChevronRight size={14} />
        </Link>
      </div>

      <div className="border-t px-6 py-8 flex items-center justify-between max-w-5xl mx-auto" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-md bg-ios-blue flex items-center justify-center">
            <Eye size={11} className="text-white" />
          </div>
          <span className="text-sm font-semibold">VISION</span>
        </div>
        <div className="flex items-center gap-5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          <a href="https://github.com/bubbaBRO1/vision-copy" target="_blank" rel="noopener noreferrer" className="hover:text-text-primary transition-colors">GitHub</a>
          <Link to="/signup" className="hover:text-text-primary transition-colors">Create Account</Link>
          <Link to="/login" className="hover:text-text-primary transition-colors">Login</Link>
        </div>
      </div>
    </div>
  )
}
