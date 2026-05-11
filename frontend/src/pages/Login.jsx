import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye } from 'lucide-react'
import api from '../utils/api'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

export default function Login() {
  const navigate = useNavigate()
  const { login } = useAuthStore()
  const [form, setForm] = useState({ identifier: '', password: '', remember_me: false })
  const [loading, setLoading] = useState(false)
  const googleBtnRef = useRef(null)

  const _doLogin = async (access_token) => {
    const me = await api.get('/auth/me', { headers: { Authorization: `Bearer ${access_token}` } })
    login(me.data, access_token)
    navigate('/search')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const { data } = await api.post('/auth/login', form)
      await _doLogin(data.access_token)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleCredential = async (response) => {
    try {
      const { data } = await api.post('/auth/google', { id_token: response.credential })
      await _doLogin(data.access_token)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Google sign-in failed')
    }
  }

  const handleGuestLogin = async () => {
    try {
      const { data } = await api.post('/auth/guest')
      login({ username: 'Guest', role: 'guest', email: '' }, data.access_token)
      navigate('/search')
    } catch (err) {
      toast.error('Guest login failed')
    }
  }

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !window.google || !googleBtnRef.current) return
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleGoogleCredential,
    })
    window.google.accounts.id.renderButton(googleBtnRef.current, {
      theme: 'filled_black', size: 'large', width: '100%', text: 'signin_with',
    })
  }, [])

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
          <h1 className="text-xl font-semibold tracking-tight">Sign in to VISION</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>Enter your credentials to continue</p>
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
            <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Email or username</label>
            <input
              className="input"
              value={form.identifier}
              onChange={e => setForm(f => ({ ...f, identifier: e.target.value }))}
              autoFocus required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Password</label>
            <input
              type="password" className="input"
              value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
              required
            />
          </div>
          <div className="flex items-center justify-between text-xs">
            <label className="flex items-center gap-2 cursor-pointer" style={{ color: 'var(--text-secondary)' }}>
              <input type="checkbox" checked={form.remember_me} onChange={e => setForm(f => ({ ...f, remember_me: e.target.checked }))} />
              Remember me
            </label>
            <Link to="/forgot-password" className="transition-colors" style={{ color: 'var(--blue)' }}>Forgot password?</Link>
          </div>
          <button type="submit" disabled={loading} className="btn-primary w-full py-3">
            {loading ? 'Signing in…' : 'Sign in'}
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

          <button
            type="button"
            onClick={handleGuestLogin}
            className="w-full py-2.5 rounded-xl text-sm font-medium transition-all duration-150"
            style={{
              background: 'var(--surface-3)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            Continue as Guest
          </button>

          <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>
            No account?{' '}
            <Link to="/signup" className="font-medium" style={{ color: 'var(--blue)' }}>Create account</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
