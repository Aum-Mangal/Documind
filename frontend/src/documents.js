// Shared helpers for showing documents and their processing state
import { useEffect, useRef } from 'react'
import { api } from './api'

export const TERMINAL = new Set(['ready', 'failed'])

const STAGE_LABELS = {
  parsing: 'Reading the file',
  chunking: 'Splitting into passages',
  embedding: 'Indexing passages',
  linking: 'Finding people, places and links',
  summarizing: 'Writing a summary'
}

export const isProcessing = (doc) => doc && !TERMINAL.has(doc.status)

export const statusLabel = (doc) => {
  if (doc.status === 'queued') return doc.error ? 'Retrying shortly' : 'Waiting to start'
  if (doc.status === 'processing') return STAGE_LABELS[doc.stage] || 'Processing'
  if (doc.status === 'failed') return 'Failed'
  return 'Ready'
}

export const formatDate = (value) =>
  value ? new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : ''

export const formatBytes = (bytes) => {
  if (bytes == null) return ''
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(bytes < 10 * 1024 * 1024 ? 1 : 0)} MB`
}

export const pageLabel = (start, end) => {
  if (start == null) return null
  return end == null || end === start ? `p. ${start}` : `pp. ${start}–${end}`
}

// Follows the progress of every listed document that is still being processed. onState
// gets each update; the stream for a document closes once it is ready, failed or deleted.
export function useProcessingWatch(docs, onState) {
  const onStateRef = useRef(onState)
  onStateRef.current = onState
  const watching = docs.filter(isProcessing).map(d => d.id).sort().join(',')

  useEffect(() => {
    if (!watching) return
    const controller = new AbortController()
    for (const id of watching.split(',').map(Number)) {
      api.watchDocument(id, (state) => onStateRef.current(state), controller.signal).catch((err) => {
        if (err.name !== 'AbortError') console.warn('Progress stream ended:', err.message)
      })
    }
    return () => controller.abort()
  }, [watching])
}
