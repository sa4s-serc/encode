import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';

import { getDefaultRepo, getLatestScan, getScan, openScanEvents, putConfig, startScan } from './api';
import { DetailPanel } from './components/DetailPanel';
import { FileMetrics } from './components/FileMetrics';
import { FileTree } from './components/FileTree';
import { Header } from './components/Header';
import { HotspotDrawer } from './components/HotspotDrawer';
import { HotspotPanel } from './components/HotspotPanel';
import { ProgressBanner } from './components/ProgressBanner';
import { SettingsModal } from './components/SettingsModal';
import { SummaryCards } from './components/SummaryCards';
import type { ConfigUpdateResponse, CostConfig, HotspotSort, ScanProgress, ScanResult } from './types';
import {
  getFilterOptions,
  getFilteredHotspots,
  getMetricCardFiles,
  getSelectedBlock,
  getSelectedFile,
} from './utils/dashboard';

export default function App() {
  const [repoPath, setRepoPath] = useState('');
  const [scanId, setScanId] = useState<string | null>(null);
  const [data, setData] = useState<ScanResult | null>(null);
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [hotspotSort, setHotspotSort] = useState<HotspotSort>('cost');
  const [hotspotFilter, setHotspotFilter] = useState('all');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const eventsRef = useRef<EventSource | null>(null);

  function closeEvents() {
    eventsRef.current?.close();
    eventsRef.current = null;
  }

  async function tryLoadLatest(nextRepoPath: string) {
    if (!nextRepoPath) return;
    try {
      const latestScan = await getLatestScan(nextRepoPath);
      setData(latestScan);
      setScanId(latestScan.scanId);
      setError(null);
    } catch {
      setData(null);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function loadDefault() {
      try {
        const payload = await getDefaultRepo();
        if (cancelled) return;
        setRepoPath(payload.repoPath || '');
        await tryLoadLatest(payload.repoPath || '');
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Failed to load default repo.');
        }
      }
    }

    void loadDefault();
    return () => {
      cancelled = true;
      closeEvents();
    };
  }, []);

  useEffect(() => {
    if (!data) {
      if (selectedFilePath !== null) setSelectedFilePath(null);
      if (selectedBlockId !== null) setSelectedBlockId(null);
      return;
    }

    if (!selectedFilePath || !data.files.some(file => file.path === selectedFilePath)) {
      const firstVisibleFile = getMetricCardFiles(data.files)[0];
      const nextSelectedPath = firstVisibleFile ? firstVisibleFile.path : null;
      if (nextSelectedPath !== selectedFilePath) {
        setSelectedFilePath(nextSelectedPath);
      }
    }

    if (selectedBlockId && !data.hotspots.some(block => block.id === selectedBlockId)) {
      setSelectedBlockId(null);
    }
  }, [data, selectedBlockId, selectedFilePath]);

  function connectEvents(nextScanId: string) {
    closeEvents();
    eventsRef.current = openScanEvents(nextScanId, {
      onProgress: payload => {
        setProgress(payload);
        if (payload.snapshot) {
          setData(payload.snapshot);
        }
      },
      onComplete: async () => {
        closeEvents();
        const completedScan = await getScan(nextScanId);
        setData(completedScan);
        setProgress({
          message: 'Scan complete',
          scannedFiles: completedScan.fileCount,
          totalFiles: completedScan.fileCount,
        });
      },
      onError: message => {
        closeEvents();
        setError(message);
      },
    });
  }

  async function handleStartScan() {
    if (!repoPath.trim()) {
      setError('Enter a repository path first.');
      return;
    }

    closeEvents();
    setError(null);
    setProgress({ message: 'Preparing repository scan...', scannedFiles: 0, totalFiles: 0 });
    const payload = await startScan(repoPath);
    setScanId(payload.scanId);
    connectEvents(payload.scanId);
  }

  async function handleRepoSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await handleStartScan();
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : 'Failed to start scan.');
    }
  }

  async function handleSaveConfig(config: CostConfig) {
    try {
      const updated = await putConfig(repoPath, scanId, config);
      if ('scanId' in updated) {
        setData(updated);
        setScanId(updated.scanId);
      } else if (updated.config && data) {
        setData({ ...data, config: updated.config });
      }
      setError(null);
      setSettingsOpen(false);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Failed to save config.');
    }
  }

  function handleExportCsv() {
    if (!scanId) return;
    window.open('/api/scans/' + encodeURIComponent(scanId) + '/export.csv', '_blank');
  }

  const selectedFile = getSelectedFile(data, selectedFilePath);
  const selectedBlock = getSelectedBlock(data, selectedFile, selectedBlockId);
  const filterOptions = data ? getFilterOptions(data.files) : [{ value: 'all', label: 'All modules' }];
  const hotspots = data ? getFilteredHotspots(data.hotspots, hotspotFilter, hotspotSort) : [];

  return (
    <div className="shell">
      <Header
        data={data}
        repoPath={repoPath}
        isScanning={eventsRef.current !== null}
        onRepoPathChange={setRepoPath}
        onSubmit={handleRepoSubmit}
        onOpenSettings={() => setSettingsOpen(true)}
        onExportCsv={handleExportCsv}
      />

      <ProgressBanner progress={progress} />

      {error ? <div className="panel error-panel">{error}</div> : null}

      {data ? (
        <>
          <main className="dashboard-layout">
            <div className="dashboard-main">
              <div className="dashboard-grid">
                <FileTree tree={data.tree} selectedFilePath={selectedFilePath} onSelectFile={setSelectedFilePath} />
                <FileMetrics files={data.files} selectedFilePath={selectedFilePath} onSelectFile={setSelectedFilePath} />
              </div>
              <SummaryCards data={data} />
              <DetailPanel file={selectedFile} selectedBlockId={selectedBlockId} onSelectBlock={setSelectedBlockId} />
            </div>

            <HotspotPanel
              hotspots={hotspots}
              filterOptions={filterOptions}
              hotspotFilter={hotspotFilter}
              hotspotSort={hotspotSort}
              selectedBlockId={selectedBlockId}
              onFilterChange={setHotspotFilter}
              onSortChange={setHotspotSort}
              onSelectBlock={setSelectedBlockId}
            />
          </main>

          <HotspotDrawer block={selectedBlock} onClose={() => setSelectedBlockId(null)} />

          {settingsOpen ? (
            <SettingsModal config={data.config} onClose={() => setSettingsOpen(false)} onSave={handleSaveConfig} />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
