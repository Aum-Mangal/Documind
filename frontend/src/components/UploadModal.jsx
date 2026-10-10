import React, { useState, useRef } from 'react'
import { UploadCloud, X, FileText, CheckCircle2, AlertCircle, Scan, Sparkles } from 'lucide-react'
import { api } from '../api'

export default function UploadModal({ isOpen, onClose, onUploadSuccess }) {
  const [dragActive, setDragActive] = useState(false)
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [statusMessage, setStatusMessage] = useState('')
  const inputRef = useRef(null)

  if (!isOpen) return null

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0])
    }
  }

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setUploading(true)
    setError(null)
    const isImage = file.name.match(/\.(png|jpg|jpeg|webp)$/i)
    setStatusMessage(isImage ? 'Running Tesseract OCR & extracting text...' : 'Parsing document & generating AI embeddings...')

    try {
      const res = await api.uploadDocument(file)
      setStatusMessage('Document intelligence complete!')
      setTimeout(() => {
        setUploading(false)
        setFile(null)
        onUploadSuccess(res)
        onClose()
      }, 700)
    } catch (err) {
      setError(err.message || 'Upload failed. Please try again.')
      setUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl overflow-hidden relative">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-800 bg-gray-950/40">
          <div className="flex items-center space-x-2">
            <UploadCloud className="w-5 h-5 text-blue-400" />
            <h3 className="text-base font-bold text-white">Upload & Analyze Document</h3>
          </div>
          <button
            onClick={onClose}
            disabled={uploading}
            className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 flex items-start space-x-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Drag and Drop Zone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
              dragActive 
                ? 'border-blue-500 bg-blue-500/10' 
                : file 
                  ? 'border-green-500/50 bg-green-500/5' 
                  : 'border-gray-700 hover:border-gray-600 bg-gray-950/30'
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              onChange={handleChange}
              accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
              className="hidden"
            />

            {file ? (
              <div className="flex flex-col items-center">
                <div className="w-12 h-12 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center justify-center text-green-400 mb-3">
                  <FileText className="w-6 h-6" />
                </div>
                <p className="text-sm font-semibold text-white max-w-xs truncate">{file.name}</p>
                <p className="text-xs text-gray-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
                <span className="text-xs text-blue-400 mt-2 hover:underline">Click to change file</span>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mb-3">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <p className="text-sm font-semibold text-white">Drag & drop your file here, or click to browse</p>
                <p className="text-xs text-gray-400 mt-1">Supports PDF, DOCX, TXT, PNG, and JPG</p>
              </div>
            )}
          </div>

          {/* Supported Format Pills */}
          <div className="flex flex-wrap items-center gap-2 mt-4 text-xs text-gray-400">
            <span className="text-gray-500 font-medium">Formats:</span>
            <span className="px-2 py-0.5 rounded bg-gray-800 text-gray-300">PDF</span>
            <span className="px-2 py-0.5 rounded bg-gray-800 text-gray-300">DOCX</span>
            <span className="px-2 py-0.5 rounded bg-gray-800 text-gray-300">TXT</span>
            <span className="px-2 py-0.5 rounded bg-purple-900/40 text-purple-300 border border-purple-800/40 flex items-center space-x-1">
              <Scan className="w-3 h-3" />
              <span>OCR Images (PNG/JPG)</span>
            </span>
          </div>

          {/* Upload progress status */}
          {uploading && (
            <div className="mt-5 p-4 rounded-xl bg-blue-950/30 border border-blue-900/50 flex items-center space-x-3">
              <div className="animate-spin w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full shrink-0" />
              <div className="flex-1">
                <p className="text-xs font-semibold text-blue-300">{statusMessage}</p>
                <p className="text-[11px] text-gray-400 mt-0.5">Extracting entities, building knowledge graph & chunking</p>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="mt-6 flex items-center justify-end space-x-3">
            <button
              onClick={onClose}
              disabled={uploading}
              className="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-xl shadow-lg shadow-blue-500/25 disabled:opacity-40 transition-all flex items-center space-x-2"
            >
              <Sparkles className="w-4 h-4" />
              <span>{uploading ? 'Processing...' : 'Upload & Analyze'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
