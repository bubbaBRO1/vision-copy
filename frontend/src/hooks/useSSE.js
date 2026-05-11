import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'

/**
 * SSE hook using fetch instead of EventSource so we can send Authorization header.
 * Avoids leaking the JWT in the URL (query params appear in logs, referrer headers, browser history).
 */
export function useSSE(url, { onMessage, onDone, onError, enabled = true } = {}) {
  const abortRef = useRef(null)
  const token = useAuthStore((s) => s.accessToken)

  const connect = useCallback(() => {
    if (!url || !enabled) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const headers = { Accept: 'text/event-stream' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    fetch(url, { headers, signal: controller.signal })
      .then((res) => {
        if (!res.ok || !res.body) {
          onError?.(new Error(`SSE connect failed: ${res.status}`))
          return
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        const pump = () => {
          reader.read().then(({ done, value }) => {
            if (done) {
              onDone?.()
              return
            }

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() ?? ''

            for (const line of lines) {
              if (!line.startsWith('data: ')) continue
              const raw = line.slice(6).trim()
              if (!raw) continue
              try {
                const data = JSON.parse(raw)
                if (data.stage === '__done__') {
                  onDone?.()
                  controller.abort()
                  return
                }
                onMessage?.(data)
              } catch {
                onMessage?.({ raw })
              }
            }

            pump()
          }).catch((err) => {
            if (err.name !== 'AbortError') onError?.(err)
          })
        }

        pump()
      })
      .catch((err) => {
        if (err.name !== 'AbortError') onError?.(err)
      })
  }, [url, enabled, token, onMessage, onDone, onError])

  useEffect(() => {
    connect()
    return () => abortRef.current?.abort()
  }, [connect])

  const abort = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { abort }
}
