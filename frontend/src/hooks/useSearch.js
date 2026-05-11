import { useCallback } from 'react'
import api from '../utils/api'
import { useSearchStore } from '../store/searchStore'
import { useSSE } from './useSSE'

export function useSearch() {
  const { currentSearchId, startSearch, updateStage, setResults, setError } = useSearchStore()

  const { abort } = useSSE(
    currentSearchId ? `/api/search/${currentSearchId}/stream` : null,
    {
      enabled: !!currentSearchId,
      onMessage: (data) => {
        if (data.stage && data.status) {
          updateStage(data.stage, data.status, data.data)
        }
      },
      onDone: async () => {
        if (currentSearchId) {
          const { data } = await api.get(`/api/search/${currentSearchId}`)
          setResults(data.results)
        }
      },
      onError: () => setError('Connection lost'),
    }
  )

  const uploadImage = useCallback(async (file) => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await api.post('/api/search', form)
    startSearch(data.search_id, data.filename)
    return data.search_id
  }, [startSearch])

  return { uploadImage, abort }
}
