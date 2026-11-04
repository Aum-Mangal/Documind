import React, { useState, useEffect, useCallback, lazy, Suspense } from 'react'
import { Plus, Search, RefreshCw, AlertCircle, ChevronRight } from 'lucide-react'
import { api } from '../api'
import UploadModal from './UploadModal'

// Cytoscape is large; only load it when a graph is actually shown
const KnowledgeGraph = lazy(() => import('./KnowledgeGraph'))

const fileType = (filename) => (filename.split('.').pop() || '').toUpperCase().slice(0, 4)

export const formatDate = (value) =>
  value ? new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : ''

export function GraphFallback() {
  return (
    <div className="panel h-full min-h-[500px] flex items-center justify-center">
      <span className="spinner w-5 h-5" aria-label="Loading graph" />
    </div>
  )
}

function ErrorNotice({ message, onRetry }) {
  return (
    <div role="alert" className="panel flex items-center justify-between gap-4 px-4 py-3 border-danger/30 bg-danger-soft">
      <div className="flex items-center gap-2 text-sm text-danger">
        <AlertCircle className="w-4 h-4 shrink-0" />
        <span>{message}</span>
      </div>
      <button onClick={onRetry} className="btn-secondary py-1.5">Retry</button>
    </div>
  )
}

function Library({ onSelectDoc }) {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [isUploadOpen, setIsUploadOpen] = useState(false)

  const loadDocs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setDocs((await api.listDocuments()) || [])
    } catch (err) {
      setError(err.message || 'Could not load your documents.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadDocs() }, [loadDocs])

  const q = searchQuery.trim().toLowerCase()
  const filteredDocs = q
    ? docs.filter(d => d.filename.toLowerCase().includes(q) || (d.summary || '').toLowerCase().includes(q))
    : docs

  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
        <div>
          <h1 className="font-serif text-3xl font-semibold text-ink">Library</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {loading ? 'Loading…' : `${docs.length} ${docs.length === 1 ? 'document' : 'documents'}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 text-ink-faint absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search titles and summaries"
              aria-label="Search documents"
              className="input pl-9"
            />
          </div>
          <button onClick={() => setIsUploadOpen(true)} className="btn-primary shrink-0">
            <Plus className="w-4 h-4" />
            Upload
          </button>
        </div>
      </div>

      {error ? (
        <ErrorNotice message={error} onRetry={loadDocs} />
      ) : loading ? (
        <div className="py-20 flex justify-center">
          <span className="spinner w-6 h-6" aria-label="Loading documents" />
        </div>
      ) : docs.length === 0 ? (
        <div className="panel px-6 py-16 text-center">
          <h2 className="font-serif text-xl font-semibold text-ink">Your library is empty</h2>
          <p className="mt-2 text-sm text-ink-muted max-w-md mx-auto">
            Upload a PDF, Word document, text file or scanned image. DocuMind extracts the text,
            writes a short summary, and lets you ask questions about it.
          </p>
          <button onClick={() => setIsUploadOpen(true)} className="btn-primary mt-6">
            <Plus className="w-4 h-4" />
            Upload your first document
          </button>
        </div>
      ) : filteredDocs.length === 0 ? (
        <p className="py-12 text-center text-sm text-ink-muted">No documents match “{searchQuery}”.</p>
      ) : (
        <ul className="panel divide-y divide-line overflow-hidden">
          {filteredDocs.map((doc) => (
            <li key={doc.id}>
              <button
                onClick={() => onSelectDoc(doc)}
                className="group w-full text-left px-5 py-4 flex items-start gap-4 hover:bg-sunken/60 transition-colors"
              >
                <span className="mt-0.5 w-11 shrink-0 rounded border border-line bg-paper py-1 text-center font-mono text-[10px] font-medium text-ink-muted">
                  {fileType(doc.filename)}
                </span>
                <span className="flex-1 min-w-0">
                  <span className="flex items-baseline justify-between gap-4">
                    <span className="font-medium text-ink truncate group-hover:text-accent transition-colors">
                      {doc.filename}
                    </span>
                    <span className="shrink-0 text-xs text-ink-faint">{formatDate(doc.created_at)}</span>
                  </span>
                  <span className="mt-1 block text-sm text-ink-muted leading-relaxed line-clamp-2">
                    {doc.summary || 'No summary available.'}
                  </span>
                </span>
                <ChevronRight className="mt-1 w-4 h-4 shrink-0 text-ink-faint group-hover:text-accent transition-colors" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={loadDocs}
      />
    </>
  )
}

function GlobalGraph() {
  const [graph, setGraph] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadGraph = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setGraph(await api.getGlobalGraph())
    } catch (err) {
      setError(err.message || 'Could not build the knowledge graph.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadGraph() }, [loadGraph])

  return (
    <>
      <div className="flex items-end justify-between gap-4 mb-6">
        <div>
          <h1 className="font-serif text-3xl font-semibold text-ink">Knowledge graph</h1>
          <p className="mt-1 text-sm text-ink-muted">
            People, organisations, places and other entities across your documents, linked when they appear together.
          </p>
        </div>
        <button onClick={loadGraph} disabled={loading} className="btn-secondary shrink-0">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error ? (
        <ErrorNotice message={error} onRetry={loadGraph} />
      ) : (
        <div className="h-[620px]">
          {loading ? (
            <GraphFallback />
          ) : (
            <Suspense fallback={<GraphFallback />}>
              <KnowledgeGraph graphData={graph} title="All documents" />
            </Suspense>
          )}
        </div>
      )}
    </>
  )
}

export default function Dashboard({ onSelectDoc, activeTab = 'documents' }) {
  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
      {activeTab === 'graph' ? <GlobalGraph /> : <Library onSelectDoc={onSelectDoc} />}
    </div>
  )
}
