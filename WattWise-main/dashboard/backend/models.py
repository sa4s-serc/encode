from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal

Tier = Literal["Low", "Medium", "High"]
NodeKind = Literal["directory", "file"]


@dataclass
class CostConfig:
    awsRateKwh: float
    co2KgPerKwh: float
    defaultCallsPerDay: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FeatureDriver:
    key: str
    label: str
    value: float
    displayValue: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BlockResult:
    id: str
    absolutePath: str
    filePath: str
    fileName: str
    modulePath: str
    label: str
    blockType: str
    startLine: int
    endLine: int
    loc: int
    energyJoules: float
    energyTier: str
    tierConfidence: float
    energyFormatted: str
    callsPerDay: int
    annualKwh: float
    costPerYear: float
    co2KgPerYear: float
    codeSnippet: str
    features: Dict[str, float]
    featureDrivers: List[FeatureDriver]
    optimizationStrategy: List[str]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["featureDrivers"] = [driver.to_dict() for driver in self.featureDrivers]
        return data


@dataclass
class FileResult:
    absolutePath: str
    path: str
    name: str
    directory: str
    loc: int
    totalBlocks: int
    highCount: int
    mediumCount: int
    lowCount: int
    aggregateScore: float
    aggregateTier: Tier
    totalEnergyJoules: float
    totalKwh: float
    totalCostUsd: float
    totalCo2Kg: float
    blocks: List[BlockResult]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["blocks"] = [block.to_dict() for block in self.blocks]
        return data


@dataclass
class TreeNode:
    kind: NodeKind
    name: str
    path: str
    loc: int
    totalBlocks: int
    highCount: int
    aggregateScore: float
    aggregateTier: Tier
    children: List["TreeNode"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["children"] = [child.to_dict() for child in self.children]
        return data


@dataclass
class HistoryPoint:
    date: str
    scannedAt: str
    commitSha: str
    energyDebtScore: int
    costUsd: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    scanId: str
    repoId: str
    repoName: str
    repoPath: str
    branch: str
    commitSha: str
    scannedAt: str
    fileCount: int
    totalLoc: int
    totalBlocks: int
    totalHigh: int
    totalMedium: int
    totalLow: int
    totalCostUsd: float
    totalKwh: float
    totalCo2Kg: float
    potentialSavingUsd: float
    energyDebtScore: int
    files: List[FileResult]
    hotspots: List[BlockResult]
    tree: TreeNode
    history: List[HistoryPoint]
    config: CostConfig

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["files"] = [file.to_dict() for file in self.files]
        data["hotspots"] = [block.to_dict() for block in self.hotspots]
        data["tree"] = self.tree.to_dict()
        data["history"] = [point.to_dict() for point in self.history]
        data["config"] = self.config.to_dict()
        return data
