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
  getDashboard: (
    start: string,
    end: string,
    params: { region?: string; focus_type?: string; event_type?: string } = {}
  ) => {
    const qs = new URLSearchParams({ start, end });
    if (params.region) qs.set('region', params.region);
    if (params.focus_type) qs.set('focus_type', params.focus_type);
    if (params.event_type) qs.set('event_type', params.event_type);
    return fetchJson<any>(`/api/v1/data/dashboard?${qs.toString()}`);
  },

  getTimeSeries: (
    start: string,
    end: string,
    granularity = 'day',
    params: { region?: string; focus_type?: string; event_type?: string } = {}
  ) => {
    const qs = new URLSearchParams({ start, end, granularity });
    if (params.region) qs.set('region', params.region);
    if (params.focus_type) qs.set('focus_type', params.focus_type);
    if (params.event_type) qs.set('event_type', params.event_type);
    return fetchJson<any>(`/api/v1/data/timeseries?${qs.toString()}`);
  },

  getGeoHeatmap: (
    start: string,
    end: string,
    precision = 2,
    params: { region?: string; focus_type?: string; event_type?: string } = {}
  ) => {
    const qs = new URLSearchParams({ start, end, precision: String(precision) });
    if (params.region) qs.set('region', params.region);
    if (params.focus_type) qs.set('focus_type', params.focus_type);
    if (params.event_type) qs.set('event_type', params.event_type);
    return fetchJson<any>(`/api/v1/data/geo?${qs.toString()}`);
  },

  getForecast: (
    start: string,
    end: string,
    params: { region?: string; actor?: string; event_type?: string; forecast_days?: number } = {}
  ) => {
    const qs = new URLSearchParams({
      start,
      end,
      event_type: params.event_type || 'all',
      forecast_days: String(params.forecast_days || 7),
    });
    if (params.region) qs.set('region', params.region);
    if (params.actor) qs.set('actor', params.actor);
    return fetchJson<any>(`/api/v1/data/forecast?${qs.toString()}`);
  },

  searchEvents: (
    query: string,
    limit = 20,
    params: {
      time_hint?: string;
      start?: string;
      end?: string;
      location_hint?: string;
      lat?: number;
      lng?: number;
      precision?: number;
      focus_type?: string;
      event_type?: string;
    } = {}
  ) => {
    const qs = new URLSearchParams({
      query,
      limit: String(limit),
    });
    if (params.time_hint) qs.set('time_hint', params.time_hint);
    if (params.start) qs.set('start', params.start);
    if (params.end) qs.set('end', params.end);
    if (params.location_hint) qs.set('location_hint', params.location_hint);
    if (params.lat !== undefined) qs.set('lat', String(params.lat));
    if (params.lng !== undefined) qs.set('lng', String(params.lng));
    if (params.precision !== undefined) qs.set('precision', String(params.precision));
    if (params.focus_type) qs.set('focus_type', params.focus_type);
    if (params.event_type) qs.set('event_type', params.event_type);
    return fetchJson<any>(`/api/v1/data/events?${qs.toString()}`);
  },

  getTopEvents: (
    start: string,
    end: string,
    params: { region?: string; focus_type?: string; event_type?: string; limit?: number } = {}
  ) => {
    const qs = new URLSearchParams({
      start,
      end,
      limit: String(params.limit || 10),
    });
    if (params.region) qs.set('region', params.region);
    if (params.focus_type) qs.set('focus_type', params.focus_type);
    if (params.event_type) qs.set('event_type', params.event_type);
    return fetchJson<any>(`/api/v1/data/top-events?${qs.toString()}`);
  },

  getEventDetail: (fingerprint: string) =>
    fetchJson<any>(`/api/v1/data/events/${encodeURIComponent(fingerprint)}`),

  compareEntities: (start: string, end: string, left: string, right: string, eventType = 'any') =>
    fetchJson<any>(
      `/api/v1/data/compare?start=${start}&end=${end}&left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}&event_type=${encodeURIComponent(eventType)}`
    ),

  getCountryPairTrends: (start: string, end: string, countryA: string, countryB: string) =>
    fetchJson<any>(
      `/api/v1/data/country-pair?start=${start}&end=${end}&country_a=${encodeURIComponent(countryA)}&country_b=${encodeURIComponent(countryB)}`
    ),

  health: () => fetchJson<any>('/api/v1/data/health'),

  // Agent
  chat: (message: string, history: any[] = [], sessionId?: string) =>
    fetchJson<any>('/api/v1/agent/chat', {
      method: 'POST',
      body: JSON.stringify({ message, history, session_id: sessionId }),
    }),

  listTools: () => fetchJson<any>('/api/v1/agent/tools'),
};
