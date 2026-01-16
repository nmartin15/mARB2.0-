import React, { useState, useEffect } from 'react'
import axios from 'axios'
import Dashboard from './components/Dashboard'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function App() {
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchClaims()
  }, [])

  const fetchClaims = async () => {
    try {
      setLoading(true)
      const response = await axios.get(`${API_BASE}/api/v1/claims?limit=100`)
      setClaims(response.data.items || [])
      setError(null)
    } catch (err) {
      setError(err.message)
      console.error('Failed to fetch claims:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="App">
      <header className="App-header">
        <h1>mARB 2.0 - Risk Dashboard</h1>
        <p>Real-time Claim Risk Analysis</p>
      </header>
      {error && <div className="error-banner">{error}</div>}
      <Dashboard claims={claims} loading={loading} onRefresh={fetchClaims} />
    </div>
  )
}

export default App

