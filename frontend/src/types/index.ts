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
  SOURCEURL?: string;
  EventRootCode?: string;
  NumSources?: number;
}

export interface CompareSeries {
  label: string;
  rows: TimeSeriesPoint[];
  total_events: number;
  avg_goldstein: number;
}

export interface CompareResult {
  left: CompareSeries;
  right: CompareSeries;
  event_type: string;
  start_date: string;
  end_date: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  thinking_steps?: ThinkingStep[];
  tools_used?: string[];
  sources?: string[];
}

export interface ThinkingStep {
  type: string;
  content?: string;
  data?: Record<string, any>;
}

export interface ApiResponse<T> {
  ok: boolean;
  error?: string;
  data?: T;
}
