import React, { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowUp, ChevronDown, ChevronRight } from 'lucide-react'
import { api } from '../api'

// Turn "[Source 2]" citations (models sometimes use full-width 【】 brackets) into links
// the markdown renderer hands back to us
const linkCitations = (text) =>
  (text || '').replace(/[[【]\s*Source\s+(\d+)\s*[\]】](?!\()/g, '[Source $1](#source-$1)')

// Markdown elements styled for answers. Raw HTML in answers is never rendered.
const markdownComponents = (onCite) => ({
  p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
  h1: ({ children }) => <h3 className="font-serif font-semibold mt-3 mb-1">{children}</h3>,
  h2: ({ children }) => <h3 className="font-serif font-semibold mt-3 mb-1">{children}</h3>,
  h3: ({ children }) => <h4 className="font-semibold mt-3 mb-1">{children}</h4>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  code: ({ children }) => <code className="rounded bg-sunken px-1 py-0.5 font-mono text-[13px]">{children}</code>,
  pre: ({ children }) => <pre className="rounded-md bg-sunken p-3 overflow-x-auto mb-3 text-[13px]">{children}</pre>,
  blockquote: ({ children }) => <blockquote className="border-l-2 border-line-strong pl-3 text-ink-muted mb-3">{children}</blockquote>,
  table: ({ children }) => <div className="overflow-x-auto mb-3"><table className="text-sm border-collapse">{children}</table></div>,
  th: ({ children }) => <th className="border border-line px-2 py-1 text-left font-semibold bg-sunken/60">{children}</th>,
  td: ({ children }) => <td className="border border-line px-2 py-1">{children}</td>,
  a: ({ href, children }) => {
    const match = href?.match(/^#source-(\d+)$/)
    if (match) {
      return (
        <button
          type="button"
          onClick={() => onCite(Number(match[1]) - 1)}
          className="mx-0.5 rounded bg-accent-soft px-1.5 text-[12px] font-medium text-accent hover:bg-accent/20 align-baseline"
        >
          {children}
        </button>
      )
    }
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent underline underline-offset-2 hover:text-accent-hover">
        {children}
      </a>
    )
  }
})

const SUGGESTED_QUESTIONS = [
  'Summarise the main points.',
  'Who are the key people and organisations?',
  'What conclusions does it reach?'
]

function Sources({ sources, expanded, onToggle }) {
  return (
    <div className="mt-3">
      <p className="text-xs font-medium text-ink-faint mb-1.5">Sources</p>
      <ol className="space-y-1">
        {sources.map((src, sIdx) => {
          const isOpen = !!expanded[sIdx]
          return (
            <li key={sIdx} className="rounded-md border border-line bg-paper text-sm">
              <button
                onClick={() => onToggle(sIdx)}
                aria-expanded={isOpen}
                className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-left text-ink-muted hover:text-ink"
              >
                {isOpen ? <ChevronDown className="w-3.5 h-3.5 shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0" />}
                <span className="font-medium">Source {sIdx + 1}</span>
                {typeof src.score === 'number' && (
                  <span className="ml-auto text-xs text-ink-faint">{Math.round(src.score * 100)}% match</span>
                )}
              </button>
              {isOpen && (
                <blockquote className="border-t border-line px-3 py-2 font-serif text-[15px] leading-relaxed text-ink-muted whitespace-pre-wrap break-words">
                  {src.text || src.chunk || String(src)}
                </blockquote>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export default function ChatBox({ docId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [expandedSources, setExpandedSources] = useState({})
  const scrollRef = useRef(null)

  // Scroll only the message list; scrollIntoView would also scroll the page around it
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  const setSourceOpen = (msgIndex, sourceIndex, open) => {
    const key = `${msgIndex}-${sourceIndex}`
    setExpandedSources(prev => ({ ...prev, [key]: open ?? !prev[key] }))
  }

  const handleSend = async (questionText) => {
    const query = (questionText || input).trim()
    if (!query || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: query }])
    setLoading(true)

    try {
      const res = await api.chatWithDocument(docId, query)
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          sources: res.sources || [],
          confidence: typeof res.confidence === 'number' ? res.confidence : null
        }
      ])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: err.message || 'Could not get an answer. Please try again.', isError: true }
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="panel flex flex-col h-full overflow-hidden" aria-label="Ask about this document">
      <div className="px-4 py-3 border-b border-line">
        <h2 className="font-serif text-lg font-semibold text-ink">Ask about this document</h2>
        <p className="text-xs text-ink-faint">Answers come only from the document’s text, with the passages they used.</p>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-5" aria-live="polite">
        {messages.length === 0 ? (
          <div className="pt-2">
            <p className="text-sm text-ink-muted mb-3">Try one of these, or ask your own question:</p>
            <ul className="space-y-1.5">
              {SUGGESTED_QUESTIONS.map(q => (
                <li key={q}>
                  <button
                    onClick={() => handleSend(q)}
                    className="w-full text-left rounded-md border border-line bg-paper px-3 py-2 text-sm text-ink hover:border-line-strong hover:bg-sunken/60 transition-colors"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          messages.map((msg, idx) =>
            msg.role === 'user' ? (
              <div key={idx} className="flex justify-end">
                <p className="max-w-[85%] rounded-lg bg-sunken px-3.5 py-2 text-sm text-ink whitespace-pre-wrap break-words">
                  {msg.content}
                </p>
              </div>
            ) : msg.isError ? (
              <p key={idx} role="alert" className="rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
                {msg.content}
              </p>
            ) : (
              <div key={idx} className="text-[15px] leading-relaxed text-ink break-words">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents((sIdx) => setSourceOpen(idx, sIdx, true))}
                >
                  {linkCitations(msg.content)}
                </ReactMarkdown>

                {msg.sources?.length > 0 && (
                  <Sources
                    sources={msg.sources}
                    expanded={Object.fromEntries(msg.sources.map((_, s) => [s, expandedSources[`${idx}-${s}`]]))}
                    onToggle={(sIdx) => setSourceOpen(idx, sIdx)}
                  />
                )}

                {msg.confidence != null && (
                  <p className="mt-2 text-xs text-ink-faint">Best passage match: {msg.confidence}%</p>
                )}
              </div>
            )
          )
        )}

        {loading && (
          <p className="flex items-center gap-2 text-sm text-ink-muted">
            <span className="spinner w-4 h-4" />
            Reading the relevant passages…
          </p>
        )}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); handleSend() }}
        className="border-t border-line p-3 flex items-end gap-2"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
          }}
          rows={1}
          placeholder="Ask a question…"
          aria-label="Ask a question about this document"
          maxLength={2000}
          disabled={loading}
          className="input resize-none max-h-32"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          aria-label="Send question"
          className="btn-primary p-2.5 shrink-0"
        >
          <ArrowUp className="w-4 h-4" />
        </button>
      </form>
    </section>
  )
}
