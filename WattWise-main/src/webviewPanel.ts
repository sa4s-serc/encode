import * as vscode from 'vscode';
import { EnergyPrediction } from './pythonBridge';

export class EnergyWebviewPanel {
    private static currentPanel: EnergyWebviewPanel | undefined;
    private readonly panel: vscode.WebviewPanel;
    private disposables: vscode.Disposable[] = [];

    static createOrShow(
        context: vscode.ExtensionContext,
        predictions: EnergyPrediction[],
        fileName: string
    ): void {
        const column = vscode.ViewColumn.Beside;

        if (EnergyWebviewPanel.currentPanel) {
            EnergyWebviewPanel.currentPanel.update(predictions, fileName);
            EnergyWebviewPanel.currentPanel.panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'wattwiseReport',
            `WattWise Report — ${fileName}`,
            column,
            { enableScripts: true, retainContextWhenHidden: true }
        );

        EnergyWebviewPanel.currentPanel = new EnergyWebviewPanel(panel, predictions, fileName);
    }

    private constructor(
        panel: vscode.WebviewPanel,
        predictions: EnergyPrediction[],
        fileName: string
    ) {
        this.panel = panel;
        this.panel.webview.html = this.buildHtml(predictions, fileName);

        this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
    }

    private update(predictions: EnergyPrediction[], fileName: string): void {
        this.panel.title = `WattWise Report — ${fileName}`;
        this.panel.webview.html = this.buildHtml(predictions, fileName);
    }

    private dispose(): void {
        EnergyWebviewPanel.currentPanel = undefined;
        this.panel.dispose();
        this.disposables.forEach(d => d.dispose());
    }

