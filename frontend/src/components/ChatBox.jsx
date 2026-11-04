import React, { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowUp, ChevronDown, ChevronRight } from 'lucide-react'
import { api } from '../api'
import { pageLabel } from '../documents'

// Turn citations into links the markdown renderer hands back to us. Models drift between
// "[Source 2]", "【Source 2】", "[2]" and "[1, 3]", so accept all of them. Only numbers that
// match a real source are linked, and existing markdown links "[x](...)" are left alone.
const CITATION = /[[【]\s*(?:Sources?\s+)?(\d+(?:\s*(?:,|and)\s*(?:Source\s+)?\d+)*)\s*[\]】](?!\()/gi

const linkCitations = (text, sourceCount) =>
  (text || '').replace(CITATION, (match, list) => {
    const numbers = list.match(/\d+/g).map(Number)
    if (!numbers.every(n => n >= 1 && n <= sourceCount)) return match
    return numbers.map(n => `[Source ${n}](#source-${n})`).join(' ')
  })

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
          onClick={() => onCite(Number(match[1]))}
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

function Sources({ sources, expanded, onToggle }) {
  return (
    <div className="mt-3">
      <p className="text-xs font-medium text-ink-faint mb-1.5">Sources</p>
      <ol className="space-y-1">
        {sources.map((src) => {
          const isOpen = !!expanded[src.n]
          const pages = pageLabel(src.page_start, src.page_end)
          return (
            <li key={src.n} className="rounded-md border border-line bg-paper text-sm">
              <button
                onClick={() => onToggle(src.n)}
                aria-expanded={isOpen}
                className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-left text-ink-muted hover:text-ink"
              >
                {isOpen ? <ChevronDown className="w-3.5 h-3.5 shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0" />}
                <span className="font-medium shrink-0">Source {src.n}</span>
                <span className="truncate text-ink-faint">· {src.filename}{pages ? `, ${pages}` : ''}</span>
              </button>
              {isOpen && (
                <blockquote className="border-t border-line px-3 py-2 font-serif text-[15px] leading-relaxed text-ink-muted whitespace-pre-wrap break-words">
                  {src.text}
                </blockquote>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

const DEFAULT_SUGGESTIONS = [
  'Summarise the main points.',
  'Who are the key people and organisations?',
  'What conclusions does it reach?'
]

// A question-and-answer panel. Without conversationId the first question starts a new
// conversation (searching documentIds, or everything); later questions continue it.
export default function ChatBox({
  documentIds,
  conversationId: initialConversationId = null,
  initialMessages = [],
  onConversation,
  disabled = false,
  disabledMessage,
  title = 'Ask about this document',
  subtitle = 'Answers come only from the document’s text, with the passages they used.',
  suggestions = DEFAULT_SUGGESTIONS
}) {
  const [messages, setMessages] = useState(initialMessages)
  const [conversationId, setConversationId] = useState(initialConversationId)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [expandedSources, setExpandedSources] = useState({})
  const scrollRef = useRef(null)

  // Scroll only the message list; scrollIntoView would also scroll the page around it
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  const setSourceOpen = (msgIndex, n, open) => {
    const key = `${msgIndex}-${n}`
    setExpandedSources(prev => ({ ...prev, [key]: open ?? !prev[key] }))
  }

  const handleSend = async (questionText) => {
    const question = (questionText || input).trim()
    if (!question || loading || disabled) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: question }])
    setLoading(true)

    try {
      const res = await api.ask({ question, conversationId, documentIds })
      setConversationId(res.conversation.id)
      setMessages(prev => [...prev, res.message])
      onConversation?.(res.conversation)
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
    <section className="panel flex flex-col h-full overflow-hidden" aria-label={title}>
      <div className="px-4 py-3 border-b border-line">
        <h2 className="font-serif text-lg font-semibold text-ink">{title}</h2>
        <p className="text-xs text-ink-faint">{subtitle}</p>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-5" aria-live="polite">
        {disabled ? (
          <p className="pt-2 text-sm text-ink-muted">{disabledMessage}</p>
        ) : messages.length === 0 ? (
          <div className="pt-2">
            <p className="text-sm text-ink-muted mb-3">Try one of these, or ask your own question:</p>
            <ul className="space-y-1.5">
              {suggestions.map(q => (
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
            ) : msg.abstained ? (
              <p key={idx} className="text-[15px] text-ink-muted italic">
                {msg.content} Try rephrasing, or check that the right documents are included.
              </p>
            ) : (
              <div key={idx} className="text-[15px] leading-relaxed text-ink break-words">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents((n) => setSourceOpen(idx, n, true))}
                >
                  {linkCitations(msg.content, msg.sources?.length || 0)}
                </ReactMarkdown>

                {msg.sources?.length > 0 && (
                  <Sources
                    sources={msg.sources}
                    expanded={Object.fromEntries(msg.sources.map(s => [s.n, expandedSources[`${idx}-${s.n}`]]))}
                    onToggle={(n) => setSourceOpen(idx, n)}
                  />
                )}
              </div>
            )
          )
        )}

        {loading && (
          <p className="flex items-center gap-2 text-sm text-ink-muted">
            <span className="spinner w-4 h-4" />
            Searching and reading the relevant passages…
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
          aria-label={title}
          maxLength={2000}
          disabled={loading || disabled}
          className="input resize-none max-h-32"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading || disabled}
          aria-label="Send question"
          className="btn-primary p-2.5 shrink-0"
        >
          <ArrowUp className="w-4 h-4" />
        </button>
      </form>
    </section>
  )
}
