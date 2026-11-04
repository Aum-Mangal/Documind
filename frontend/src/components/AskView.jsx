import React, { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { api } from '../api'
import { formatDate } from '../documents'
import ChatBox from './ChatBox'
import { ErrorNotice } from './Dashboard'

const ALL_SUGGESTIONS = [
  'What are the main themes across my documents?',
  'Which people or organisations come up most often?',
  'Where do my documents disagree with each other?'
]

function scopeLabel(documentIds, docsById) {
  if (!documentIds?.length) return 'All documents'
  if (documentIds.length === 1) return docsById[documentIds[0]]?.filename || '1 document'
  return `${documentIds.length} documents`
}

function ScopePicker({ docs, selected, onChange }) {
  const [choosing, setChoosing] = useState(selected.length > 0)
  const toggle = (id) => onChange(selected.includes(id) ? selected.filter(x => x !== id) : [...selected, id])

  return (
    <fieldset className="mb-4">
      <legend className="text-sm font-medium text-ink mb-2">Search in</legend>
      <div className="flex flex-wrap gap-4 text-sm text-ink">
        <label className="flex items-center gap-2">
          <input type="radio" name="scope" checked={!choosing} onChange={() => { setChoosing(false); onChange([]) }} className="accent-accent" />
          All documents
        </label>
        <label className="flex items-center gap-2">
          <input type="radio" name="scope" checked={choosing} onChange={() => setChoosing(true)} className="accent-accent" disabled={!docs.length} />
          Selected documents
        </label>
      </div>
      {choosing && (
        <ul className="mt-3 max-h-40 overflow-y-auto rounded-md border border-line bg-surface divide-y divide-line">
          {docs.map(doc => (
            <li key={doc.id}>
              <label className="flex items-center gap-2.5 px-3 py-2 text-sm text-ink hover:bg-sunken/60 cursor-pointer">
                <input type="checkbox" checked={selected.includes(doc.id)} onChange={() => toggle(doc.id)} className="accent-accent" />
                <span className="truncate">{doc.filename}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
    </fieldset>
  )
}

export default function AskView() {
  const [conversations, setConversations] = useState([])
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // null: a new conversation; otherwise the open conversation, with its messages
  const [active, setActive] = useState(null)
  const [opening, setOpening] = useState(false)
  const [scope, setScope] = useState([])
  // Remounts the chat panel when switching conversations
  const [chatKey, setChatKey] = useState('new-0')
  const [allowance, setAllowance] = useState(null)

  const refreshAllowance = useCallback(() => {
    api.me().then(me => setAllowance(me.usage.ai_tokens_today)).catch(() => {})
  }, [])
  useEffect(() => { refreshAllowance() }, [refreshAllowance])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [convs, documents] = await Promise.all([api.listConversations(), api.listDocuments()])
      setConversations(convs)
      setDocs(documents.filter(d => d.status === 'ready'))
    } catch (err) {
      setError(err.message || 'Could not load your conversations.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const docsById = Object.fromEntries(docs.map(d => [d.id, d]))

  const startNew = () => {
    setActive(null)
    setScope([])
    setChatKey(`new-${Date.now()}`)
  }

  const open = async (conversation) => {
    setOpening(true)
    setError(null)
    try {
      const full = await api.getConversation(conversation.id)
      setActive(full)
      setChatKey(`conv-${full.id}`)
    } catch (err) {
      setError(err.message || 'Could not open that conversation.')
    } finally {
      setOpening(false)
    }
  }

  const remove = async (conversation) => {
    if (!window.confirm(`Delete the conversation “${conversation.title}”?`)) return
    setConversations(prev => prev.filter(c => c.id !== conversation.id))
    if (active?.id === conversation.id) startNew()
    try {
      await api.deleteConversation(conversation.id)
    } catch (err) {
      setError(err.message || 'Could not delete the conversation.')
      load()
    }
  }

  // The first answer in a new conversation creates it; show it in the list
  const handleConversation = (conversation) => {
    refreshAllowance()
    setConversations(prev => [conversation, ...prev.filter(c => c.id !== conversation.id)])
    setActive(prev => (prev && prev.id === conversation.id ? prev : { ...conversation, messages: null }))
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
      <div className="mb-6">
        <h1 className="font-serif text-3xl font-semibold text-ink">Ask</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Questions across your whole library, or a few documents you choose. Every answer cites the passages it used.
        </p>
        {allowance?.limit && (
          <p className="mt-1 text-xs text-ink-faint">
            AI allowance today: {Math.min(100, Math.round((100 * allowance.used) / allowance.limit))}% used · resets at midnight UTC
          </p>
        )}
      </div>

      {error && <div className="mb-4"><ErrorNotice message={error} onRetry={load} /></div>}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <aside className="lg:col-span-4" aria-label="Conversations">
          <button onClick={startNew} className="btn-secondary w-full mb-3">
            <Plus className="w-4 h-4" /> New conversation
          </button>
          {loading ? (
            <div className="py-8 flex justify-center"><span className="spinner w-5 h-5" /></div>
          ) : conversations.length === 0 ? (
            <p className="text-sm text-ink-muted px-1">Your conversations will appear here.</p>
          ) : (
            <ul className="panel divide-y divide-line overflow-hidden">
              {conversations.map(c => (
                <li key={c.id} className="group relative">
                  <button
                    onClick={() => open(c)}
                    aria-current={active?.id === c.id ? 'true' : undefined}
                    className={`w-full text-left px-4 py-3 pr-10 transition-colors ${
                      active?.id === c.id ? 'bg-sunken' : 'hover:bg-sunken/60'
                    }`}
                  >
                    <span className="block text-sm font-medium text-ink truncate">{c.title}</span>
                    <span className="block text-xs text-ink-faint mt-0.5 truncate">
                      {scopeLabel(c.document_ids, docsById)} · {formatDate(c.updated_at)}
                    </span>
                  </button>
                  <button
                    onClick={() => remove(c)}
                    className="btn-ghost p-1.5 absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-danger"
                    aria-label={`Delete conversation ${c.title}`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <div className="lg:col-span-8 flex flex-col h-[calc(100vh-14rem)] min-h-[520px]">
          {!active && !loading && (
            docs.length ? (
              <ScopePicker docs={docs} selected={scope} onChange={setScope} />
            ) : (
              <p className="mb-4 text-sm text-ink-muted">Upload a document to start asking questions about it.</p>
            )
          )}
          {active && (
            <p className="mb-3 text-sm text-ink-muted">Searching: {scopeLabel(active.document_ids, docsById)}</p>
          )}
          <div className="flex-1 min-h-0">
            {opening ? (
              <div className="panel h-full flex items-center justify-center"><span className="spinner w-5 h-5" /></div>
            ) : (
              <ChatBox
                key={chatKey}
                conversationId={active?.id ?? null}
                initialMessages={active?.messages || []}
                documentIds={active ? undefined : scope}
                onConversation={handleConversation}
                disabled={!loading && !docs.length}
                disabledMessage="There’s nothing to search yet."
                title={active ? active.title : 'New conversation'}
                subtitle="Answers come only from your documents, with the passages they used."
                suggestions={ALL_SUGGESTIONS}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
