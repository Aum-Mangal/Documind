import React, { useState, useRef, useEffect } from 'react'
import { UploadCloud, X, FileText, AlertCircle } from 'lucide-react'
import { api } from '../api'

const ACCEPTED = '.pdf,.docx,.txt,.png,.jpg,.jpeg,.webp'
const IMAGE_PATTERN = /\.(png|jpe?g|webp)$/i

export default function UploadModal({ isOpen, onClose, onUploadSuccess }) {
  const [dragActive, setDragActive] = useState(false)
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  // Start fresh every time the dialog opens
  useEffect(() => {
    if (isOpen) {
      setFile(null)
      setError(null)
      setDragActive(false)
    }
  }, [isOpen])

  // Escape closes the dialog (but not mid-upload)
  useEffect(() => {
    if (!isOpen) return
    const onKey = (e) => {
      if (e.key === 'Escape' && !uploading) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isOpen, uploading, onClose])

  if (!isOpen) return null

  const pickFile = (picked) => {
    if (picked) {
      setFile(picked)
      setError(null)
    }
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true)
    else if (e.type === 'dragleave' && !e.currentTarget.contains(e.relatedTarget)) setDragActive(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    pickFile(e.dataTransfer.files?.[0])
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await api.uploadDocument(file)
      onUploadSuccess()
      onClose()
    } catch (err) {
      setError(err.message || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const isImage = file && IMAGE_PATTERN.test(file.name)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40 animate-fade-in"
      onMouseDown={(e) => { if (e.target === e.currentTarget && !uploading) onClose() }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-title"
        className="w-full max-w-lg rounded-lg border border-line bg-surface shadow-raised animate-slide-up"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <h2 id="upload-title" className="font-serif text-lg font-semibold text-ink">Upload a document</h2>
          <button onClick={onClose} disabled={uploading} className="btn-ghost p-1.5" aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5">
          {error && (
            <div role="alert" className="mb-4 flex items-start gap-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-danger">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => !uploading && inputRef.current?.click()}
            onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !uploading) { e.preventDefault(); inputRef.current?.click() } }}
            role="button"
            tabIndex={0}
            aria-label="Choose a file to upload"
            className={`rounded-lg border-2 border-dashed px-6 py-10 text-center cursor-pointer transition-colors ${
              dragActive ? 'border-accent bg-accent-soft/60' : 'border-line-strong bg-paper hover:bg-sunken/60'
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              onChange={(e) => pickFile(e.target.files?.[0])}
              accept={ACCEPTED}
              className="hidden"
            />

            {file ? (
              <div className="flex flex-col items-center">
                <FileText className="w-7 h-7 text-accent mb-2" />
                <p className="text-sm font-medium text-ink max-w-xs truncate">{file.name}</p>
                <p className="mt-0.5 text-xs text-ink-faint">{(file.size / 1024).toFixed(1)} KB · click to choose another</p>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <UploadCloud className="w-7 h-7 text-ink-faint mb-2" />
                <p className="text-sm text-ink">
                  <span className="font-medium text-accent">Choose a file</span> or drag it here
                </p>
                <p className="mt-1 text-xs text-ink-faint">PDF, DOCX, TXT, or an image (PNG, JPG, WEBP) to read with OCR</p>
              </div>
            )}
          </div>

          {uploading && (
            <p className="mt-4 flex items-center gap-2 text-sm text-ink-muted" aria-live="polite">
              <span className="spinner w-4 h-4" />
              {isImage ? 'Reading text from the image…' : 'Extracting text and writing a summary…'} This can take a minute for long files.
            </p>
          )}

          <div className="mt-5 flex items-center justify-end gap-2">
            <button onClick={onClose} disabled={uploading} className="btn-ghost">Cancel</button>
            <button onClick={handleUpload} disabled={!file || uploading} className="btn-primary">
              {uploading ? 'Uploading…' : 'Upload'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
