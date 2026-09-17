const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path) {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  return res.json()
}

export function getStations() {
  return request('/stations')
}

export function getLatest(stationId) {
  const qs = stationId ? `?station=${encodeURIComponent(stationId)}` : ''
  return request(`/telemetry/latest${qs}`)
}

export function getHistory(stationId, hours = 6) {
  return request(`/telemetry/history?station=${encodeURIComponent(stationId)}&hours=${hours}`)
}

export function getAnomalies(stationId) {
  const qs = stationId ? `?station=${encodeURIComponent(stationId)}` : ''
  return request(`/anomalies/latest${qs}`)
}