# DocuMind Revamp Plan

## Goal
Transform DocuMind into a modern document intelligence platform with React frontend, interactive Cytoscape knowledge graphs, upgraded RAG with citations, Tesseract OCR, and zero-friction SQLite default.

## Tasks
- [ ] Task 1: Setup React + Vite frontend skeleton with Tailwind CSS, Lucide icons, and Cytoscape.js → Verify: `npm run build` succeeds and produces `frontend/dist/`.
- [ ] Task 2: Implement OCR service in backend for scanned PDFs and images (PNG/JPG) using PyMuPDF and pytesseract fallback → Verify: Python test extracts text from image sample.
- [ ] Task 3: Build Graph Engine in backend to generate document and cross-document entity co-occurrence networks → Verify: `GET /docs/{id}/graph` and `GET /docs/graph/global` return nodes and edges.
- [ ] Task 4: Upgrade RAG service with sliding window chunking, source chunk citations, and confidence scores → Verify: `POST /docs/{id}/chat` returns `{ answer, sources, confidence }`.
- [ ] Task 5: Configure FastAPI to mount and serve React SPA directly at `/` with SQLite default → Verify: Browsing `http://127.0.0.1:8000/` loads React UI with zero CORS errors.
- [ ] Task 6: Build React Dashboard (Document Library, Upload Modal with OCR, Global Graph Tab) → Verify: Upload file, view document list, and inspect global graph.
- [ ] Task 7: Build React Document Detail Page (Document Summary, Entities, Cytoscape Graph, and Cited RAG Chat) → Verify: Ask question in chat, verify cited snippet displays.
- [ ] Task 8: End-to-end verification and production build → Verify: Full flow test: login → upload image/PDF → graph view → chat citations.

## Done When
- [ ] Entire app runs on a single command without external database setup.
- [ ] Interactive knowledge graph renders nodes and relationships.
- [ ] RAG answers questions with cited source chunks.
- [ ] OCR processes scanned documents and images.
