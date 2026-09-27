// Day 1 placeholder — full dashboard UI built in Week 11
// This just shows the backend is connected

import { useEffect, useState } from 'react'

interface HealthStatus {
  status: string
  app: string
  version: string
  environment: string
}

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/health`)
      .then(r => r.json())
      .then(setHealth)
      .catch(() => setError('Cannot reach backend'))
  }, [])

  return (
    <div style={{ textAlign: 'center', padding: '2rem' }}>
      <h1 style={{ fontSize: '2.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
        🎙️ VoxAI
      </h1>
      <p style={{ color: '#94a3b8', marginBottom: '2rem' }}>
        AI Voice Operations Platform — Week 1 Foundation
      </p>

      <div style={{
        background: '#1e1e2e',
        border: '1px solid #334155',
        borderRadius: '12px',
        padding: '1.5rem',
        maxWidth: '400px',
        margin: '0 auto',
      }}>
        <p style={{ color: '#64748b', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
          Backend Health Check
        </p>

        {error && (
          <p style={{ color: '#f87171' }}>❌ {error}</p>
        )}

        {health && (
          <div style={{ textAlign: 'left' }}>
            <p style={{ color: '#4ade80', marginBottom: '0.5rem' }}>
              ✅ Backend is running
            </p>
            <pre style={{
              background: '#0f172a',
              padding: '1rem',
              borderRadius: '8px',
              fontSize: '0.8rem',
              color: '#94a3b8',
              overflow: 'auto',
            }}>
              {JSON.stringify(health, null, 2)}
            </pre>
          </div>
        )}

        {!health && !error && (
          <p style={{ color: '#94a3b8' }}>Checking backend...</p>
        )}
      </div>

      <p style={{ marginTop: '2rem', color: '#475569', fontSize: '0.8rem' }}>
        Full dashboard UI → Week 11
      </p>
    </div>
  )
}
