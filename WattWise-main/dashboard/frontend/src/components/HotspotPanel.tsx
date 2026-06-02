import type { BlockResult, FilterOption, HotspotSort } from '../types';
import { formatCurrency } from '../utils/format';

interface HotspotPanelProps {
  hotspots: BlockResult[];
  filterOptions: FilterOption[];
  hotspotFilter: string;
  hotspotSort: HotspotSort;
  selectedBlockId: string | null;
  onFilterChange: (value: string) => void;
  onSortChange: (value: HotspotSort) => void;
  onSelectBlock: (blockId: string) => void;
}

export function HotspotPanel({
  hotspots,
  filterOptions,
  hotspotFilter,
  hotspotSort,
  selectedBlockId,
  onFilterChange,
  onSortChange,
  onSelectBlock,
}: HotspotPanelProps) {
  return (
    <section className="panel hotspot-panel">
      <div className="panel-head">
        <div>
          <div className="panel-eyebrow">Top Hotspots</div>
          <div className="panel-sub">ranked by annual cost impact</div>
        </div>
        <div className="hotspot-controls">
          <select value={hotspotFilter} onChange={event => onFilterChange(event.target.value)}>
            {filterOptions.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select value={hotspotSort} onChange={event => onSortChange(event.target.value as HotspotSort)}>
            <option value="cost">Cost</option>
            <option value="tier">Tier</option>
            <option value="loc">LOC</option>
            <option value="type">Block type</option>
          </select>
        </div>
      </div>
      <div className="hotspot-list">
        {hotspots.length ? (
          hotspots.map((block, index) => (
            <button
              key={block.id}
              type="button"
              className={`hotspot-item${block.id === selectedBlockId ? ' is-selected' : ''}`}
              onClick={() => onSelectBlock(block.id)}
            >
              <div className="hotspot-topline">
                <span className={`tier-badge tier-${block.energyTier.toLowerCase()}`}>{block.energyTier}</span>
                <span className="hotspot-rank">#{index + 1}</span>
                <span className="hotspot-cost">{formatCurrency(block.costPerYear)}/yr</span>
              </div>
              <div className="hotspot-title">{block.label}</div>
              <div className="hotspot-meta">
                {block.filePath}:{block.startLine}
              </div>
            </button>
          ))
        ) : (
          <div className="empty-hotspots">No hotspots match this filter.</div>
        )}
      </div>
    </section>
  );
}
