import React, { useState, useEffect } from 'react'
import { Plus, Search, FileText, Calendar, ArrowRight, Sparkles, Network, Database, Layers, RefreshCw } from 'lucide-react'
import { api } from '../api'
import KnowledgeGraph from './KnowledgeGraph'
import UploadModal from './UploadModal'

export default function Dashboard({ onSelectDoc, activeTab = 'documents' }) {
  const [docs, setDocs] = useState([])
  const [globalGraph, setGlobalGraph] = useState(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [isUploadOpen, setIsUploadOpen] = useState(false)

  const loadData = async () => {
    setLoading(true)
    try {
      const [docList, graphRes] = await Promise.all([
        api.listDocuments().catch(() => []),
        api.getGlobalGraph().catch(() => ({ nodes: [], edges: [] }))
      ])
      setDocs(docList || [])
      setGlobalGraph(graphRes)
    } catch (err) {
      console.error('Error loading dashboard data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const filteredDocs = docs.filter(d => 
    d.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (d.summary && d.summary.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
      {/* Metrics Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5 backdrop-blur flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Document Library</p>
            <h3 className="text-2xl font-bold text-white mt-1">{docs.length} files</h3>
          </div>
          <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
            <FileText className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5 backdrop-blur flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Graph Entities</p>
            <h3 className="text-2xl font-bold text-purple-400 mt-1">
              {globalGraph?.nodes?.length || 0} nodes
            </h3>
          </div>
          <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <Network className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5 backdrop-blur flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Storage Engine</p>
            <h3 className="text-2xl font-bold text-emerald-400 mt-1">SQLite Local</h3>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Database className="w-6 h-6" />
          </div>
        </div>
      </div>

      {activeTab === 'graph' ? (
        /* Global Knowledge Graph View */
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">Cross-Document Knowledge Graph</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Multi-document entity co-occurrence network across your entire uploaded collection
              </p>
            </div>
            <button
              onClick={loadData}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs font-semibold text-gray-300 hover:text-white hover:border-gray-700 transition-all"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh Graph</span>
            </button>
          </div>
          <div className="h-[600px] w-full">
            <KnowledgeGraph 
              graphData={globalGraph} 
              title="Global Multi-Document Knowledge Graph" 
            />
          </div>
        </div>
      ) : (
        /* Document Library View */
        <div>
          {/* Controls Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search documents and summaries..."
                className="w-full bg-gray-900/90 border border-gray-800 rounded-xl py-2 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
              />
            </div>

            <div className="flex items-center space-x-3">
              <button
                onClick={() => setIsUploadOpen(true)}
                className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-sm font-semibold rounded-xl shadow-lg shadow-blue-500/20 transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>Upload Document</span>
              </button>
            </div>
          </div>

          {/* Document Grid */}
          {loading ? (
            <div className="py-20 text-center flex flex-col items-center justify-center">
              <span className="animate-spin w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full mb-3" />
              <p className="text-sm text-gray-400">Loading your knowledge base...</p>
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="border border-dashed border-gray-800 rounded-2xl p-12 text-center bg-gray-950/30">
              <div className="w-16 h-16 rounded-2xl bg-gray-900 border border-gray-800 flex items-center justify-center mx-auto text-gray-500 mb-4">
                <FileText className="w-8 h-8" />
              </div>
              <h3 className="text-base font-bold text-white">No documents found</h3>
              <p className="text-xs text-gray-400 max-w-md mx-auto mt-1 mb-6">
                Upload your first PDF, Word document, text file, or image to extract entities, build graphs, and query using AI.
              </p>
              <button
                onClick={() => setIsUploadOpen(true)}
                className="inline-flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold rounded-xl shadow-lg shadow-blue-500/20 transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>Upload Your First File</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredDocs.map((doc) => (
                <div
                  key={doc.id}
                  onClick={() => onSelectDoc(doc)}
                  className="bg-gray-900/60 hover:bg-gray-900 border border-gray-800 hover:border-blue-500/40 rounded-2xl p-5 cursor-pointer transition-all hover:shadow-xl hover:shadow-blue-500/5 group flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between mb-3">
                      <div className="w-10 h-10 rounded-xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-400 group-hover:bg-blue-600 group-hover:text-white transition-all">
                        <FileText className="w-5 h-5" />
                      </div>
                      <span className="text-[11px] font-mono text-gray-500 bg-gray-950 px-2 py-0.5 rounded border border-gray-800/80">
                        #{doc.id}
                      </span>
                    </div>

                    <h4 className="font-bold text-white text-base group-hover:text-blue-400 transition-colors line-clamp-1 mb-2">
                      {doc.filename}
                    </h4>

                    <p className="text-xs text-gray-400 line-clamp-3 leading-relaxed mb-4">
                      {doc.summary || "No executive summary available for this file."}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-gray-800/60 flex items-center justify-between text-xs text-gray-500">
                    <div className="flex items-center space-x-1.5">
                      <Calendar className="w-3.5 h-3.5" />
                      <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                    </div>
                    <span className="flex items-center space-x-1 text-blue-400 font-semibold group-hover:translate-x-1 transition-transform">
                      <span>Analyze</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={loadData}
      />
    </div>
  )
}
