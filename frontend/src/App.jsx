import React, { useState, useEffect, useCallback } from 'react'
import { api, isAuthenticated, UNAUTHORIZED_EVENT } from './api'
import Navbar from './components/Navbar'
import AuthModal from './components/AuthModal'
import Dashboard from './components/Dashboard'
import DocumentView from './components/DocumentView'
import AskView from './components/AskView'

export default function App() {
  const [authed, setAuthed] = useState(false)
  const [activeTab, setActiveTab] = useState('documents') // 'documents' | 'ask' | 'graph'
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(true)

  useEffect(() => {
    setAuthed(isAuthenticated())
    setCheckingAuth(false)

    // The API client clears an expired/invalid token and fires this event
    const handleUnauthorized = () => {
      setAuthed(false)
      setSelectedDoc(null)
    }
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized)
  }, [])

  const handleLogout = () => {
    api.logout()
    setAuthed(false)
    setSelectedDoc(null)
  }

  const goToLibrary = useCallback((tab) => {
    setSelectedDoc(null)
    if (typeof tab === 'string') setActiveTab(tab)
  }, [])

  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <span className="spinner w-6 h-6" aria-label="Loading" />
      </div>
    )
  }

  if (!authed) {
    return <AuthModal onAuthenticated={() => setAuthed(true)} />
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar
        activeTab={selectedDoc ? null : activeTab}
        onNavigate={goToLibrary}
        onLogout={handleLogout}
      />

      <main className="flex-1">
        {selectedDoc ? (
          <DocumentView doc={selectedDoc} onBack={goToLibrary} />
        ) : activeTab === 'ask' ? (
          <AskView />
        ) : (
          <Dashboard activeTab={activeTab} onSelectDoc={setSelectedDoc} />
        )}
      </main>
    </div>
  )
}
