const API_BASE = '';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Dashboard
  getDashboard: (start: string, end: string) =>
    fetchJson<any>(`/api/v1/data/dashboard?start=${start}&end=${end}`),

  getTimeSeries: (start: string, end: string, granularity = 'day') =>
    fetchJson<any>(`/api/v1/data/timeseries?start=${start}&end=${end}&granularity=${granularity}`),

  getGeoHeatmap: (start: string, end: string, precision = 2) =>
    fetchJson<any>(`/api/v1/data/geo?start=${start}&end=${end}&precision=${precision}`),

  searchEvents: (query: string, limit = 20) =>
    fetchJson<any>(`/api/v1/data/events?query=${encodeURIComponent(query)}&limit=${limit}`),

  health: () => fetchJson<any>('/api/v1/data/health'),

  // Agent
  chat: (message: string, history: any[] = [], sessionId?: string) =>
    fetchJson<any>('/api/v1/agent/chat', {
      method: 'POST',
      body: JSON.stringify({ message, history, session_id: sessionId }),
    }),

  listTools: () => fetchJson<any>('/api/v1/agent/tools'),
};
