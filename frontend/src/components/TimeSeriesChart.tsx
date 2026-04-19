import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { TimeSeriesPoint } from '../types';

interface Props {
  data: TimeSeriesPoint[];
  title?: string;
}

export default function TimeSeriesChart({ data, title = 'Event Trends' }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
    }

    const periods = data.map((d) => d.period);
    const eventCounts = data.map((d) => d.event_count);
    const conflictPcts = data.map((d) => d.conflict_pct ?? 0);

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
      },
      legend: {
        data: ['Event Count', 'Conflict %'],
        bottom: 0,
      },
      grid: {
        left: 60,
        right: 60,
        top: 40,
        bottom: 40,
      },
      xAxis: {
        type: 'category',
        data: periods,
        axisLabel: { rotate: 45, fontSize: 11 },
      },
      yAxis: [
        {
          type: 'value',
          name: 'Events',
          position: 'left',
        },
        {
          type: 'value',
          name: 'Conflict %',
          position: 'right',
          min: 0,
          max: 100,
          axisLabel: { formatter: '{value}%' },
        },
      ],
      series: [
        {
          name: 'Event Count',
          type: 'bar',
          data: eventCounts,
          itemStyle: { color: '#3b82f6' },
          barMaxWidth: 40,
        },
        {
          name: 'Conflict %',
          type: 'line',
          yAxisIndex: 1,
          data: conflictPcts,
          smooth: true,
          itemStyle: { color: '#ef4444' },
          lineStyle: { width: 3 },
          symbol: 'circle',
          symbolSize: 6,
        },
      ],
    };

    chartInstance.current.setOption(option);

    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [data]);

  return (
    <div className="panel">
      <h3>{title}</h3>
      <div ref={chartRef} style={{ width: '100%', height: 320 }} />
    </div>
  );
}
