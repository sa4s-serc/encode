import type { ScanProgress } from '../types';

interface ProgressBannerProps {
  progress: ScanProgress | null;
}

export function ProgressBanner({ progress }: ProgressBannerProps) {
  if (!progress) return null;

  const total = Math.max(1, Number(progress.totalFiles || 0));
  const ratio = Math.min(1, Number(progress.scannedFiles || 0) / total);

  return (
    <div className="scan-banner">
      <div className="scan-copy">
        <strong>{progress.message || 'Scanning repository'}</strong>
        <span>
          {progress.scannedFiles || 0} / {progress.totalFiles || 0} files
        </span>
      </div>
      <div className="scan-bar">
        <span style={{ width: `${(ratio * 100).toFixed(1)}%` }} />
      </div>
    </div>
  );
}
