import React from 'react'
import { LogOut } from 'lucide-react'

const TABS = [
  { id: 'documents', label: 'Library' },
  { id: 'ask', label: 'Ask' },
  { id: 'graph', label: 'Knowledge graph' }
]

export function Wordmark({ size = 'text-xl' }) {
  return (
    <span className={`font-serif ${size} font-semibold tracking-tight text-ink`}>
      Docu<span className="text-accent">Mind</span>
    </span>
  )
}

export default function Navbar({ activeTab, onNavigate, onLogout }) {
  return (
    <header className="border-b border-line bg-paper sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
        <div className="flex items-center gap-8 min-w-0">
          <button onClick={() => onNavigate('documents')} className="shrink-0 rounded" aria-label="DocuMind home">
            <Wordmark />
          </button>

          <nav className="flex items-center gap-1" aria-label="Main">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => onNavigate(tab.id)}
                aria-current={activeTab === tab.id ? 'page' : undefined}
                className={`relative px-3 py-4 text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'text-ink font-medium after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-accent'
                    : 'text-ink-muted hover:text-ink'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <button onClick={onLogout} className="btn-ghost px-2.5" title="Sign out">
          <LogOut className="w-4 h-4" />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  )
}
