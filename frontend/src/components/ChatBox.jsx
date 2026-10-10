import React, { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Sparkles, ChevronDown, ChevronUp, BookOpen, CheckCircle, ShieldCheck } from 'lucide-react'
import { api } from '../api'

export default function ChatBox({ docId, docFilename }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [expandedSources, setExpandedSources] = useState({})
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  const toggleSource = (msgIndex, sourceIndex) => {
    const key = `${msgIndex}-${sourceIndex}`
    setExpandedSources(prev => ({
      ...prev,
      [key]: !prev[key]
    }))
  }

  const handleSend = async (questionText) => {
    const query = questionText || input.trim()
    if (!query || loading) return

    setInput('')
    const userMsg = { role: 'user', content: query }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await api.chatWithDocument(docId, query)
      const aiMsg = {
        role: 'assistant',
        content: res.answer,
        sources: res.sources || [],
        confidence: res.confidence || null
      }
      setMessages(prev => [...prev, aiMsg])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `Sorry, an error occurred: ${err.message || 'Unable to retrieve answer.'}`,
          isError: true
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  const suggestedQuestions = [
    "What is the main summary of this document?",
    "What are the key entities and organizations mentioned?",
    "What are the major takeaways or conclusions?"
  ]

  return (
    <div className="flex flex-col h-full bg-gray-900/60 rounded-2xl border border-gray-800 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-gray-800 bg-gray-950/40 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Bot className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-bold text-white">Document RAG Assistant</span>
        </div>
        <span className="text-xs text-gray-400 bg-gray-800/60 px-2 py-0.5 rounded font-mono truncate max-w-[200px]">
          {docFilename}
        </span>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 my-auto">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600/20 to-purple-600/20 border border-blue-500/20 flex items-center justify-center text-blue-400 mb-3 shadow-lg shadow-blue-500/10">
              <Sparkles className="w-6 h-6" />
            </div>
            <h4 className="text-white font-semibold text-sm">Ask Anything About This Document</h4>
            <p className="text-xs text-gray-400 mt-1 max-w-sm">
              Grounded answers generated strictly from document contents with exact chunk citations.
            </p>

            {/* Suggested Question Chips */}
            <div className="mt-6 space-y-2 w-full max-w-sm text-left">
              <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500 block mb-1">
                Suggested Prompts
              </span>
              {suggestedQuestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(q)}
                  className="w-full text-left p-2.5 rounded-xl bg-gray-800/40 hover:bg-gray-800 border border-gray-700/50 hover:border-blue-500/50 text-xs text-gray-300 hover:text-white transition-all flex items-center justify-between group"
                >
                  <span className="truncate pr-2">{q}</span>
                  <Send className="w-3 h-3 text-gray-500 group-hover:text-blue-400 shrink-0" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`flex space-x-2.5 max-w-[85%] ${
                  msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : 'flex-row'
                }`}
              >
                {/* Avatar */}
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : msg.isError
                      ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                      : 'bg-purple-600/20 text-purple-300 border border-purple-500/30'
                  }`}
                >
                  {msg.role === 'user' ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                </div>

                {/* Message Bubble */}
                <div
                  className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                      : msg.isError
                      ? 'bg-red-500/10 border border-red-500/20 text-red-300'
                      : 'bg-gray-800/80 border border-gray-700/70 text-gray-100 shadow-md'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>

                  {/* Confidence Badge */}
                  {msg.confidence && (
                    <div className="mt-3 pt-2 border-t border-gray-700/60 flex items-center space-x-2 text-xs text-emerald-400">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span className="font-semibold">Retrieval Confidence: {msg.confidence}%</span>
                    </div>
                  )}

                  {/* Sources Accordion */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center space-x-1.5 text-xs text-gray-400 font-semibold">
                        <BookOpen className="w-3.5 h-3.5 text-blue-400" />
                        <span>Cited Sources ({msg.sources.length}):</span>
                      </div>
                      <div className="space-y-1.5">
                        {msg.sources.map((src, sIdx) => {
                          const isExpanded = expandedSources[`${idx}-${sIdx}`]
                          return (
                            <div
                              key={sIdx}
                              className="rounded-lg bg-gray-950/60 border border-gray-800 text-xs overflow-hidden"
                            >
                              <button
                                onClick={() => toggleSource(idx, sIdx)}
                                className="w-full px-3 py-2 flex items-center justify-between text-gray-300 hover:text-white hover:bg-gray-800/40 transition-colors"
                              >
                                <span className="font-medium text-blue-400">
                                  Source {sIdx + 1} {src.score ? `• ${Math.round(src.score * 100)}% match` : ''}
                                </span>
                                {isExpanded ? (
                                  <ChevronUp className="w-3.5 h-3.5 text-gray-500" />
                                ) : (
                                  <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
                                )}
                              </button>
                              {isExpanded && (
                                <div className="px-3 pb-2.5 pt-1 text-gray-400 text-[11px] font-mono leading-relaxed border-t border-gray-800/60 bg-gray-950/90">
                                  "{src.text || src.chunk || src}"
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}

        {/* Loading Indicator */}
        {loading && (
          <div className="flex items-center space-x-2.5">
            <div className="w-7 h-7 rounded-lg bg-purple-600/20 text-purple-300 border border-purple-500/30 flex items-center justify-center">
              <Bot className="w-3.5 h-3.5" />
            </div>
            <div className="rounded-2xl px-4 py-3 bg-gray-800/80 border border-gray-700/70 flex items-center space-x-2 text-xs text-gray-400">
              <span className="animate-spin w-3.5 h-3.5 border-2 border-blue-400 border-t-transparent rounded-full" />
              <span>Scanning document vectors & synthesizing answer...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleSend()
        }}
        className="p-3 bg-gray-950/80 border-t border-gray-800 flex items-center space-x-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about this document..."
          disabled={loading}
          className="flex-1 bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="p-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 disabled:opacity-40 transition-all"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  )
}
