const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path, options) {
  const res = await fetch(`${BASE_URL}${path}`, options)
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

export function getHealthCurrent(stationId) {
  return request(`/stations/${encodeURIComponent(stationId)}/health/current`)
}

export function getHealthBreakdown(stationId, hours = 24) {
  return request(`/stations/${encodeURIComponent(stationId)}/health/breakdown?hours=${hours}`)
}

// --- Remote Management Action Layer -----------------------------------

export function postCommand(stationId, command) {
  return request(`/stations/${encodeURIComponent(stationId)}/commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(command),
  })
}

export function getCommands(stationId, limit = 20) {
  return request(`/stations/${encodeURIComponent(stationId)}/commands?limit=${limit}`)
}
