import type { FormEvent } from 'react';

import type { ScanResult } from '../types';
import { formatCurrencyCompact, formatNumber, formatRelativeTime } from '../utils/format';

interface HeaderProps {
  data: ScanResult | null;
  repoPath: string;
  isScanning: boolean;
  onRepoPathChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onOpenSettings: () => void;
  onExportCsv: () => void;
}

export function Header({
  data,
  repoPath,
  isScanning,
  onRepoPathChange,
  onSubmit,
  onOpenSettings,
  onExportCsv,
}: HeaderProps) {
  const repoForm = (
    <form className="repo-form" onSubmit={onSubmit}>
      <input
        className="repo-input"
        name="repoPath"
        value={repoPath}
        onChange={event => onRepoPathChange(event.target.value)}
        placeholder="/absolute/path/to/repository"
      />
      <button className="primary-button" type="submit">
        {isScanning ? 'Scanning…' : data ? 'Re-scan' : 'Scan repository'}
      </button>
      {data ? (
        <>
          <button className="ghost-button" type="button" onClick={onOpenSettings}>
            Call rates
          </button>
          <button className="ghost-button" type="button" onClick={onExportCsv}>
            Export CSV
          </button>
        </>
      ) : null}
    </form>
  );

  if (!data) {
    return (
      <header className="hero panel">
        <div>
          <h1 className="hero-title">WattWise Repository Dashboard</h1>
          <p className="hero-meta">Enter a local repository path, scan it on demand, and track energy debt over time.</p>
          {repoForm}
        </div>
      </header>
    );
  }

  return (
    <header className="hero panel">
      <div>
        <h1 className="hero-title">WattWise — {data.repoName}</h1>
        <p className="hero-meta">
          branch: {data.branch} · scanned {formatRelativeTime(data.scannedAt)} · {formatNumber(data.fileCount)} files ·{' '}
          {formatNumber(data.totalLoc)} LOC · {formatNumber(data.totalBlocks)} blocks
        </p>
        <div className="trend-strip">
          <div className="trend-metric">
            <span className="trend-label">energy debt</span>
            <strong>{formatNumber(data.energyDebtScore)}</strong>
          </div>
        </div>
        {repoForm}
      </div>
      <div className="hero-actions">
        <div className="hero-pill">
          {formatNumber(data.totalHigh)} high blocks · {formatCurrencyCompact(data.totalCostUsd)} / yr
        </div>
      </div>
    </header>
  );
}
