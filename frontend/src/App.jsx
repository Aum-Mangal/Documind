import React, { useState, useEffect } from 'react'
import { api, isAuthenticated } from './api'
import Navbar from './components/Navbar'
import AuthModal from './components/AuthModal'
import Dashboard from './components/Dashboard'
import DocumentView from './components/DocumentView'

export default function App() {
  const [authed, setAuthed] = useState(false)
  const [activeTab, setActiveTab] = useState('documents') // 'documents' | 'graph'
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(true)

  useEffect(() => {
    setAuthed(isAuthenticated())
    setCheckingAuth(false)
  }, [])

  const handleLogout = () => {
    api.logout()
    setAuthed(false)
    setSelectedDoc(null)
  }

  if (checkingAuth) {
    return (
      <div className="min-h-screen bg-[#0B0F19] flex items-center justify-center">
        <span className="animate-spin w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!authed) {
    return <AuthModal onAuthenticated={() => setAuthed(true)} />
  }

  return (
    <div className="min-h-screen bg-[#0B0F19] text-gray-100 flex flex-col font-['Plus_Jakarta_Sans',sans-serif]">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onLogout={handleLogout}
        currentDoc={selectedDoc}
        onBackToDashboard={() => setSelectedDoc(null)}
      />

      <main className="flex-1 overflow-x-hidden">
        {selectedDoc ? (
          <DocumentView
            doc={selectedDoc}
            onBack={() => setSelectedDoc(null)}
          />
        ) : (
          <Dashboard
            activeTab={activeTab}
            onSelectDoc={(doc) => setSelectedDoc(doc)}
          />
        )}
      </main>
    </div>
  )
}
