export interface DashboardData {
  daily_trend: { data: any[]; count: number };
  top_actors: { data: any[]; count: number };
  geo_distribution: { data: any[]; count: number };
  event_types: { data: any[]; count: number };
  summary_stats: { data: any[]; count: number };
  _meta: { elapsed_ms: number; start_date: string; end_date: string };
}

export interface TimeSeriesPoint {
  period: string;
  event_count: number;
  conflict_pct?: number;
  cooperation_pct?: number;
  avg_goldstein?: number;
  avg_tone?: number;
}

export interface GeoPoint {
  lat: number;
  lng: number;
  intensity: number;
  avg_conflict?: number;
  sample_location?: string;
}

export interface EventItem {
  GlobalEventID: number;
  SQLDATE: string;
  Actor1Name?: string;
  Actor2Name?: string;
  EventCode?: string;
  GoldsteinScale?: number;
  AvgTone?: number;
  NumArticles?: number;
  ActionGeo_FullName?: string;
  ActionGeo_CountryCode?: string;
  ActionGeo_Lat?: number;
  ActionGeo_Long?: number;
  fingerprint?: string;
  headline?: string;
  summary?: string;
  event_type_label?: string;
  severity_score?: number;
  SOURCEURL?: string;
  key_actors?: string;
  location_name?: string;
  location_country?: string;
}

export interface GeoEventPoint {
  GlobalEventID: number;
  SQLDATE: string;
  Actor1Name?: string;
  Actor2Name?: string;
  EventCode?: string;
  GoldsteinScale?: number;
  AvgTone?: number;
  NumArticles?: number;
  ActionGeo_FullName?: string;
  ActionGeo_CountryCode?: string;
  lat: number;
  lng: number;
  fingerprint?: string;
  headline?: string;
  summary?: string;
  event_type_label?: string;
}

export interface FilterState {
  startDate: string;
  endDate: string;
  location: string;
  locationExact: string;
  actor: string;
  actorExact: string;
  eventType: string;
  keyword: string;
}

// Forecast types
export interface ForecastPoint {
  date: string;
  low: number;
  median: number;
  high: number;
}

export interface ThpForecastPoint {
  date: string;
  expected_events: number;
  low_events: number;
  median_events: number;
  high_events: number;
  risk_score?: number;
  risk_level?: string;
  hawkes_excitation?: number;
}

export interface ThpForecastResult {
  model: string;
  ok: boolean;
  error?: string;
  target?: Record<string, any>;
  summary?: Record<string, any>;
  forecast?: ThpForecastPoint[];
  checkpoint?: Record<string, any>;
  recent_history?: Array<{
    date: string;
    event_count: number;
    avg_goldstein?: number;
    avg_tone?: number;
  }>;
  attention_context?: Array<Record<string, any>>;
  _meta?: Record<string, any>;
}

// AI Analyze types
export interface LLMConfig {
  provider: string;
  api_key: string;
  model?: string;
  base_url?: string;
}

export interface QueryStep {
  type: string;
  params: Record<string, any>;
}

export interface QueryPlan {
  intent: string;
  thinking?: string;
  time_range?: { start: string; end: string };
  steps: QueryStep[];
  visualizations: string[];
  report_prompt?: string;
  notice?: string;
}

export interface ReportResult {
  summary: string;
  key_findings: string[];
}

export interface Phase {
  name: string;
  status: "pending" | "running" | "completed";
  detail?: string;
  elapsed_ms?: number;
}

export interface AnalyzeResponse {
  ok: boolean;
  query: string;
  plan: QueryPlan;
  data: Record<string, { type: string; data: any; error?: string }>;
  report?: ReportResult;
  elapsed_ms?: number;
  phases?: Phase[];
  error?: string;
}

export interface ApiResponse<T> {
  ok: boolean;
  error?: string;
  data?: T;
}
