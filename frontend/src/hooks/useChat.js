import { useCallback, useRef } from 'react'
import { useChatStore } from '../store/chatStore'
import { useSearchStore } from '../store/searchStore'
import { useAuthStore } from '../store/authStore'

export function useChat() {
  const { model, mode, isIncognito, addMessage, appendToLast, setStreaming, newSession, activeSessionId } = useChatStore()
  const { currentSearchId } = useSearchStore()
  const accessToken = useAuthStore((s) => s.accessToken)
  const abortRef = useRef(null)

  const sendMessage = useCallback(async (content) => {
    addMessage({ role: 'user', content })
    setStreaming(true)

    const controller = new AbortController()
    abortRef.current = () => controller.abort()

    try {
      const response = await fetch('/api/chat/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken || ''}`,
        },
        signal: controller.signal,
        body: JSON.stringify({
          content,
          model,
          mode,
          is_incognito: isIncognito,
          session_id: isIncognito ? null : activeSessionId,
          search_id: currentSearchId,
        }),
      })

      const sessionId = response.headers.get('X-Session-Id')
      if (sessionId && sessionId !== 'incognito' && !activeSessionId) {
        newSession(sessionId)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value)
        const lines = text.split('\n')
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const token = line.slice(6)
            if (token === '[DONE]') break
            appendToLast(token)
          }
        }
      }
    } catch (e) {
      addMessage({ role: 'assistant', content: `Error: ${e.message}` })
    } finally {
      setStreaming(false)
    }
  }, [model, mode, isIncognito, activeSessionId, currentSearchId, accessToken, addMessage, appendToLast, setStreaming, newSession])

  const abort = useCallback(() => {
    abortRef.current?.()
    setStreaming(false)
  }, [setStreaming])

  return { sendMessage, abort }
}
