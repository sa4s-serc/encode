import type { HistoryPoint } from '../types';

interface SparklineProps {
  history: HistoryPoint[];
}

function buildPath(values: number[]): string {
  const width = 160;
  const height = 34;
  const padding = 4;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;

  return values
    .map((value, index) => {
      const x = padding + (index * (width - padding * 2)) / Math.max(1, values.length - 1);
      const y = padding + (height - padding * 2) * (1 - (value - min) / range);
      return (index === 0 ? 'M' : 'L') + x.toFixed(2) + ' ' + y.toFixed(2);
    })
    .join(' ');
}

export function Sparkline({ history }: SparklineProps) {
  if (!history || history.length < 2) {
    return <div className="sparkline-empty">history builds after each scan</div>;
  }

  const debt = history.map(point => Number(point.energyDebtScore || 0));
  const cost = history.map(point => Number(point.costUsd || 0));

  return (
    <svg className="sparkline" viewBox="0 0 160 34">
      <path d={buildPath(cost)} className="sparkline-cost" />
      <path d={buildPath(debt)} className="sparkline-debt" />
    </svg>
  );
}
