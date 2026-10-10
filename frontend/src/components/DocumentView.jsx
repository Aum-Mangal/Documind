import React, { useState, useEffect } from 'react'
import { ArrowLeft, FileText, Network, Sparkles, Tag, Calendar, Layers, ExternalLink } from 'lucide-react'
import { api } from '../api'
import KnowledgeGraph from './KnowledgeGraph'
import ChatBox from './ChatBox'

export default function DocumentView({ doc, onBack }) {
  const [activeTab, setActiveTab] = useState('overview') // 'overview' | 'graph'
  const [entities, setEntities] = useState([])
  const [graphData, setGraphData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchDocDetails = async () => {
      setLoading(true)
      try {
        // Fetch entities and document-specific graph
        const [entRes, graphRes] = await Promise.all([
          api.getEntities(doc.id).catch(() => ({ entities: [] })),
          api.getDocumentGraph(doc.id).catch(() => ({ nodes: [], edges: [] }))
        ])

        setEntities(entRes.entities || [])
        setGraphData(graphRes)
      } catch (err) {
        console.error('Error fetching document metadata:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchDocDetails()
  }, [doc.id])

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col p-4 md:p-6 max-w-7xl mx-auto w-full gap-4">
      {/* Top action bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-gray-900/60 p-3 px-4 rounded-xl border border-gray-800 backdrop-blur">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gray-800 text-gray-300 hover:text-white hover:bg-gray-700 text-xs font-semibold transition-all"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Library</span>
          </button>
          <div className="flex items-center space-x-2">
            <FileText className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-bold text-white max-w-md truncate">{doc.filename}</h2>
          </div>
        </div>

        {/* View mode toggle */}
        <div className="flex items-center space-x-1 bg-gray-950/80 p-1 rounded-lg border border-gray-800">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-3 py-1 rounded-md text-xs font-semibold transition-all flex items-center space-x-1.5 ${
              activeTab === 'overview'
                ? 'bg-blue-600 text-white shadow'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Overview & Entities</span>
          </button>
          <button
            onClick={() => setActiveTab('graph')}
            className={`px-3 py-1 rounded-md text-xs font-semibold transition-all flex items-center space-x-1.5 ${
              activeTab === 'graph'
                ? 'bg-purple-600 text-white shadow'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>Entity Graph</span>
          </button>
        </div>
      </div>

      {/* Main split grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-0">
        {/* Left Pane (Document Details / Graph) */}
        <div className="lg:col-span-7 flex flex-col h-full min-h-0">
          {activeTab === 'overview' ? (
            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              {/* AI Summary Card */}
              <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5 shadow-lg">
                <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-blue-400 mb-3">
                  <Sparkles className="w-4 h-4" />
                  <span>Executive AI Summary</span>
                </div>
                <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
                  {doc.summary || "No summary was generated for this document."}
                </p>
                <div className="mt-4 pt-3 border-t border-gray-800/80 flex items-center justify-between text-xs text-gray-500">
                  <div className="flex items-center space-x-1.5">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Uploaded on {new Date(doc.created_at).toLocaleDateString()}</span>
                  </div>
                  <span className="font-mono bg-gray-950 px-2 py-0.5 rounded text-[11px]">ID #{doc.id}</span>
                </div>
              </div>

              {/* Named Entities Card */}
              <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5 shadow-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-purple-400">
                    <Tag className="w-4 h-4" />
                    <span>Discovered Named Entities ({entities.length})</span>
                  </div>
                  <button
                    onClick={() => setActiveTab('graph')}
                    className="text-xs text-purple-400 hover:text-purple-300 flex items-center space-x-1"
                  >
                    <span>View in Graph</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>

                {loading ? (
                  <div className="py-6 flex items-center justify-center text-xs text-gray-400 space-x-2">
                    <span className="animate-spin w-4 h-4 border-2 border-purple-400 border-t-transparent rounded-full" />
                    <span>Loading entity intelligence...</span>
                  </div>
                ) : entities.length === 0 ? (
                  <p className="text-xs text-gray-500 italic py-2">No entities detected in this document.</p>
                ) : (
                  <div className="flex flex-wrap gap-2 max-h-60 overflow-y-auto">
                    {entities.map((ent, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-gray-950 border border-gray-800 text-xs font-medium text-gray-300 hover:border-gray-700 transition-colors"
                      >
                        <span className="w-2 h-2 rounded-full bg-purple-400 shrink-0" />
                        <span className="font-semibold text-white">{ent.text}</span>
                        <span className="text-[10px] text-gray-500 font-mono">[{ent.label}]</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex-1 h-full min-h-0">
              <KnowledgeGraph 
                graphData={graphData} 
                title={`Knowledge Network — ${doc.filename}`} 
              />
            </div>
          )}
        </div>

        {/* Right Pane (Chat Assistant) */}
        <div className="lg:col-span-5 h-full min-h-0 flex flex-col">
          <ChatBox docId={doc.id} docFilename={doc.filename} />
        </div>
      </div>
    </div>
  )
}
