import React, { useEffect, useState } from 'react'
import { api } from '../api'

// The API can take a minute to come up (first start, or Docker still starting). Instead of
// letting that look like a failure, say so and keep checking until it answers.
const SLOW_AFTER_MS = 2000
const RETRY_EVERY_MS = 3000

export default function ServerStatus() {
  const [state, setState] = useState('checking') // 'checking' | 'waking' | 'ready'

  useEffect(() => {
    let cancelled = false
    const slowTimer = setTimeout(() => { if (!cancelled) setState(s => (s === 'checking' ? 'waking' : s)) }, SLOW_AFTER_MS)

    const check = async () => {
      while (!cancelled) {
        if (await api.health()) {
          if (!cancelled) setState('ready')
          return
        }
        if (!cancelled) setState('waking')
        await new Promise(resolve => setTimeout(resolve, RETRY_EVERY_MS))
      }
    }
    check()
    return () => { cancelled = true; clearTimeout(slowTimer) }
  }, [])

  if (state !== 'waking') return null
  return (
    <div role="status" className="border-b border-line bg-accent-soft px-4 py-2 text-center text-sm text-ink">
      <span className="spinner w-3.5 h-3.5 mr-2 align-[-2px]" />
      Waiting for the server. If you just started DocuMind this can take a minute; otherwise check that Docker is running.
    </div>
  )
}
