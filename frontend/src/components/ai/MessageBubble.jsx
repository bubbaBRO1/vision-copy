import { motion } from 'framer-motion'
import { Bot } from 'lucide-react'

function renderMarkdown(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code style="background:var(--surface-4);padding:1px 4px;border-radius:4px;font-family:monospace;font-size:0.85em">$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:var(--blue);text-decoration:underline">$1</a>')
    .replace(/\n/g, '<br />')
}

export function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {!isUser && (
        <div
          className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center mt-0.5"
          style={{ background: 'var(--surface-4)' }}
        >
          <Bot size={12} style={{ color: 'var(--blue)' }} />
        </div>
      )}

      <div
        className="max-w-[82%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed"
        style={isUser
          ? { background: 'var(--blue)', color: '#fff' }
          : { background: 'var(--surface-3)', color: 'var(--text-primary)' }
        }
        dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
      />
    </motion.div>
  )
}
