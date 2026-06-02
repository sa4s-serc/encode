import type { FileResult } from '../types';
import { formatCurrency, formatNumber } from '../utils/format';

interface DetailPanelProps {
  file: FileResult | null;
  selectedBlockId: string | null;
  onSelectBlock: (blockId: string) => void;
}

export function DetailPanel({ file, selectedBlockId, onSelectBlock }: DetailPanelProps) {
  if (!file) {
    return (
      <section className="panel detail-panel">
        <div className="empty-detail">Select a file to inspect its blocks.</div>
      </section>
    );
  }

  return (
    <section className="panel detail-panel">
      <div className="panel-head detail-head">
        <div>
          <div className="panel-eyebrow">File Drill-down</div>
          <div className="detail-title">{file.path}</div>
          <div className="detail-sub">
            {file.loc} LOC · {file.totalBlocks} blocks · {formatCurrency(file.totalCostUsd)}/yr
          </div>
        </div>
      </div>
      <div className="detail-blocks">
        {file.blocks.length ? file.blocks.map(block => (
          <button
            key={block.id}
            type="button"
            className={`detail-block${block.id === selectedBlockId ? ' is-selected' : ''}`}
            onClick={() => onSelectBlock(block.id)}
          >
            <div className="detail-row">
              <span className={`tier-badge tier-${block.energyTier.toLowerCase()}`}>{block.energyTier}</span>
              <span>{block.label}</span>
              <span className="detail-cost">{formatCurrency(block.costPerYear)}/yr</span>
            </div>
            <div className="detail-row detail-row-secondary">
              <span>
                lines {block.startLine}–{block.endLine}
              </span>
              <span>{block.blockType}</span>
              <span>{formatNumber(block.callsPerDay)} calls/day</span>
            </div>
            <div className="detail-row">
              {(block.featureDrivers || []).map(driver => (
                <span key={`${block.id}:${driver.label}`} className="driver-pill">
                  {driver.label}: {driver.displayValue}
                </span>
              ))}
            </div>
          </button>
        )) : <div className="detail-empty-state">No analysable code blocks were found in this file.</div>}
      </div>
    </section>
  );
}
