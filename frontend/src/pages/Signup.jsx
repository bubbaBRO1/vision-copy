import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, Check, X } from 'lucide-react'
import api from '../utils/api'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

function PasswordStrength({ password }) {
  const checks = [
    { label: '8+ chars',  ok: password.length >= 8 },
    { label: 'Uppercase', ok: /[A-Z]/.test(password) },
    { label: 'Number',    ok: /\d/.test(password) },
    { label: 'Symbol',    ok: /[^a-zA-Z0-9]/.test(password) },
  ]
  const score = checks.filter(c => c.ok).length
  const barColor = score <= 1 ? 'var(--red)' : score <= 2 ? 'var(--orange)' : score <= 3 ? 'var(--yellow)' : 'var(--green)'

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex gap-1">
        {[0,1,2,3].map(i => (
          <div
            key={i}
            className="h-1 flex-1 rounded-full transition-all duration-300"
            style={{ background: i < score ? barColor : 'var(--surface-4)' }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {checks.map(({ label, ok }) => (
          <span
            key={label}
            className="flex items-center gap-0.5 text-xs"
            style={{ color: ok ? 'var(--green)' : 'var(--text-tertiary)' }}
          >
            {ok ? <Check size={10} /> : <X size={10} />} {label}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function Signup() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const isUpgrade = searchParams.get('upgrade') === '1'
  const { login, accessToken } = useAuthStore()
  const [form, setForm] = useState({ username: '', email: '', password: '', invite_code: null, accept_terms: false })
  const [usernameStatus, setUsernameStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const googleBtnRef = useRef(null)

  const handleGoogleCredential = async (response) => {
    try {
      const { data } = await api.post('/auth/google', { id_token: response.credential })
      const me = await api.get('/auth/me', { headers: { Authorization: `Bearer ${data.access_token}` } })
      login(me.data, data.access_token)
      navigate('/search')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Google sign-up failed')
    }
  }

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !window.google || !googleBtnRef.current) return
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleGoogleCredential,
    })
    window.google.accounts.id.renderButton(googleBtnRef.current, {
      theme: 'filled_black', size: 'large', width: '100%', text: 'signup_with',
    })
  }, [])

  const checkUsername = async (val) => {
    if (val.length < 3) { setUsernameStatus(null); return }
    setUsernameStatus('checking')
    try {
      const { data } = await api.get(`/auth/check-username/${val}`)
      setUsernameStatus(data.available ? 'available' : 'taken')
    } catch { setUsernameStatus(null) }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.accept_terms) { toast.error('Must accept terms'); return }
    setLoading(true)
    try {
      if (isUpgrade && accessToken) {
        // Upgrade guest → real account, preserving data
        const { data } = await api.post(
          '/auth/upgrade-guest',
          { username: form.username, email: form.email, password: form.password, accept_terms: form.accept_terms },
          { headers: { Authorization: `Bearer ${accessToken}` } }
        )
        const me = await api.get('/auth/me', { headers: { Authorization: `Bearer ${data.access_token}` } })
        login(me.data, data.access_token)
        toast.success('Account created — your searches and chats have been saved!')
        navigate('/dashboard')
      } else {
        await api.post('/auth/signup', { ...form, hcaptcha_token: null })
        toast.success('Account created! Check your email to verify.')
        navigate('/login')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Signup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{ background: 'var(--surface-1)' }}
    >
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-ios-blue flex items-center justify-center mx-auto mb-4" style={{ boxShadow: '0 8px 24px rgba(10,132,255,0.3)' }}>
            <Eye size={22} className="text-white" />
          </div>
          <h1 className="text-xl font-semibold tracking-tight">{isUpgrade ? 'Save your work' : 'Create your account'}</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
            {isUpgrade ? 'Create an account to keep your searches and chats' : 'Free to use — no invite required'}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl p-6 space-y-4"
          style={{
            background: 'var(--glass-bg)',
            backdropFilter: 'blur(20px)',
            border: '1px solid var(--glass-border)',
            boxShadow: 'var(--shadow-lg)',
          }}
        >
          <div className="space-y-1">
            <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Username</label>
            <input
              className="input"
              value={form.username}
              onChange={e => { setForm(f => ({ ...f, username: e.target.value })); checkUsername(e.target.value) }}
              pattern="[a-zA-Z0-9_-]{3,50}" required autoFocus
            />
            {usernameStatus && (
              <p className="text-xs mt-0.5" style={{
                color: usernameStatus === 'available' ? 'var(--green)'
                  : usernameStatus === 'taken' ? 'var(--red)'
                  : 'var(--text-tertiary)'
              }}>
                {usernameStatus === 'available' ? '✓ Available' : usernameStatus === 'taken' ? '✗ Taken' : 'Checking…'}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Email</label>
            <input type="email" className="input" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Password</label>
            <input type="password" className="input" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required />
            {form.password && <PasswordStrength password={form.password} />}
          </div>

          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={form.accept_terms}
              onChange={e => setForm(f => ({ ...f, accept_terms: e.target.checked }))}
              required
            />
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              I accept the{' '}
              <Link to="/terms" style={{ color: 'var(--blue)' }}>Terms of Service</Link>
              {' '}and{' '}
              <Link to="/privacy" style={{ color: 'var(--blue)' }}>Privacy Policy</Link>
            </span>
          </label>

          <button
            type="submit"
            disabled={loading || usernameStatus === 'taken'}
            className="btn-primary w-full py-3"
          >
            {loading ? 'Creating account…' : 'Create account'}
          </button>

          {GOOGLE_CLIENT_ID && (
            <>
              <div className="flex items-center gap-2 my-1">
                <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>or</span>
                <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
              </div>
              <div ref={googleBtnRef} className="w-full" />
            </>
          )}

          <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>
            Already have an account?{' '}
            <Link to="/login" className="font-medium" style={{ color: 'var(--blue)' }}>Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
