import { Link } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

export default function GuestBanner() {
  const { isGuest } = useAuthStore()
  if (!isGuest()) return null

  return (
    <div
      className="flex items-center justify-between px-4 py-2 text-xs shrink-0"
      style={{
        background: 'rgba(10,132,255,0.12)',
        borderBottom: '1px solid rgba(10,132,255,0.25)',
        color: 'var(--text-secondary)',
      }}
    >
      <span>Guest session — searches and chats are temporary</span>
      <Link
        to="/signup?upgrade=1"
        className="font-semibold text-xs transition-colors"
        style={{ color: 'var(--blue)' }}
      >
        Save your work — create free account →
      </Link>
    </div>
  )
}
