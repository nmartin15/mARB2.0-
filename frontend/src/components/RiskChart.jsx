import React from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'
import './RiskChart.css'

const COLORS = {
  low: '#4caf50',
  medium: '#ff9800',
  high: '#f44336',
  critical: '#9c27b0',
  unknown: '#9e9e9e',
}

function RiskChart({ riskScores }) {
  const data = [
    {
      name: 'Low Risk',
      value: riskScores.filter((s) => s.score < 25).length,
      color: COLORS.low,
    },
    {
      name: 'Medium Risk',
      value: riskScores.filter((s) => s.score >= 25 && s.score < 50).length,
      color: COLORS.medium,
    },
    {
      name: 'High Risk',
      value: riskScores.filter((s) => s.score >= 50 && s.score < 75).length,
      color: COLORS.high,
    },
    {
      name: 'Critical Risk',
      value: riskScores.filter((s) => s.score >= 75).length,
      color: COLORS.critical,
    },
  ].filter((item) => item.value > 0)

  if (data.length === 0) {
    return <div className="no-data">No risk score data available</div>
  }

  return (
    <div className="risk-chart">
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

export default RiskChart

