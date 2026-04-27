import { useMemo } from 'react';
import { TrendingUp, TrendingDown, Activity, Users, Globe, Newspaper } from 'lucide-react';
import type { DashboardData } from '../types';

interface Props {
  data: DashboardData | null;
}

export default function StatsCards({ data }: Props) {
  const stats = useMemo(() => {
    if (!data) return [];
    const summary = data.summary_stats?.data?.[0] || {};
    return [
      {
        label: 'Total Events',
        value: summary.total_events ?? 0,
        icon: Activity,
        color: '#2563eb',
      },
      {
        label: 'Unique Actors',
        value: summary.unique_actors ?? 0,
        icon: Users,
        color: '#7c3aed',
      },
      {
        label: 'Total Articles',
        value: summary.total_articles ?? 0,
        icon: Newspaper,
        color: '#059669',
      },
      {
        label: 'Avg Goldstein',
        value: summary.avg_goldstein?.toFixed(2) ?? 'N/A',
        icon: Globe,
        color: summary.avg_goldstein < 0 ? '#dc2626' : '#2563eb',
      },
    ];
  }, [data]);

  if (!data) return null;

  return (
    <div className="stats-row">
      {stats.map((s) => {
        const Icon = s.icon;
        return (
          <div key={s.label} className="stat-card">
            <div className="label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icon size={14} color={s.color} />
              {s.label}
            </div>
            <div className="value" style={{ color: s.color }}>
              {typeof s.value === 'number' ? s.value.toLocaleString() : s.value}
            </div>
          </div>
        );
      })}
    </div>
  );
}
