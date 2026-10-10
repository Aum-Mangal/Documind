import React from 'react'
import { Sparkles, LogOut, FileText, Network, Settings } from 'lucide-react'

export default function Navbar({ activeTab, setActiveTab, onLogout, userEmail, currentDoc, onBackToDashboard }) {
  return (
    <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3 cursor-pointer" onClick={onBackToDashboard}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent">
                DocuMind
              </span>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                AI Intelligence
              </span>
            </div>
            <p className="text-xs text-gray-500 hidden sm:block">Knowledge Graph & Semantic RAG</p>
          </div>
        </div>

        {currentDoc ? (
          <div className="hidden md:flex items-center space-x-2 text-sm text-gray-400">
            <button 
              onClick={onBackToDashboard}
              className="hover:text-white transition-colors"
            >
              Documents
            </button>
            <span>/</span>
            <span className="text-white font-medium max-w-[200px] truncate">
              {currentDoc.filename}
            </span>
          </div>
        ) : (
          <div className="flex items-center space-x-1 bg-gray-900/60 p-1 rounded-lg border border-gray-800">
            <button
              onClick={() => setActiveTab('documents')}
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                activeTab === 'documents'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Library</span>
            </button>
            <button
              onClick={() => setActiveTab('graph')}
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                activeTab === 'graph'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
              }`}
            >
              <Network className="w-4 h-4" />
              <span>Global Graph</span>
            </button>
          </div>
        )}

        <div className="flex items-center space-x-3">
          <button
            onClick={onLogout}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </div>
    </header>
  )
}
