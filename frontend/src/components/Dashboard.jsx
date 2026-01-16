import React, { useState, useEffect } from 'react'
import axios from 'axios'
import WebSocketConnection from './WebSocketConnection'
import ClaimsTable from './ClaimsTable'
import RiskChart from './RiskChart'
import StatsCards from './StatsCards'
import './Dashboard.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function Dashboard({ claims, loading, onRefresh }) {
  const [riskScores, setRiskScores] = useState([])
  const [notifications, setNotifications] = useState([])
  const [stats, setStats] = useState({
    total: 0,
    highRisk: 0,
    mediumRisk: 0,
    lowRisk: 0,
  })

  useEffect(() => {
    calculateStats()
  }, [claims, riskScores])

  useEffect(() => {
    // Fetch risk scores for claims
    const fetchRiskScores = async () => {
      const scores = []
      for (const claim of claims.slice(0, 20)) {
        // Limit to first 20 to avoid too many requests
        try {
          const response = await axios.get(`${API_BASE}/api/v1/risk/${claim.id}`)
          scores.push({
            claimId: claim.id,
            score: response.data.overall_score || 0,
            level: response.data.risk_level || 'unknown',
          })
        } catch (err) {
          console.error(`Failed to fetch risk score for claim ${claim.id}:`, err)
        }
      }
      setRiskScores(scores)
    }

    if (claims.length > 0) {
      fetchRiskScores()
    }
  }, [claims])

  const calculateStats = () => {
    const total = claims.length
    const highRisk = riskScores.filter((s) => s.score >= 50).length
    const mediumRisk = riskScores.filter((s) => s.score >= 25 && s.score < 50).length
    const lowRisk = riskScores.filter((s) => s.score < 25).length

    setStats({
      total,
      highRisk,
      mediumRisk,
      lowRisk,
    })
  }

  const handleNotification = (notification) => {
    setNotifications((prev) => [notification, ...prev].slice(0, 10)) // Keep last 10
    if (notification.type === 'risk_score_calculated') {
      // Refresh risk scores when a new one is calculated
      onRefresh()
    }
  }

  return (
    <div className="dashboard">
      <WebSocketConnection onNotification={handleNotification} />
      
      <div className="dashboard-content">
        <StatsCards stats={stats} />
        
        <div className="dashboard-grid">
          <div className="dashboard-section">
            <h2>Risk Distribution</h2>
            <RiskChart riskScores={riskScores} />
          </div>
          
          <div className="dashboard-section">
            <h2>Recent Notifications</h2>
            <div className="notifications">
              {notifications.length === 0 ? (
                <p className="no-notifications">No recent notifications</p>
              ) : (
                notifications.map((notif, idx) => (
                  <div key={idx} className="notification">
                    <span className="notification-type">{notif.type}</span>
                    <span className="notification-message">{notif.message || JSON.stringify(notif.data)}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="dashboard-section">
          <div className="section-header">
            <h2>Claims</h2>
            <button onClick={onRefresh} className="refresh-button">
              Refresh
            </button>
          </div>
          <ClaimsTable claims={claims} riskScores={riskScores} loading={loading} />
        </div>
      </div>
    </div>
  )
}

export default Dashboard

