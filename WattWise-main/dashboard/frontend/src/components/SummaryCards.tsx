import type { ScanResult } from '../types';
import { formatCurrencyCompact, formatKg, formatKwh } from '../utils/format';

interface SummaryCardsProps {
  data: ScanResult;
}

export function SummaryCards({ data }: SummaryCardsProps) {
  return (
    <section className="summary-grid">
      <div className="summary-card">
        <div className="summary-value">{formatKwh(data.totalKwh)}</div>
        <div className="summary-label">kWh / year</div>
        <div className="summary-sub">at configured call rates</div>
      </div>
      <div className="summary-card summary-card-warn">
        <div className="summary-value">{formatCurrencyCompact(data.totalCostUsd)}</div>
        <div className="summary-label">AWS cost / year</div>
        <div className="summary-sub">us-east-1 · ₹{Number(data.config.awsRateKwh).toFixed(2)}/kWh</div>
      </div>
      <div className="summary-card">
        <div className="summary-value">{formatKg(data.totalCo2Kg)} kg</div>
        <div className="summary-label">CO₂ / year</div>
        <div className="summary-sub">{Number(data.config.co2KgPerKwh).toFixed(1)} kg/kWh grid avg</div>
      </div>
      <div className="summary-card summary-card-positive">
        <div className="summary-value">{formatCurrencyCompact(data.potentialSavingUsd)}</div>
        <div className="summary-label">potential saving</div>
        <div className="summary-sub">if top 5 hotspots are addressed</div>
      </div>
    </section>
  );
}
