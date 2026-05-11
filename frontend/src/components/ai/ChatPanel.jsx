import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Square, Bot, Ghost, ChevronDown, Trash2 } from 'lucide-react'
import { useChatStore, CHAT_MODES } from '../../store/chatStore'
import { useChat } from '../../hooks/useChat'
import { MessageBubble } from './MessageBubble'
import { SlashCommandMenu } from './SlashCommandMenu'
import { ModelSelector } from './ModelSelector'

export function ChatPanel({ searchId }) {
  const [input, setInput] = useState('')
  const [showSlash, setShowSlash] = useState(false)
  const [showModes, setShowModes] = useState(false)
  const { messages, isStreaming, mode, isIncognito, setMode, clearMessages } = useChatStore()
  const { sendMessage, abort } = useChat()
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  const currentMode = CHAT_MODES.find(m => m.id === mode) || CHAT_MODES[0]

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus on "/" key press globally
  useEffect(() => {
    const handler = (e) => {
      if (e.key === '/' && document.activeElement !== inputRef.current) {
        e.preventDefault()
        inputRef.current?.focus()
        setInput('/')
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || isStreaming) return
    setInput('')
    setShowSlash(false)
    await sendMessage(text)
  }

  const handleInputChange = (e) => {
    const val = e.target.value
    setInput(val)
    setShowSlash(val.startsWith('/') && val.length > 0)
  }

  const selectCommand = (cmd) => {
    setInput(cmd + ' ')
    setShowSlash(false)
    inputRef.current?.focus()
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[--border]">
        <div className="flex items-center gap-2">
          {isIncognito
            ? <Ghost size={16} style={{ color: 'var(--text-tertiary)' }} />
            : <Bot size={16} className="text-ios-blue" />
          }
          <span className="text-sm font-semibold mono" style={{ color: isIncognito ? 'var(--text-tertiary)' : 'var(--blue)' }}>
            {isIncognito ? 'Incognito' : 'VISION-AI'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Mode selector */}
          <div className="relative">
            <button
              onClick={() => setShowModes(v => !v)}
              className="flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-lg transition-colors"
              style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
            >
              {currentMode.label}
              <ChevronDown size={10} />
            </button>
            {showModes && (
              <div
                className="absolute right-0 top-full mt-1 z-50 rounded-xl overflow-hidden"
                style={{ background: 'var(--surface-3)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-lg)', width: 200 }}
              >
                {CHAT_MODES.map(m => (
                  <button
                    key={m.id}
                    onClick={() => { setMode(m.id); setShowModes(false); clearMessages() }}
                    className="w-full text-left px-3 py-2 text-xs transition-colors hover:bg-[--surface-4]"
                    style={{ color: mode === m.id ? 'var(--blue)' : 'var(--text-primary)' }}
                  >
                    <div className="font-medium">{m.label}</div>
                    <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>{m.description}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
          {messages.length > 0 && (
            <button
              onClick={clearMessages}
              className="p-1 rounded-lg transition-colors"
              style={{ color: 'var(--text-tertiary)' }}
              title="Clear conversation"
            >
              <Trash2 size={13} />
            </button>
          )}
          <ModelSelector />
        </div>
      </div>

      {/* Incognito notice */}
      {isIncognito && (
        <div className="px-4 py-2 text-[11px] flex items-center gap-1.5" style={{ background: 'var(--surface-3)', color: 'var(--text-tertiary)', borderBottom: '1px solid var(--border)' }}>
          <Ghost size={11} />
          Ephemeral session — nothing is stored
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-text-secondary text-sm py-8">
            <Bot size={32} className="mx-auto mb-2 opacity-30" />
            <p>Ask me anything about OSINT, geolocation, or this image.</p>
            <p className="text-xs mt-1">Type <kbd className="mono text-ios-blue">/</kbd> for commands</p>
          </div>
        )}
        <AnimatePresence initial={false}>
          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}
        </AnimatePresence>
        {isStreaming && (
          <div className="flex items-center gap-2 text-text-secondary text-xs">
            <div className="flex gap-1">
              {[0, 1, 2].map(i => (
                <div key={i} className="w-1.5 h-1.5 bg-accent-cyan rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </div>
            <span>Thinking...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Slash command menu */}
      {showSlash && (
        <SlashCommandMenu query={input.slice(1)} onSelect={selectCommand} />
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-4 pb-4 pt-2 border-t border-[--border]">
        <div className="flex gap-2 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e) }
                if (e.key === 'Escape') setShowSlash(false)
              }}
              placeholder="Ask VISION-AI or type / for commands..."
              rows={1}
              className="input resize-none py-2 pr-2"
              style={{ minHeight: 40, maxHeight: 120 }}
            />
          </div>
          {isStreaming ? (
            <button type="button" onClick={abort} className="btn-danger p-2 flex-shrink-0">
              <Square size={16} />
            </button>
          ) : (
            <button type="submit" disabled={!input.trim()} className="btn-primary p-2 flex-shrink-0 disabled:opacity-40">
              <Send size={16} />
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
