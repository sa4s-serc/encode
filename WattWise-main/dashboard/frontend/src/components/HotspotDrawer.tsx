import type { BlockResult } from '../types';
import { formatCurrency, formatNumber } from '../utils/format';

interface HotspotDrawerProps {
  block: BlockResult | null;
  onClose: () => void;
}

export function HotspotDrawer({ block, onClose }: HotspotDrawerProps) {
  if (!block) return null;

  return (
    <aside className="drawer">
      <div className="drawer-head">
        <div>
          <div className="panel-eyebrow">Hotspot Detail</div>
          <div className="drawer-title">{block.label}</div>
          <div className="drawer-sub">
            {block.filePath}:{block.startLine} · {block.blockType}
          </div>
        </div>
        <button className="icon-button" type="button" onClick={onClose}>
          Close
        </button>
      </div>

      <div className="drawer-grid">
        <div className="drawer-metric">
          <span className="drawer-metric-label">Tier</span>
          <span className={`tier-badge tier-${block.energyTier.toLowerCase()}`}>{block.energyTier}</span>
        </div>
        <div className="drawer-metric">
          <span className="drawer-metric-label">Annual cost</span>
          <strong>{formatCurrency(block.costPerYear)}/yr</strong>
        </div>
        <div className="drawer-metric">
          <span className="drawer-metric-label">Energy</span>
          <strong>{Number(block.energyJoules).toExponential(2)} J</strong>
        </div>
        <div className="drawer-metric">
          <span className="drawer-metric-label">Calls / day</span>
          <strong>{formatNumber(block.callsPerDay)}</strong>
        </div>
      </div>

      <div className="drawer-section">
        <div className="drawer-section-title">Feature drivers</div>
        <div className="driver-stack">
          {(block.featureDrivers || []).length ? (
            (block.featureDrivers || []).map(driver => (
              <div key={`${block.id}:${driver.label}`} className="driver-row">
                <span>{driver.label}</span>
                <strong>{driver.displayValue}</strong>
              </div>
            ))
          ) : (
            <div className="driver-row">
              <span>no dominant drivers</span>
              <strong>n/a</strong>
            </div>
          )}
        </div>
      </div>

      <div className="drawer-section">
        <div className="drawer-section-title">Suggested optimisation strategy</div>
        <ul className="strategy-list">
          {(block.optimizationStrategy || []).map((item, index) => (
            <li key={`${block.id}:strategy:${index}`}>{item}</li>
          ))}
        </ul>
      </div>

      <div className="drawer-section">
        <div className="drawer-section-title">Code snippet</div>
        <pre className="code-block">
          <code>{block.codeSnippet || ''}</code>
        </pre>
      </div>
    </aside>
  );
}
