import { Download, FileText } from 'lucide-react';
import type { DashboardData, EventItem, TimeSeriesPoint } from '../types';

interface Props {
  dashboard: DashboardData | null;
  timeSeries: TimeSeriesPoint[];
  events: EventItem[];
  startDate: string;
  endDate: string;
  region?: string;
  eventType?: string;
}

function codedLabel(value: unknown, fallback: string) {
  const text = String(value || '').trim();
  return text && text.toLowerCase() !== 'unknown' ? text : fallback;
}

export default function ReportExport({
  dashboard,
  timeSeries,
  events,
  startDate,
  endDate,
  region,
  eventType,
}: Props) {
  const buildMarkdown = () => {
    const summary = dashboard?.summary_stats?.data?.[0] || {};
    const peakDay = [...timeSeries].sort((a, b) => b.event_count - a.event_count)[0];
    const topActors = (dashboard?.top_actors?.data || [])
      .slice(0, 5)
      .map((actor: any, index: number) => `${index + 1}. ${codedLabel(actor.actor, 'Actor not coded')}: ${actor.event_count}`)
      .join('\n');
    const eventLines = events
      .slice(0, 5)
      .map((event) => {
        const actor = codedLabel(event.Actor1Name, 'Actor not coded');
        const target = codedLabel(event.Actor2Name, 'No second actor coded');
        return `- ${event.SQLDATE}: ${actor} / ${target} (${event.GoldsteinScale ?? 'n/a'})`;
      })
      .join('\n');

    return `# GDELT Analysis Report

Date range: ${startDate} to ${endDate}
Focus: ${region || 'All regions'} / ${eventType || 'All event types'}

## Summary
- Total events: ${summary.total_events?.toLocaleString?.() || 'n/a'}
- Unique actors: ${summary.unique_actors?.toLocaleString?.() || 'n/a'}
- Avg Goldstein: ${summary.avg_goldstein ?? 'n/a'}
- Peak day: ${peakDay?.period || 'n/a'} (${peakDay?.event_count?.toLocaleString?.() || 0} events)

## Top Actors
${topActors || 'No actor data loaded.'}

## Representative Events
${eventLines || 'No event data loaded.'}

## Notes
Generated from the dashboard state. Forecast values shown in the UI are baseline projections unless a dedicated THP forecast endpoint is connected.
`;
  };

  const downloadReport = () => {
    const blob = new Blob([buildMarkdown()], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `gdelt-report-${startDate}-${endDate}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <button className="secondary-action" onClick={downloadReport}>
      <Download size={14} />
      Export Report
      <FileText size={14} />
    </button>
  );
}
