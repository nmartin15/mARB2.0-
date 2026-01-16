import React, { useEffect, useRef } from 'react'

const WS_BASE = import.meta.env.VITE_WS_BASE || 'ws://localhost:8000'

function WebSocketConnection({ onNotification }) {
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  useEffect(() => {
    const connect = () => {
      try {
        const ws = new WebSocket(`${WS_BASE}/ws/notifications`)
        wsRef.current = ws

        ws.onopen = () => {
          console.log('WebSocket connected')
          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
            reconnectTimeoutRef.current = null
          }
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (onNotification) {
              onNotification(data)
            }
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err)
          }
        }

        ws.onerror = (error) => {
          console.error('WebSocket error:', error)
        }

        ws.onclose = () => {
          console.log('WebSocket disconnected, reconnecting...')
          // Reconnect after 3 seconds
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, 3000)
        }
      } catch (err) {
        console.error('Failed to connect WebSocket:', err)
        // Retry after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, 3000)
      }
    }

    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [onNotification])

  return null // This component doesn't render anything
}

export default WebSocketConnection

