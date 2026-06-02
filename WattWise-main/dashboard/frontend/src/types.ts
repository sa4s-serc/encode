export type EnergyTier = 'High' | 'Medium' | 'Low';
export type HotspotSort = 'cost' | 'tier' | 'loc' | 'type';

export interface HistoryPoint {
  scannedAt: string;
  energyDebtScore: number;
  costUsd: number;
  commitSha?: string | null;
  label?: string | null;
}

export interface FeatureDriver {
  label: string;
  displayValue: string;
  value?: number | string | null;
}

export interface BlockResult {
  id: string;
  label: string;
  filePath: string;
  modulePath?: string | null;
  blockType: string;
  startLine: number;
  endLine: number;
  energyTier: EnergyTier;
  energyJoules: number;
  costPerYear: number;
  callsPerDay: number;
  loc: number;
  codeSnippet?: string;
  optimizationStrategy?: string[];
  featureDrivers?: FeatureDriver[];
}

export interface FileResult {
  name: string;
  path: string;
  directory?: string;
  loc: number;
  totalBlocks: number;
  highCount: number;
  mediumCount: number;
  aggregateScore: number;
  totalCostUsd: number;
  blocks: BlockResult[];
}

export interface TreeNode {
  kind: 'directory' | 'file';
  name: string;
  path?: string;
  highCount: number;
  totalBlocks: number;
  aggregateScore: number;
  children?: TreeNode[];
}

export interface CostConfig {
  awsRateKwh: number;
  co2KgPerKwh: number;
  defaultCallsPerDay: Record<string, number>;
}

export interface ScanResult {
  scanId: string;
  repoId: string;
  repoName: string;
  branch: string;
  scannedAt: string;
  fileCount: number;
  totalLoc: number;
  totalBlocks: number;
  totalHigh: number;
  totalMedium: number;
  totalLow: number;
  totalKwh: number;
  totalCo2Kg: number;
  totalCostUsd: number;
  potentialSavingUsd: number;
  energyDebtScore: number;
  tree: TreeNode;
  files: FileResult[];
  hotspots: BlockResult[];
  history: HistoryPoint[];
  config: CostConfig;
}

export interface ScanProgress {
  message: string;
  scannedFiles: number;
  totalFiles: number;
  snapshot?: ScanResult;
}

export interface FilterOption {
  value: string;
  label: string;
}

export interface DefaultRepoResponse {
  repoPath: string;
}

export interface StartScanResponse {
  scanId: string;
  repoId: string;
  repoMeta?: Record<string, string | null>;
}

export type ConfigUpdateResponse = ScanResult | { config: CostConfig };
