import React, { useState, useEffect, useCallback, lazy, Suspense } from 'react'
import { ArrowLeft, Download, Trash2, RotateCcw } from 'lucide-react'
import { api } from '../api'
import { formatDate, isProcessing, useProcessingWatch } from '../documents'
import ChatBox from './ChatBox'
import { GraphFallback, ProcessingBar } from './Dashboard'

const KnowledgeGraph = lazy(() => import('./KnowledgeGraph'))

// spaCy labels, in plain words
const ENTITY_LABELS = {
  PERSON: 'People',
  ORG: 'Organisations',
  PLACE: 'Places',
  PRODUCT: 'Products',
  EVENT: 'Events',
  GROUP: 'Groups',
  WORK: 'Works and laws',
  OTHER: 'Other'
}

// Show the most informative groups first
const GROUP_ORDER = ['PERSON', 'ORG', 'PLACE', 'PRODUCT', 'EVENT', 'GROUP', 'WORK', 'OTHER']

const groupEntities = (entities) => {
  const groups = {}
  for (const ent of entities) {
    const text = ent.text.trim()
    if (!text) continue
    const group = (groups[ent.label] ||= new Map())
    group.set(text, (group.get(text) || 0) + (ent.mentions || 1))
  }
  const rank = (label) => {
    const i = GROUP_ORDER.indexOf(label)
    return i === -1 ? GROUP_ORDER.length : i
  }
  return Object.entries(groups)
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([label, group]) => ({
      label,
      name: ENTITY_LABELS[label] || label,
      // Most mentioned first
      items: [...group.entries()].sort((a, b) => b[1] - a[1]).map(([text, mentions]) => ({ text, mentions }))
    }))
}

const VIEWS = [
  { id: 'overview', label: 'Overview' },
  { id: 'graph', label: 'Entity graph' }
]

function Insights({ doc, view, setView }) {
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
        const [entRes, graphRes] = await Promise.all([api.getEntities(doc.id), api.getDocumentGraph(doc.id)])
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

  if (view === 'graph') {
    return (
      <div className="h-[600px]">
        {loading ? <GraphFallback /> : (
          <Suspense fallback={<GraphFallback />}>
            <KnowledgeGraph graphData={graphData} title="Entities in this document" />
          </Suspense>
        )}
      </div>
    )
  }

  return (
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
            <span className="spinner w-4 h-4" /> Loading people, organisations and places…
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
                    <span key={item.text} className="rounded border border-line bg-surface px-2 py-0.5 text-sm text-ink-muted">
                      {item.text}
                      {item.mentions > 1 && <span className="ml-1 text-xs text-ink-faint">×{item.mentions}</span>}
                    </span>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>
    </div>
  )
}

export default function DocumentView({ doc: initialDoc, onBack }) {
  const [doc, setDoc] = useState(initialDoc)
  const [view, setView] = useState('overview')
  const [actionError, setActionError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      setDoc(await api.getDocument(initialDoc.id))
    } catch (err) {
      if (err.status === 404) onBack()
    }
  }, [initialDoc.id, onBack])

  useEffect(() => { refresh() }, [refresh])

  useProcessingWatch([doc], (state) => {
    if (state.status === 'deleted') onBack()
    else if (state.status === 'ready' || state.status === 'failed') refresh()
    else setDoc(prev => ({ ...prev, ...state }))
  })

  const ready = doc.status === 'ready'
  const pages = doc.page_count ? ` · ${doc.page_count} ${doc.page_count === 1 ? 'page' : 'pages'}` : ''

  const handleDownload = async () => {
    setActionError(null)
    try { await api.downloadDocument(doc) } catch (err) { setActionError(err.message) }
  }

  const handleDelete = async () => {
    if (!window.confirm(`Delete “${doc.filename}”? This removes the file and everything extracted from it.`)) return
    try {
      await api.deleteDocument(doc.id)
      onBack()
    } catch (err) {
      setActionError(err.message || 'Could not delete the document.')
    }
  }

  const handleRetry = async () => {
    setActionError(null)
    try { setDoc(await api.reprocessDocument(doc.id)) } catch (err) { setActionError(err.message) }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <button onClick={onBack} className="inline-flex items-center gap-1.5 text-sm text-ink-muted hover:text-ink mb-4">
        <ArrowLeft className="w-4 h-4" />
        Library
      </button>

      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-5 mb-6 border-b border-line">
        <div className="min-w-0">
          <h1 className="font-serif text-2xl sm:text-3xl font-semibold text-ink break-words">{doc.filename}</h1>
          <p className="mt-1 text-sm text-ink-muted">Uploaded {formatDate(doc.created_at)}{pages}</p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {ready && (
            <div className="inline-flex rounded-md border border-line bg-surface p-0.5" role="tablist">
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
          )}
          {doc.mime_type && (
            <button onClick={handleDownload} className="btn-ghost p-2" title="Download original" aria-label="Download original">
              <Download className="w-4 h-4" />
            </button>
          )}
          <button onClick={handleDelete} className="btn-ghost p-2 hover:text-danger" title="Delete" aria-label="Delete document">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {actionError && <p role="alert" className="mb-4 text-sm text-danger">{actionError}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 min-w-0">
          {ready ? (
            <Insights doc={doc} view={view} setView={setView} />
          ) : doc.status === 'failed' ? (
            <div className="panel p-5">
              <h2 className="font-medium text-ink">This document couldn’t be processed</h2>
              <p className="mt-1 text-sm text-danger">{doc.error || 'Processing failed.'}</p>
              <button onClick={handleRetry} className="btn-secondary mt-4">
                <RotateCcw className="w-4 h-4" /> Process again
              </button>
            </div>
          ) : (
            <div className="panel p-5">
              <h2 className="font-medium text-ink">Processing this document</h2>
              <p className="mt-1 text-sm text-ink-muted">
                DocuMind is reading the text, splitting it into passages and indexing them for search.
                The summary and entities appear here when it’s done.
              </p>
              <ProcessingBar doc={doc} />
            </div>
          )}
        </div>

        <div className="lg:col-span-5 lg:sticky lg:top-20 h-[600px] lg:h-[calc(100vh-7rem)] min-h-[480px]">
          <ChatBox
            documentIds={[doc.id]}
            disabled={!ready}
            disabledMessage={isProcessing(doc)
              ? 'You can ask questions once processing finishes.'
              : 'This document has no searchable text yet.'}
          />
        </div>
      </div>
    </div>
  )
}
