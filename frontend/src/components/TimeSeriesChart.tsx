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

    const periods = data.map((d) => d.period.slice(5)); // Show MM-DD only
    const eventCounts = data.map((d) => d.event_count);
    const conflictPcts = data.map((d) => d.conflict_pct ?? 0);

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any) => {
          const idx = params[0]?.dataIndex ?? 0;
          const fullDate = data[idx]?.period ?? '';
          let html = `<div style="font-weight:600;margin-bottom:4px">${fullDate}</div>`;
          params.forEach((p: any) => {
            html += `<div style="display:flex;align-items:center;gap:6px">
              <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${p.color}"></span>
              <span>${p.seriesName}:</span>
              <span style="font-weight:600">${p.value.toLocaleString()}${p.seriesName.includes('%') ? '%' : ''}</span>
            </div>`;
          });
          return html;
        },
      },
      legend: {
        data: ['Event Count', 'Conflict Rate'],
        bottom: 0,
        textStyle: { fontSize: 12 },
      },
      grid: {
        left: 56,
        right: 56,
        top: 48,
        bottom: 72,
      },
      dataZoom: [
        {
          type: 'inside',
          start: 0,
          end: 100,
        },
        {
          type: 'slider',
          start: 0,
          end: 100,
          bottom: 28,
          height: 18,
          showDetail: false,
        },
      ],
      xAxis: {
        type: 'category',
        data: periods,
        axisLabel: {
          fontSize: 11,
          rotate: 35,
          interval: Math.max(0, Math.floor(periods.length / 8)),
        },
        axisTick: { alignWithLabel: true },
      },
      yAxis: [
        {
          type: 'value',
          name: 'Events',
          position: 'left',
          axisLabel: { fontSize: 11 },
          nameTextStyle: { fontSize: 12, padding: [0, 0, 0, -30] },
          splitLine: { lineStyle: { color: '#f0f0f0' } },
        },
        {
          type: 'value',
          name: 'Conflict %',
          position: 'right',
          min: 0,
          max: 100,
          axisLabel: { formatter: '{value}%', fontSize: 11 },
          nameTextStyle: { fontSize: 12, padding: [0, -30, 0, 0] },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'Event Count',
          type: 'bar',
          data: eventCounts,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#60a5fa' },
              { offset: 1, color: '#2563eb' },
            ]),
            borderRadius: [4, 4, 0, 0],
          },
          barMaxWidth: 28,
          animationDelay: (idx: number) => idx * 20,
        },
        {
          name: 'Conflict Rate',
          type: 'line',
          yAxisIndex: 1,
          data: conflictPcts,
          smooth: true,
          symbol: 'circle',
          symbolSize: 7,
          itemStyle: { color: '#ef4444', borderWidth: 2, borderColor: '#fff' },
          lineStyle: { width: 3, shadowColor: 'rgba(239,68,68,0.3)', shadowBlur: 8 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(239,68,68,0.15)' },
              { offset: 1, color: 'rgba(239,68,68,0)' },
            ]),
          },
        },
      ],
      animationEasing: 'elasticOut',
      animationDelayUpdate: (idx: number) => idx * 5,
    };

    chartInstance.current.setOption(option, true);

    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [data]);

  return (
    <div className="panel">
      <h3>{title}</h3>
      <div ref={chartRef} style={{ width: '100%', height: 460 }} />
    </div>
  );
}
