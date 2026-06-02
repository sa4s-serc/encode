import type { TreeNode } from '../types';
import { getTierDot } from '../utils/dashboard';

interface FileTreeProps {
  tree: TreeNode;
  selectedFilePath: string | null;
  onSelectFile: (path: string) => void;
}

interface FileTreeNodeViewProps extends FileTreeProps {
  node: TreeNode;
  branchTrail: boolean[];
  isLast: boolean;
}

function TreePrefix({ branchTrail, isLast }: { branchTrail: boolean[]; isLast: boolean }) {
  return (
    <span className="tree-prefix" aria-hidden="true">
      {branchTrail.map((hasSiblingBelow, index) => (
        <span key={`trail:${index}`} className={`tree-rail${hasSiblingBelow ? ' is-active' : ''}`} />
      ))}
      <span className={`tree-branch ${isLast ? 'is-last' : 'is-mid'}`} />
    </span>
  );
}

function FileTreeNodeView({ node, selectedFilePath, onSelectFile, branchTrail, isLast }: FileTreeNodeViewProps): JSX.Element | null {
  const nextBranchTrail = branchTrail.concat(!isLast);

  if (node.kind === 'directory') {
    const children = (node.children || []).map((child, childIndex, childArray) => (
      <FileTreeNodeView
        key={child.path || `${node.path || 'root'}:${child.name}`}
        node={child}
        tree={node}
        selectedFilePath={selectedFilePath}
        onSelectFile={onSelectFile}
        branchTrail={nextBranchTrail}
        isLast={childIndex === childArray.length - 1}
      />
    ));

    if (!node.path) {
      return <>{children}</>;
    }

    return (
      <div className="tree-group">
        <div className="tree-folder-row">
          <TreePrefix branchTrail={branchTrail} isLast={isLast} />
          <div className="tree-folder">{node.name} /</div>
        </div>
        {children}
      </div>
    );
  }

  const isSelected = node.path === selectedFilePath;
  const severity = getTierDot(node.aggregateScore);

  return (
    <button
      type="button"
      className={`tree-file tree-file-${severity}${isSelected ? ' is-selected' : ''}`}
      onClick={() => node.path && onSelectFile(node.path)}
    >
      <TreePrefix branchTrail={branchTrail} isLast={isLast} />
      <span className={`tree-dot tree-dot-${severity}`} />
      <span className="tree-label">{node.name}</span>
      {node.highCount > 0 ? <span className="tree-badge">{node.highCount} H</span> : null}
    </button>
  );
}

export function FileTree({ tree, selectedFilePath, onSelectFile }: FileTreeProps) {
  return (
    <section className="panel tree-panel">
      <div className="panel-head">
        <div>
          <div className="panel-eyebrow">File Tree</div>
          <div className="panel-sub">actual repository structure</div>
        </div>
      </div>
      <div className="tree-scroll">
        {(tree.children || []).map((child, index, array) => (
          <FileTreeNodeView
            key={child.path || `root:${child.name}`}
            node={child}
            tree={tree}
            selectedFilePath={selectedFilePath}
            onSelectFile={onSelectFile}
            branchTrail={[]}
            isLast={index === array.length - 1}
          />
        ))}
      </div>
    </section>
  );
}
