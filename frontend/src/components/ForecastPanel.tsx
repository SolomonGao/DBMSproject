import { Activity, Database, TrendingUp, Zap } from 'lucide-react';
import type { ForecastPoint, ThpForecastResult, TimeSeriesPoint } from '../types';

interface Props {
  data: TimeSeriesPoint[];
  title?: string;
  sourceLabel?: string;
  health?: any;
  forecastResult?: ThpForecastResult | null;
  forecastStartDate: string;
  historyStartDate: string;
  historyEndDate: string;
}

type DisplayForecastPoint = ForecastPoint & {
  riskLevel?: string;
  riskScore?: number;
};

function formatMetric(value: unknown, digits = 1) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 'n/a';
  return numeric.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function formatPercent(value: unknown) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 'n/a';
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(1)}%`;
}

function seriesCategory(seriesKey?: string) {
  const prefix = String(seriesKey || 'global').split(':')[0];
  if (prefix === 'country_pair') return 'country_pair';
  if (prefix === 'actor_pair') return 'actor_pair';
  if (prefix === 'country') return 'country';
  if (prefix === 'actor') return 'actor';
  if (prefix === 'cameo_root') return 'event_root';
  if (prefix === 'event_code') return 'event_code';
  return 'global';
}

function addDays(date: string, days: number) {
  const value = new Date(`${date}T00:00:00`);
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
}

function buildForecast(data: TimeSeriesPoint[], forecastStartDate: string): ForecastPoint[] {
  if (data.length === 0) return [];
  const recent = data.slice(-7);
  const previous = data.slice(-14, -7);
  const recentAvg = recent.reduce((sum, row) => sum + row.event_count, 0) / Math.max(1, recent.length);
  const previousAvg = previous.reduce((sum, row) => sum + row.event_count, 0) / Math.max(1, previous.length);
  const trend = previous.length > 0 ? (recentAvg - previousAvg) / Math.max(1, previous.length) : 0;

  return Array.from({ length: 7 }, (_, index) => {
    const median = Math.max(0, recentAvg + trend * (index + 1));
    const uncertainty = Math.max(4, median * (0.18 + index * 0.025));
    return {
      date: addDays(forecastStartDate, index),
      low: Math.max(0, median - uncertainty),
      median,
      high: median + uncertainty,
    };
  });
}

export default function ForecastPanel({
  data,
  title = 'Forecast Lab',
  sourceLabel = 'Baseline projection from GDELT time series',
  health,
  forecastResult,
  forecastStartDate,
  historyStartDate,
  historyEndDate,
}: Props) {
  const thpForecast: DisplayForecastPoint[] = (forecastResult?.forecast || []).map((point) => ({
    date: point.date,
    low: point.low_events,
    median: point.median_events ?? point.expected_events,
    high: point.high_events,
    riskLevel: point.risk_level,
    riskScore: point.risk_score,
  }));
  const forecast: DisplayForecastPoint[] = thpForecast.length > 0 ? thpForecast : buildForecast(data, forecastStartDate);
  const history = forecastResult?.recent_history?.length
    ? forecastResult.recent_history.map((point) => ({
        period: point.date,
        event_count: point.event_count,
        avg_goldstein: point.avg_goldstein,
        avg_tone: point.avg_tone,
      }))
    : data.slice(-14);
  const maxValue = Math.max(
    1,
    ...history.map((row) => row.event_count),
    ...forecast.map((row) => row.high)
  );
  const baselineNow = forecast[0]?.median || 0;
  const baselinePeak = forecast.reduce((peak, row) => (row.median > peak.median ? row : peak), forecast[0]);
  const dbHealthy = health?.db_status === 'healthy';
  const modelName = forecastResult?.model || 'baseline_frontend_fallback';
  const checkpointAvailable = Boolean(forecastResult?.checkpoint?.available);
  const checkpointError = forecastResult?.checkpoint?.error;
  const summary = forecastResult?.summary || {};
  const checkpoint = forecastResult?.checkpoint || {};
  const metadata = checkpoint.metadata || {};
  const evaluation = metadata.evaluation || {};
  const baselineComparison = checkpoint.baseline_comparison || {};
  const neuralMetrics = evaluation.neural_thp || {};
  const residualCalibration = evaluation.residual_calibration || {};
  const categoryKey = seriesCategory(checkpoint.series_key);
  const categoryMetrics = evaluation.per_category?.[categoryKey];
  const eventTypeKey = String(forecastResult?.target?.event_type || 'all').toLowerCase();
  const categoryEventMetrics = evaluation.per_category_event_type?.[`${categoryKey}:${eventTypeKey}`];
  const targetMetrics = categoryEventMetrics || categoryMetrics;
  const validationLabel = metadata.best_epoch
    ? `Best epoch ${metadata.best_epoch} of ${metadata.completed_epochs || metadata.epochs || 'n/a'}`
    : 'Validation backtest';

  return (
    <section className="panel forecast-lab">
      <div className="section-title-row">
        <div>
          <h3>{title}</h3>
          <p>{sourceLabel}</p>
        </div>
        <span className={`status-pill ${dbHealthy ? 'healthy' : 'muted'}`}>
          <Database size={13} />
          {dbHealthy ? `DB ${health?.db_latency_ms ?? '?'}ms` : 'DB status unknown'}
        </span>
      </div>

      {forecast.length === 0 ? (
        <div className="empty-state">
          Load historical data before {forecastStartDate} to generate a 7-day baseline forecast.
        </div>
      ) : (
        <>
          <div className="forecast-hero">
            <div>
              <span>Start-day median</span>
              <strong>{Math.round(baselineNow).toLocaleString()}</strong>
            </div>
            <div>
              <span>Peak forecast day</span>
              <strong>{summary.peak_risk_date || baselinePeak?.date || 'n/a'}</strong>
            </div>
            <div>
              <span>Model</span>
              <strong>{modelName.replace(/_/g, ' ')}</strong>
            </div>
          </div>

          <div className="mini-forecast-chart" aria-label="History and forecast chart">
            {[...history, ...forecast].map((point: any, index) => {
              const isFuture = 'median' in point;
              const value = isFuture ? point.median : point.event_count;
              const height = Math.max(4, (value / maxValue) * 100);
              return (
                <div className="forecast-bar-wrap" key={`${point.period || point.date}-${index}`}>
                  <div
                    className={`forecast-bar ${isFuture ? 'future' : ''}`}
                    style={{ height: `${height}%` }}
                    title={`${point.period || point.date}: ${Math.round(value).toLocaleString()}`}
                  />
                </div>
              );
            })}
          </div>

          <div className="forecast-strip">
            {forecast.map((point) => (
              <div className="forecast-day" key={point.date}>
                <span>{point.date.slice(5)}</span>
                <strong>{Math.round(point.median).toLocaleString()}</strong>
                <small>
                  {Math.round(point.low).toLocaleString()} - {Math.round(point.high).toLocaleString()}
                </small>
                {point.riskLevel && <small>{point.riskLevel} risk</small>}
              </div>
            ))}
          </div>

          {checkpointAvailable && (
            <div className="evaluation-panel" aria-label="Model evaluation metrics">
              <div className="evaluation-heading">
                <div>
                  <span>Model Evaluation</span>
                  <strong>Rolling validation backtest</strong>
                </div>
                <small>{validationLabel}</small>
              </div>
              <div className="evaluation-grid">
                <div>
                  <span>Overall THP MAE</span>
                  <strong>{formatMetric(baselineComparison.model_mae ?? neuralMetrics.mae, 1)}</strong>
                  <small>All validation series</small>
                </div>
                <div>
                  <span>Overall Baseline MAE</span>
                  <strong>{formatMetric(baselineComparison.baseline_mae, 1)}</strong>
                  <small>{String(baselineComparison.best_baseline || 'moving_avg_7').replace(/_/g, ' ')}</small>
                </div>
                <div>
                  <span>Overall Improvement</span>
                  <strong>{formatPercent(baselineComparison.mae_improvement_pct)}</strong>
                  <small>THP vs baseline</small>
                </div>
                <div>
                  <span>Target Event MAE</span>
                  <strong>{formatMetric(targetMetrics?.mae, 1)}</strong>
                  <small>
                    {categoryEventMetrics
                      ? `${categoryKey.replace(/_/g, ' ')} / ${eventTypeKey}`
                      : `${categoryKey.replace(/_/g, ' ')} validation group`}
                  </small>
                </div>
                <div>
                  <span>Target Event RMSE</span>
                  <strong>{formatMetric(targetMetrics?.rmse, 1)}</strong>
                  <small>Penalizes large errors</small>
                </div>
                <div>
                  <span>Validation Windows</span>
                  <strong>{targetMetrics?.samples?.toLocaleString?.() || 'n/a'}</strong>
                  <small>Held-out backtest windows</small>
                </div>
              </div>
              <p className="evaluation-note">
                Evaluation is computed on held-out historical windows. It tells us how THP performed when
                forecasting past periods before seeing the actual future values.
              </p>
            </div>
          )}

          <div className="forecast-meta">
            <span><Zap size={12} /> Forecast source: THP service + GDELT summary tables</span>
            <span><TrendingUp size={12} /> Input window: {historyStartDate} to {historyEndDate}</span>
            <span>
              <Activity size={12} />
              {checkpointAvailable
                ? 'Neural THP checkpoint loaded'
                : `Empirical THP fallback${checkpointError ? ` (${checkpointError})` : ''}`}
            </span>
          </div>
        </>
      )}
    </section>
  );
}
