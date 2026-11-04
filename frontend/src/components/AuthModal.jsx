import React, { useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { api } from '../api'
import { Wordmark } from './Navbar'

export default function AuthModal({ onAuthenticated }) {
  const [mode, setMode] = useState('login') // 'login' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const isSignup = mode === 'signup'

  const switchMode = (next) => {
    setMode(next)
    setError(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (isSignup) {
        await api.signup(email, password)
      }
      await api.login(email, password)
      onAuthenticated()
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <Wordmark size="text-3xl" />
          <p className="mt-3 text-sm text-ink-muted leading-relaxed">
            Upload documents, read their summaries, and ask questions answered from the text itself.
          </p>
        </div>

        <div className="panel p-6">
          <h1 className="font-serif text-xl font-semibold text-ink mb-5">
            {isSignup ? 'Create an account' : 'Sign in'}
          </h1>

          {error && (
            <div role="alert" className="mb-4 flex items-start gap-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-danger">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="label">Email</label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
              />
            </div>

            <div>
              <label htmlFor="password" className="label">Password</label>
              <input
                id="password"
                type="password"
                required
                autoComplete={isSignup ? 'new-password' : 'current-password'}
                minLength={isSignup ? 8 : undefined}
                maxLength={128}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
              />
              {isSignup && <p className="mt-1.5 text-xs text-ink-faint">At least 8 characters.</p>}
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full py-2.5">
              {loading && <span className="spinner w-4 h-4 border-surface/40 border-t-surface" />}
              {isSignup ? 'Create account' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="mt-5 text-center text-sm text-ink-muted">
          {isSignup ? 'Already have an account?' : 'New to DocuMind?'}{' '}
          <button
            type="button"
            onClick={() => switchMode(isSignup ? 'login' : 'signup')}
            className="font-medium text-accent hover:text-accent-hover underline underline-offset-2"
          >
            {isSignup ? 'Sign in' : 'Create an account'}
          </button>
        </p>
      </div>
    </div>
  )
}
