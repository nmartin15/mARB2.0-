import React from 'react'
import './ClaimsTable.css'

function ClaimsTable({ claims, riskScores, loading }) {
  const getRiskScore = (claimId) => {
    const score = riskScores.find((s) => s.claimId === claimId)
    return score ? score.score : null
  }

  const getRiskLevel = (claimId) => {
    const score = riskScores.find((s) => s.claimId === claimId)
    return score ? score.level : 'unknown'
  }

  const getRiskClass = (level) => {
    const levelMap = {
      low: 'risk-low',
      medium: 'risk-medium',
      high: 'risk-high',
      critical: 'risk-critical',
      unknown: 'risk-unknown',
    }
    return levelMap[level] || 'risk-unknown'
  }

  if (loading) {
    return <div className="loading">Loading claims...</div>
  }

  if (claims.length === 0) {
    return <div className="no-claims">No claims found</div>
  }

  return (
    <div className="claims-table-container">
      <table className="claims-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Control Number</th>
            <th>Patient</th>
            <th>Provider</th>
            <th>Payer</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Risk Score</th>
            <th>Risk Level</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => {
            const score = getRiskScore(claim.id)
            const level = getRiskLevel(claim.id)
            return (
              <tr key={claim.id}>
                <td>{claim.id}</td>
                <td>{claim.claim_control_number || 'N/A'}</td>
                <td>{claim.patient_control_number || 'N/A'}</td>
                <td>{claim.provider?.name || 'N/A'}</td>
                <td>{claim.payer?.name || 'N/A'}</td>
                <td>${(claim.total_charge_amount || 0).toFixed(2)}</td>
                <td>
                  <span className={`status status-${claim.status?.toLowerCase() || 'unknown'}`}>
                    {claim.status || 'Unknown'}
                  </span>
                </td>
                <td>
                  {score !== null ? (
                    <span className={`risk-score ${getRiskClass(level)}`}>{score.toFixed(1)}</span>
                  ) : (
                    <span className="risk-score risk-unknown">-</span>
                  )}
                </td>
                <td>
                  <span className={`risk-badge ${getRiskClass(level)}`}>{level}</span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default ClaimsTable

