import type {
  ConfigUpdateResponse,
  CostConfig,
  DefaultRepoResponse,
  ScanProgress,
  ScanResult,
  StartScanResponse,
} from './types';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || payload.message || response.statusText);
  }
  return response.json() as Promise<T>;
}

export function getDefaultRepo(): Promise<DefaultRepoResponse> {
  return fetchJson<DefaultRepoResponse>('/api/default-repo');
}

export function getLatestScan(repoPath: string): Promise<ScanResult> {
  return fetchJson<ScanResult>('/api/repos/latest?repoPath=' + encodeURIComponent(repoPath));
}

export function startScan(repoPath: string): Promise<StartScanResponse> {
  return fetchJson<StartScanResponse>('/api/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repoPath }),
  });
}

export function getScan(scanId: string): Promise<ScanResult> {
  return fetchJson<ScanResult>('/api/scans/' + encodeURIComponent(scanId));
}

export function putConfig(
  repoPath: string,
  scanId: string | null,
  config: CostConfig
): Promise<ConfigUpdateResponse> {
  return fetchJson<ConfigUpdateResponse>('/api/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repoPath, scanId, config }),
  });
}

export function openScanEvents(
  scanId: string,
  handlers: {
    onProgress: (payload: ScanProgress) => void;
    onComplete: () => void;
    onError: (message: string) => void;
  }
): EventSource {
  const events = new EventSource('/api/scans/' + encodeURIComponent(scanId) + '/events');
  events.addEventListener('progress', event => {
    handlers.onProgress(JSON.parse(event.data) as ScanProgress);
  });
  events.addEventListener('complete', () => {
    handlers.onComplete();
  });
  events.addEventListener('scan-error', event => {
    try {
      const payload = JSON.parse(event.data) as { message?: string };
      handlers.onError(payload.message || 'Scan failed.');
    } catch {
      handlers.onError('Scan failed.');
    }
  });
  return events;
}
