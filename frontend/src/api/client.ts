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
  // Dashboard (direct data endpoints)
  getDashboard: (start: string, end: string) =>
    fetchJson<any>(`/api/v1/data/dashboard?start=${start}&end=${end}`),

  getTimeSeries: (start: string, end: string, granularity = 'day') =>
    fetchJson<any>(`/api/v1/data/timeseries?start=${start}&end=${end}&granularity=${granularity}`),

  getGeoHeatmap: (start: string, end: string, precision = 2) =>
    fetchJson<any>(`/api/v1/data/geo?start=${start}&end=${end}&precision=${precision}`),

  searchEvents: (query: string, limit = 20) =>
    fetchJson<any>(`/api/v1/data/events?query=${encodeURIComponent(query)}&limit=${limit}`),

  health: () => fetchJson<any>('/api/v1/data/health'),

  // AI Analyze (Planner + Executor)
  analyze: (query: string, llmConfig?: any) =>
    fetchJson<any>('/api/v1/analyze', {
      method: 'POST',
      body: JSON.stringify({ query, llm_config: llmConfig }),
    }),

  // AI Report (delayed load)
  generateReport: (data: any, prompt?: string, llmConfig?: any) =>
    fetchJson<any>('/api/v1/analyze/report', {
      method: 'POST',
      body: JSON.stringify({ data, prompt, llm_config: llmConfig }),
    }),
};
