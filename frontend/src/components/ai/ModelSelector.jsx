import { useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { useChatStore } from '../../store/chatStore'
import api from '../../utils/api'

const DEFAULT_MODELS = ['llama3:8b', 'llava:13b', 'mistral:7b', 'codellama:13b']

export function ModelSelector() {
  const { model, setModel } = useChatStore()
  const [models, setModels] = useState(DEFAULT_MODELS)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    api.get('/api/chat/models').then(r => setModels(r.data?.models || DEFAULT_MODELS)).catch(() => {})
  }, [])

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1 text-xs mono text-text-dim hover:text-text-primary transition-colors"
      >
        {model} <ChevronDown size={11} />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 card border border-border-color rounded-lg overflow-hidden z-50 min-w-36">
          {models.map(m => (
            <button
              key={m}
              onClick={() => { setModel(m); setOpen(false) }}
              className={`w-full text-left px-3 py-1.5 text-xs mono hover:bg-accent-cyan/5 transition-colors ${m === model ? 'text-accent-green' : 'text-text-dim'}`}
            >
              {m}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
