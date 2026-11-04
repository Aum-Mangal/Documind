import React, { useState, useEffect, lazy, Suspense } from 'react'
import { ArrowLeft } from 'lucide-react'
import { api } from '../api'
import ChatBox from './ChatBox'
import { formatDate, GraphFallback } from './Dashboard'

const KnowledgeGraph = lazy(() => import('./KnowledgeGraph'))

// spaCy labels, in plain words
const ENTITY_LABELS = {
  PERSON: 'People',
  ORG: 'Organisations',
  GPE: 'Places',
  LOC: 'Locations',
  FAC: 'Facilities',
  NORP: 'Groups',
  PRODUCT: 'Products',
  EVENT: 'Events',
  WORK_OF_ART: 'Works',
  LAW: 'Laws',
  LANGUAGE: 'Languages',
  DATE: 'Dates',
  TIME: 'Times',
  MONEY: 'Money',
  PERCENT: 'Percentages',
  QUANTITY: 'Quantities',
  ORDINAL: 'Ordinals',
  CARDINAL: 'Numbers'
}

// Show the most informative groups first
const GROUP_ORDER = ['PERSON', 'ORG', 'GPE', 'LOC', 'PRODUCT', 'EVENT', 'NORP', 'FAC', 'WORK_OF_ART', 'LAW', 'MONEY', 'DATE']

const groupEntities = (entities) => {
  const groups = {}
  for (const ent of entities) {
    const text = ent.text.trim()
    if (!text) continue
    const set = (groups[ent.label] ||= new Set())
    set.add(text)
  }
  const rank = (label) => {
    const i = GROUP_ORDER.indexOf(label)
    return i === -1 ? GROUP_ORDER.length : i
  }
  return Object.entries(groups)
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([label, set]) => ({ label, name: ENTITY_LABELS[label] || label, items: [...set] }))
}

const VIEWS = [
  { id: 'overview', label: 'Overview' },
  { id: 'graph', label: 'Entity graph' }
]

export default function DocumentView({ doc, onBack }) {
  const [view, setView] = useState('overview')
  const [entities, setEntities] = useState([])
  const [graphData, setGraphData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    const fetchDetails = async () => {
      setLoading(true)
      setError(null)
      try {
        const [entRes, graphRes] = await Promise.all([
          api.getEntities(doc.id),
          api.getDocumentGraph(doc.id)
        ])
        if (cancelled) return
        setEntities(entRes.entities || [])
        setGraphData(graphRes)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load entities for this document.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchDetails()
    return () => { cancelled = true }
  }, [doc.id])

  const groups = groupEntities(entities)

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <button onClick={onBack} className="inline-flex items-center gap-1.5 text-sm text-ink-muted hover:text-ink mb-4">
        <ArrowLeft className="w-4 h-4" />
        Library
      </button>

      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-5 mb-6 border-b border-line">
        <div className="min-w-0">
          <h1 className="font-serif text-2xl sm:text-3xl font-semibold text-ink break-words">{doc.filename}</h1>
          <p className="mt-1 text-sm text-ink-muted">Uploaded {formatDate(doc.created_at)}</p>
        </div>

        <div className="inline-flex shrink-0 rounded-md border border-line bg-surface p-0.5" role="tablist">
          {VIEWS.map(v => (
            <button
              key={v.id}
              role="tab"
              aria-selected={view === v.id}
              onClick={() => setView(v.id)}
              className={`px-3.5 py-1.5 rounded text-sm transition-colors ${
                view === v.id ? 'bg-sunken text-ink font-medium' : 'text-ink-muted hover:text-ink'
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 min-w-0">
          {view === 'overview' ? (
            <div className="space-y-8">
              <section>
                <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-faint mb-2">Summary</h2>
                <p className="font-serif text-[17px] leading-relaxed text-ink whitespace-pre-wrap">
                  {doc.summary || 'No summary was generated for this document.'}
                </p>
              </section>

              <section>
                <div className="flex items-baseline justify-between mb-3">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
                    Entities{!loading && !error ? ` · ${groups.reduce((n, g) => n + g.items.length, 0)}` : ''}
                  </h2>
                  {groups.length > 0 && (
                    <button onClick={() => setView('graph')} className="text-sm text-accent hover:text-accent-hover">
                      View as graph
                    </button>
                  )}
                </div>

                {loading ? (
                  <p className="flex items-center gap-2 text-sm text-ink-muted">
                    <span className="spinner w-4 h-4" /> Finding names, places and dates…
                  </p>
                ) : error ? (
                  <p className="text-sm text-danger">{error}</p>
                ) : groups.length === 0 ? (
                  <p className="text-sm text-ink-muted">No named entities were found in this document.</p>
                ) : (
                  <dl className="space-y-4">
                    {groups.map(group => (
                      <div key={group.label}>
                        <dt className="text-sm font-medium text-ink mb-1.5">{group.name}</dt>
                        <dd className="flex flex-wrap gap-1.5">
                          {group.items.map(item => (
                            <span key={item} className="rounded border border-line bg-surface px-2 py-0.5 text-sm text-ink-muted">
                              {item}
                            </span>
                          ))}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
              </section>
            </div>
          ) : (
            <div className="h-[600px]">
              {loading ? (
                <GraphFallback />
              ) : (
                <Suspense fallback={<GraphFallback />}>
                  <KnowledgeGraph graphData={graphData} title="Entities in this document" />
                </Suspense>
              )}
            </div>
          )}
        </div>

        <div className="lg:col-span-5 lg:sticky lg:top-20 h-[600px] lg:h-[calc(100vh-7rem)] min-h-[480px]">
          <ChatBox docId={doc.id} />
        </div>
      </div>
    </div>
  )
}
