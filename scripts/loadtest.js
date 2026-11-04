// k6 load test for a running DocuMind stack. No LLM calls are made:
//   - "browse":        list documents and conversations
//   - "cached answer": a question asked before, served from the answer cache
//   - "search":        a new, unrelated question each time; runs query embedding, hybrid search
//                      and reranking, then declines below the relevance threshold without the LLM
//
//   docker run --rm -i -e BASE=http://host.docker.internal:8000 grafana/k6:1.8.2 run - < scripts/loadtest.js
//
// Each virtual user signs up its own account (so per-user chat limits aren't shared); the
// stack needs SIGNUP_PER_HOUR above the number of users, as the dev compose file sets.
import http from 'k6/http'
import { check, sleep } from 'k6'
import { Trend } from 'k6/metrics'

const BASE = __ENV.BASE || 'http://127.0.0.1:8000'
const USERS = Number(__ENV.USERS || 10)

const browse = new Trend('latency_browse', true)
const cached = new Trend('latency_cached_answer', true)
const search = new Trend('latency_search', true)

export const options = {
  scenarios: {
    steady: { executor: 'constant-vus', vus: USERS, duration: __ENV.DURATION || '2m' }
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    latency_browse: ['p(95)<500'],
    latency_cached_answer: ['p(95)<500'],
    latency_search: ['p(95)<3000']
  },
  setupTimeout: '5m'
}

const json = (token) => ({ headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) } })

const NOTE = 'Load test note. The Lisbon office signed a maintenance contract with Marisol Transportes. '.repeat(20)

export function setup() {
  const run = Date.now()
  const tokens = []
  for (let i = 0; i < USERS; i++) {
    const email = `load-${run}-${i}@documind.dev`
    http.post(`${BASE}/api/auth/signup`, JSON.stringify({ email, password: 'load-test-pass' }), json())
    const token = http.post(`${BASE}/api/auth/login`, JSON.stringify({ email, password: 'load-test-pass' }), json()).json('access_token')
    const auth = { Authorization: `Bearer ${token}` }
    http.post(`${BASE}/api/documents`, { file: http.file(`${NOTE} user ${i}`, `note-${i}.txt`, 'text/plain') }, { headers: auth })
    tokens.push(token)
  }
  // Wait for every user's document to be processed
  for (const token of tokens) {
    for (let t = 0; t < 120; t++) {
      const docs = http.get(`${BASE}/api/documents`, json(token)).json()
      if (docs.length && docs.every(d => d.status === 'ready')) break
      sleep(1)
    }
    // Prime the cache with an answer that needs no LLM (declined as unrelated)
    http.post(`${BASE}/api/chat`, JSON.stringify({ question: 'What is the boiling point of mercury?' }), json(token))
  }
  return { tokens }
}

export default function (data) {
  const token = data.tokens[(__VU - 1) % data.tokens.length]

  let r = http.get(`${BASE}/api/documents`, json(token))
  check(r, { 'documents 200': res => res.status === 200 })
  browse.add(r.timings.duration)
  r = http.get(`${BASE}/api/conversations`, json(token))
  check(r, { 'conversations 200': res => res.status === 200 })
  browse.add(r.timings.duration)

  r = http.post(`${BASE}/api/chat`, JSON.stringify({ question: 'What is the boiling point of mercury?' }), json(token))
  check(r, { 'cached answer': res => res.status === 200 && res.json('cached') === true })
  cached.add(r.timings.duration)

  r = http.post(`${BASE}/api/chat`, JSON.stringify({ question: `How tall is mountain number ${__VU}-${__ITER}?` }), json(token))
  check(r, { 'search answered': res => res.status === 200 && res.json('cached') === false })
  search.add(r.timings.duration)

  // Two questions per iteration: stay under the default 20 questions a minute per user
  sleep(7)
}
