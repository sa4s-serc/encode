import type {
  BlockResult,
  FileResult,
  FilterOption,
  HotspotSort,
  ScanResult,
} from '../types';

export const SETTINGS_BLOCK_TYPES = ['FunctionDef', 'For', 'While', 'If', 'Try', 'With'] as const;
export type FileSeverity = 'high' | 'medium' | 'low';

export function tierOrder(tier: string): number {
  return { High: 3, Medium: 2, Low: 1 }[tier] || 0;
}

function blendHex(left: string, right: string, factor: number): string {
  const startHex = left.replace('#', '');
  const endHex = right.replace('#', '');
  const channels = [0, 1, 2].map(index => {
    const start = parseInt(startHex.slice(index * 2, index * 2 + 2), 16);
    const end = parseInt(endHex.slice(index * 2, index * 2 + 2), 16);
    return Math.round(start + (end - start) * factor)
      .toString(16)
      .padStart(2, '0');
  });
  return '#' + channels.join('');
}

export function getTierColor(score: number): string {
  if (score <= 0.5) return blendHex('#C0DD97', '#FAC775', score * 2);
  return blendHex('#FAC775', '#F09595', Math.min(1, (score - 0.5) * 2));
}

export function getTierDot(score: number): FileSeverity {
  if (score >= 0.45) return 'high';
  if (score > 0.01) return 'medium';
  return 'low';
}

export function getMetricCardFiles(files: FileResult[]): FileResult[] {
  return files.slice().sort((left, right) => {
    return (
      Number(right.totalCostUsd || 0) - Number(left.totalCostUsd || 0) ||
      Number(right.highCount || 0) - Number(left.highCount || 0) ||
      Number(right.loc || 0) - Number(left.loc || 0)
    );
  });
}

export function getFileDebtPercent(file?: FileResult | null): number {
  if (!file || !file.totalBlocks) return 0;
  return Math.round((Number(file.highCount || 0) / Number(file.totalBlocks || 1)) * 100);
}

export function getFilterOptions(files: FileResult[]): FilterOption[] {
  const modules = new Set<string>();
  const filePaths: string[] = [];
  files.forEach(file => {
    modules.add(file.directory || '.');
    filePaths.push(file.path);
  });

  return [{ value: 'all', label: 'All modules' }]
    .concat(
      Array.from(modules)
        .sort()
        .map(modulePath => ({
          value: 'module:' + modulePath,
          label: modulePath === '.' ? 'Module: root' : 'Module: ' + modulePath,
        }))
    )
    .concat(
      filePaths.sort().map(filePath => ({
        value: 'file:' + filePath,
        label: 'File: ' + filePath,
      }))
    );
}

export function getFilteredHotspots(
  hotspots: BlockResult[],
  hotspotFilter: string,
  hotspotSort: HotspotSort
): BlockResult[] {
  let nextHotspots = hotspots.slice();
  if (hotspotFilter.startsWith('module:')) {
    const modulePath = hotspotFilter.slice('module:'.length);
    nextHotspots = nextHotspots.filter(block => (block.modulePath || '.') === modulePath);
  } else if (hotspotFilter.startsWith('file:')) {
    const filePath = hotspotFilter.slice('file:'.length);
    nextHotspots = nextHotspots.filter(block => block.filePath === filePath);
  }

  nextHotspots.sort((left, right) => {
    switch (hotspotSort) {
      case 'tier':
        return tierOrder(right.energyTier) - tierOrder(left.energyTier) || right.costPerYear - left.costPerYear;
      case 'loc':
        return right.loc - left.loc || right.costPerYear - left.costPerYear;
      case 'type':
        return left.blockType.localeCompare(right.blockType) || right.costPerYear - left.costPerYear;
      default:
        return right.costPerYear - left.costPerYear || right.energyJoules - left.energyJoules;
    }
  });

  return nextHotspots;
}

export function getSelectedFile(
  data: ScanResult | null,
  selectedFilePath: string | null
): FileResult | null {
  if (!data || !data.files.length) return null;
  return data.files.find(file => file.path === selectedFilePath) || getMetricCardFiles(data.files)[0] || null;
}

export function getSelectedBlock(
  data: ScanResult | null,
  selectedFile: FileResult | null,
  selectedBlockId: string | null
): BlockResult | null {
  if (!data || !selectedBlockId) return null;
  return (
    data.hotspots.find(block => block.id === selectedBlockId) ||
    selectedFile?.blocks.find(block => block.id === selectedBlockId) ||
    null
  );
}
