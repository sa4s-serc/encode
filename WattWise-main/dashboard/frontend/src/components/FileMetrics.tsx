import type { FileResult } from '../types';
import { getFileDebtPercent, getMetricCardFiles, getTierColor, getTierDot } from '../utils/dashboard';
import { formatCurrency, formatNumber } from '../utils/format';

interface FileMetricsProps {
  files: FileResult[];
  selectedFilePath: string | null;
  onSelectFile: (path: string) => void;
}

export function FileMetrics({ files, selectedFilePath, onSelectFile }: FileMetricsProps) {
  return (
    <section className="panel heatmap-panel">
      <div className="panel-head">
        <div>
          <div className="panel-eyebrow">File Metrics</div>
          <div className="panel-sub">uniform cards with numeric file-level stats</div>
        </div>
        <div className="heatmap-legend" aria-label="Severity legend">
          <span>
            <i className="legend-chip legend-high" />
            High
          </span>
          <span>
            <i className="legend-chip legend-medium" />
            Medium
          </span>
          <span>
            <i className="legend-chip legend-low" />
            Low
          </span>
        </div>
      </div>
      <div className="heatmap-wrap">
        {files.length ? (
          <div className="file-metrics-grid">
            {getMetricCardFiles(files).map(file => {
              const debtPercent = getFileDebtPercent(file);
              const severity = getTierDot(file.aggregateScore || 0);
              const isSelected = file.path === selectedFilePath;
              return (
                <button
                  key={file.path}
                  type="button"
                  className={`file-metric-card file-metric-card-${severity}${isSelected ? ' is-selected' : ''}`}
                  style={{ ['--file-accent' as string]: getTierColor(file.aggregateScore || 0) }}
                  onClick={() => onSelectFile(file.path)}
                >
                  <div className="file-metric-topline">
                    <span className={`tier-badge tier-${severity}`}>{severity}</span>
                    <span className="file-metric-debt">{debtPercent}% debt</span>
                    <span className="file-metric-cost">{formatCurrency(file.totalCostUsd)}/yr</span>
                  </div>
                  <div className="file-metric-title">{file.name}</div>
                  <div className="file-metric-path">{file.path}</div>
                  <div className="file-metric-stats">
                    <div className="file-metric-stat">
                      <strong>{formatNumber(file.loc)}</strong>
                      <span>LOC</span>
                    </div>
                    <div className="file-metric-stat">
                      <strong>{formatNumber(file.totalBlocks)}</strong>
                      <span>Blocks</span>
                    </div>
                    <div className="file-metric-stat">
                      <strong>{formatNumber(file.highCount)}</strong>
                      <span>High</span>
                    </div>
                    <div className="file-metric-stat">
                      <strong>{formatNumber(file.mediumCount || 0)}</strong>
                      <span>Medium</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="empty-heatmap">No Python files with analysable blocks were found.</div>
        )}
      </div>
    </section>
  );
}