    private buildHtml(predictions: EnergyPrediction[], fileName: string): string {
        const totalEnergy = predictions.reduce((s, p) => s + (p.energy_joules || 0), 0);
        const avgEnergy = totalEnergy / predictions.length;

        const counts = { Low: 0, Medium: 0, High: 0 };
        predictions.forEach(p => {
            if (p.energy_tier in counts) { counts[p.energy_tier as keyof typeof counts]++; }
        });

        const sorted = [...predictions].sort((a, b) => (b.energy_joules || 0) - (a.energy_joules || 0));
        const highBlocks = predictions.filter(p => p.energy_tier === 'High');

        const tierBadge = (tier: string) => {
            const map: Record<string, string> = {
                Low: 'badge-low', Medium: 'badge-medium', High: 'badge-high'
            };
            return `<span class="badge ${map[tier] || ''}">${tier}</span>`;
        };

        const blockRows = sorted.map((p, i) => {
            const barPct = Math.min(100, (p.energy_joules / (sorted[0].energy_joules || 1)) * 100).toFixed(1);
            const barClass = { Low: 'bar-low', Medium: 'bar-medium', High: 'bar-high' }[p.energy_tier] || 'bar-low';
            return `
            <tr>
                <td>${i + 1}</td>
                <td><code>${p.block_type}</code></td>
                <td>${p.start_line}–${p.end_line}</td>
                <td>
                    <div class="bar-wrap">
                        <div class="bar ${barClass}" style="width:${barPct}%"></div>
                    </div>
                    <span class="energy-val">${p.energy_joules.toExponential(2)} J</span>
                </td>
                <td>${tierBadge(p.energy_tier)}</td>
                <td>${((p.tier_confidence || 0) * 100).toFixed(0)}%</td>
            </tr>`;
        }).join('');

        const suggestionCards = highBlocks
            .filter(p => p.suggestion && !p.suggestion.error)
            .map(p => {
                const s = p.suggestion!;
                const tips = (s.suggestions || []).map(t => `<li>${escapeHtml(t)}</li>`).join('');
                const code = s.improved_code
                    ? `<div class="code-wrap"><pre><code>${escapeHtml(s.improved_code)}</code></pre></div>`
                    : '';
                return `
                <div class="suggestion-card">
                    <div class="suggestion-header">
                        <span class="badge badge-high">${p.block_type}</span>
                        <span class="lines">lines ${p.start_line}–${p.end_line}</span>
                        <span class="energy-label">${p.energy_joules.toExponential(2)} J</span>
                    </div>
                    ${s.explanation ? `<p class="explanation"><strong>Why it's expensive:</strong> ${escapeHtml(s.explanation)}</p>` : ''}
                    ${tips ? `<ul class="tips">${tips}</ul>` : ''}
                    ${code}
                </div>`;
            }).join('');

        const noSuggestions = highBlocks.length > 0 && !highBlocks.some(p => p.suggestion && !p.suggestion.error)
            ? `<p class="muted">No AI suggestions available. Make sure the Gemini API key is configured.</p>`
            : '';

        const distributionBars = (['High', 'Medium', 'Low'] as const).map(tier => {
            const pct = predictions.length ? ((counts[tier] / predictions.length) * 100).toFixed(0) : '0';
            const cls = { High: 'bar-high', Medium: 'bar-medium', Low: 'bar-low' }[tier];
            return `
            <div class="dist-row">
                <span class="dist-label">${tier}</span>
                <div class="bar-wrap">
                    <div class="bar ${cls}" style="width:${pct}%"></div>
                </div>
                <span class="dist-count">${counts[tier]} block${counts[tier] !== 1 ? 's' : ''}</span>
            </div>`;
        }).join('');

        const timestamp = new Date().toLocaleString();

        return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>WattWise Report</title>
<style>
  :root {
    --bg: var(--vscode-editor-background);
    --fg: var(--vscode-editor-foreground);
    --border: var(--vscode-panel-border, #444);
    --card-bg: var(--vscode-editorWidget-background, #1e1e1e);
    --low:    #4caf50;
    --medium: #ff9800;
    --high:   #f44336;
    --accent: var(--vscode-button-background, #0e639c);
    --code-bg: var(--vscode-textCodeBlock-background, #2d2d2d);
    --muted: var(--vscode-descriptionForeground, #888);
    --font: var(--vscode-font-family, 'Segoe UI', sans-serif);
    --mono: var(--vscode-editor-font-family, 'Courier New', monospace);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--fg); font-family: var(--font); font-size: 13px; padding: 20px; }
  h1 { font-size: 18px; margin-bottom: 4px; }
  h2 { font-size: 14px; margin: 24px 0 10px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
  .meta { color: var(--muted); font-size: 11px; margin-bottom: 20px; }

  /* stat cards */
  .cards { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
  .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px;
          padding: 12px 16px; min-width: 140px; flex: 1; }
  .card-val { font-size: 22px; font-weight: bold; margin-bottom: 2px; }
  .card-lbl { font-size: 11px; color: var(--muted); }
  .card-high .card-val { color: var(--high); }
  .card-med  .card-val { color: var(--medium); }
  .card-low  .card-val { color: var(--low); }

  /* distribution bars */
  .dist-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .dist-label { width: 54px; font-size: 12px; }
  .dist-count { width: 70px; font-size: 11px; color: var(--muted); text-align: right; }

  /* bar commons */
  .bar-wrap { flex: 1; background: var(--card-bg); border-radius: 3px; height: 10px; overflow: hidden; }
  .bar { height: 100%; border-radius: 3px; transition: width 0.3s; }
  .bar-low    { background: var(--low); }
  .bar-medium { background: var(--medium); }
  .bar-high   { background: var(--high); }

  /* table */
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); color: var(--muted); font-weight: 600; }
  td { padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(255,255,255,0.03); }
  .energy-val { font-family: var(--mono); font-size: 11px; margin-left: 6px; }
  .bar-wrap { min-width: 80px; }

  /* badges */
  .badge { display: inline-block; padding: 2px 7px; border-radius: 10px; font-size: 10px; font-weight: 700; }
  .badge-low    { background: rgba(76,175,80,0.2);  color: var(--low);    border: 1px solid var(--low); }
  .badge-medium { background: rgba(255,152,0,0.2);  color: var(--medium); border: 1px solid var(--medium); }
  .badge-high   { background: rgba(244,67,54,0.2);  color: var(--high);   border: 1px solid var(--high); }

  /* suggestion cards */
  .suggestion-card { background: var(--card-bg); border: 1px solid var(--border); border-left: 3px solid var(--high);
                     border-radius: 6px; padding: 14px; margin-bottom: 14px; }
  .suggestion-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
  .lines { color: var(--muted); font-size: 11px; }
  .energy-label { margin-left: auto; font-family: var(--mono); font-size: 11px; color: var(--high); }
  .explanation { font-size: 12px; margin-bottom: 10px; line-height: 1.5; }
  .tips { margin: 0 0 10px 16px; font-size: 12px; line-height: 1.8; }
  .code-wrap { background: var(--code-bg); border-radius: 4px; padding: 10px 12px; overflow-x: auto; }
  .code-wrap pre { margin: 0; }
  .code-wrap code { font-family: var(--mono); font-size: 12px; white-space: pre; }
  .muted { color: var(--muted); font-size: 12px; }
  code { font-family: var(--mono); }
  .tagline { font-size: 12px; font-weight: 400; color: var(--muted); margin-left: 8px; letter-spacing: 0.04em; text-transform: uppercase; }
  .powered { font-size: 11px; font-weight: 400; color: var(--muted); margin-left: 6px; }
</style>
</head>
<body>

<h1>⚡ WattWise <span class="tagline">Energy Linter for Code</span></h1>
<p class="meta">File: <strong>${escapeHtml(fileName)}</strong> &nbsp;|&nbsp; Generated: ${timestamp}</p>

<div class="cards">
  <div class="card">
    <div class="card-val">${predictions.length}</div>
    <div class="card-lbl">Blocks Analyzed</div>
  </div>
  <div class="card">
    <div class="card-val">${totalEnergy.toExponential(2)} J</div>
    <div class="card-lbl">Total Energy</div>
  </div>
  <div class="card">
    <div class="card-val">${avgEnergy.toExponential(2)} J</div>
    <div class="card-lbl">Avg per Block</div>
  </div>
  <div class="card card-high">
    <div class="card-val">${counts.High}</div>
    <div class="card-lbl">High-Energy Blocks</div>
  </div>
  <div class="card card-med">
    <div class="card-val">${counts.Medium}</div>
    <div class="card-lbl">Medium-Energy Blocks</div>
  </div>
  <div class="card card-low">
    <div class="card-val">${counts.Low}</div>
    <div class="card-lbl">Low-Energy Blocks</div>
  </div>
</div>

<h2>Tier Distribution</h2>
${distributionBars}

<h2>All Blocks (sorted by energy)</h2>
<table>
  <thead>
    <tr><th>#</th><th>Type</th><th>Lines</th><th>Energy</th><th>Tier</th><th>Confidence</th></tr>
  </thead>
  <tbody>${blockRows}</tbody>
</table>

<h2>🤖 WattWise AI Suggestions <span class="powered">powered by Gemini 2.5 Flash</span></h2>
${suggestionCards || noSuggestions || '<p class="muted">No high-energy blocks found.</p>'}

</body>
</html>`;
    }
}

function escapeHtml(str: string): string {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
