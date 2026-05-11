import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, CheckCircle2, Database, KeyRound, Server, ShieldCheck } from 'lucide-react'
import api from '../utils/api'

function CheckRow({ icon: Icon, label, status, detail }) {
  const ok = status === true || status === 'ok'
  return (
    <div className="flex items-start gap-3 p-3 rounded-xl" style={{ background: 'var(--surface-3)', border: '1px solid var(--border)' }}>
      <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: ok ? 'rgba(48,209,88,0.12)' : 'rgba(255,159,10,0.12)', color: ok ? 'var(--green)' : 'var(--orange)' }}>
        <Icon size={15} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium">{label}</p>
          {ok ? <CheckCircle2 size={13} style={{ color: 'var(--green)' }} /> : <AlertTriangle size={13} style={{ color: 'var(--orange)' }} />}
        </div>
        {detail && <p className="text-xs mt-1 break-words" style={{ color: 'var(--text-secondary)' }}>{detail}</p>}
      </div>
    </div>
  )
}

export default function SystemHealth() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/api/system/health')
      .then(({ data }) => setHealth(data))
      .catch((error) => setHealth({ status: 'error', error: error.message }))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6 space-y-3"><div className="h-8 w-48 skeleton rounded-xl" /><div className="h-80 skeleton rounded-xl" /></div>

  const required = health?.checks?.required_env || {}
  const optional = health?.checks?.optional_integrations || {}

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto space-y-5">
      <div>
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: 'rgba(10,132,255,0.12)', color: 'var(--blue)' }}>
            <Activity size={20} />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">System Health</h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
              Local setup, service readiness, optional integrations, and privacy posture.
            </p>
          </div>
        </div>
      </div>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="card p-4">
          <p className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-tertiary)' }}>Backend</p>
          <p className="text-2xl font-bold mt-2 capitalize">{health?.status || 'unknown'}</p>
        </div>
        <div className="card p-4">
          <p className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-tertiary)' }}>Database</p>
          <p className="text-2xl font-bold mt-2 capitalize">{health?.checks?.database?.status || 'unknown'}</p>
        </div>
        <div className="card p-4">
          <p className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-tertiary)' }}>AI Notice</p>
          <p className="text-sm mt-2" style={{ color: 'var(--text-secondary)' }}>{health?.privacy?.ai_notice || 'AI outputs require verification.'}</p>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-5 space-y-3">
          <h2 className="text-sm font-semibold flex items-center gap-2"><Server size={15} /> Core Checks</h2>
          <CheckRow icon={Database} label="Database" status={health?.checks?.database?.status} detail={health?.checks?.database?.detail} />
          <CheckRow icon={ShieldCheck} label="Upload storage" status="ok" detail={health?.checks?.uploads?.path} />
          <CheckRow icon={Server} label="Ollama URL configured" status={!!health?.checks?.ollama?.configured_url} detail={health?.checks?.ollama?.configured_url} />
        </div>

        <div className="card p-5 space-y-3">
          <h2 className="text-sm font-semibold flex items-center gap-2"><KeyRound size={15} /> Required Environment</h2>
          {Object.entries(required).map(([key, value]) => (
            <CheckRow key={key} icon={KeyRound} label={key} status={value.present && value.safe} detail={value.safe ? 'Configured' : 'Missing or unsafe default'} />
          ))}
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-semibold mb-3">Optional Integrations</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {Object.entries(optional).map(([key, enabled]) => (
            <CheckRow key={key} icon={KeyRound} label={key} status={enabled} detail={enabled ? 'Enabled' : 'Not configured'} />
          ))}
        </div>
      </section>
    </div>
  )
}
