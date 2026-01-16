import React from 'react'
import './StatsCards.css'

function StatsCards({ stats }) {
  return (
    <div className="stats-cards">
      <div className="stat-card">
        <div className="stat-value">{stats.total}</div>
        <div className="stat-label">Total Claims</div>
      </div>
      <div className="stat-card stat-low">
        <div className="stat-value">{stats.lowRisk}</div>
        <div className="stat-label">Low Risk</div>
      </div>
      <div className="stat-card stat-medium">
        <div className="stat-value">{stats.mediumRisk}</div>
        <div className="stat-label">Medium Risk</div>
      </div>
      <div className="stat-card stat-high">
        <div className="stat-value">{stats.highRisk}</div>
        <div className="stat-label">High Risk</div>
      </div>
    </div>
  )
}

export default StatsCards

