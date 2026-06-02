import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { PythonBridge, EnergyPrediction, EnergySuggestion } from './pythonBridge';
import { EnergyDecorationManager } from './decorations';
import { EnergyWebviewPanel } from './webviewPanel';

let pythonBridge: PythonBridge;
let decorationManager: EnergyDecorationManager;
let outputChannel: vscode.OutputChannel;
let statusBarItem: vscode.StatusBarItem;
let extensionContext: vscode.ExtensionContext;

/**
 * Extension activation
 */
export function activate(context: vscode.ExtensionContext) {
    console.log('WattWise — Energy Linter for Code is now active');

    extensionContext = context;

    pythonBridge = new PythonBridge(context.extensionPath);
    decorationManager = new EnergyDecorationManager();
    outputChannel = vscode.window.createOutputChannel('WattWise');

    // Status bar
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'wattwise.analyzeFile';
    statusBarItem.text = '$(zap) WattWise';
    statusBarItem.tooltip = 'WattWise: Analyze energy consumption of this Python file';
    context.subscriptions.push(statusBarItem);

    updateStatusBarVisibility();

    // Commands
    context.subscriptions.push(
        vscode.commands.registerCommand('wattwise.analyzeFile', analyzeCurrentFile)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('wattwise.clearAnalysis', clearAnalysis)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('wattwise.trainModels', trainModels)
    );

    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(updateStatusBarVisibility)
    );

    vscode.window.showInformationMessage(
        '⚡ WattWise activated — open a Python file and click $(zap) WattWise to lint its energy usage.',
        'Train Models'
    ).then(selection => {
        if (selection === 'Train Models') {
            vscode.commands.executeCommand('wattwise.trainModels');
        }
    });
}

/**
 * Show status bar item only for Python files
 */
function updateStatusBarVisibility() {
    const editor = vscode.window.activeTextEditor;
    if (editor && editor.document.languageId === 'python') {
        statusBarItem.show();
    } else {
        statusBarItem.hide();
    }
}

/**
 * Analyze the currently open Python file
 */
async function analyzeCurrentFile() {
    const editor = vscode.window.activeTextEditor;

    if (!editor) {
        vscode.window.showErrorMessage('WattWise: No active editor.');
        return;
    }

    if (editor.document.languageId !== 'python') {
        vscode.window.showErrorMessage('WattWise: This command only works with Python files.');
        return;
    }

    const code = editor.document.getText();

    if (!code.trim()) {
        vscode.window.showErrorMessage('WattWise: File is empty.');
        return;
    }

    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: '⚡ WattWise',
            cancellable: false
        },
        async (progress) => {
            try {
                progress.report({ increment: 0, message: 'Parsing code blocks...' });

                const predictions = await pythonBridge.analyzeFile(code);

                progress.report({ increment: 50, message: 'Predicting energy tiers...' });

                if (!predictions || predictions.length === 0) {
                    vscode.window.showInformationMessage('WattWise: No analysable code blocks found.');
                    return;
                }

                // Gemini suggestions for High-energy blocks
                const config = vscode.workspace.getConfiguration('wattwise');
                const apiKey = config.get<string>('geminiApiKey', '')
                    || process.env.GEMINI_API_KEY
                    || '';
                const highEnergyBlocks = predictions.filter(p => p.energy_tier === 'High' && !p.error);
                let suggestionCount = 0;

                if (highEnergyBlocks.length > 0) {
                    progress.report({ increment: 75, message: `Fetching Gemini suggestions for ${highEnergyBlocks.length} high-energy block(s)...` });
                    try {
                        const suggestions = await pythonBridge.getSuggestions(code, highEnergyBlocks, apiKey);
                        attachSuggestionsToPredictions(predictions, suggestions);
                        suggestionCount = suggestions.filter(s => !s.error).length;
                    } catch (suggErr: any) {
                        outputChannel.appendLine(`\nWattWise Warning: Could not fetch AI suggestions: ${suggErr.message}`);
                    }
                }

                progress.report({ increment: 95, message: 'Applying energy annotations...' });

                decorationManager.applyDecorations(editor, predictions);

                const fileName = path.basename(editor.document.fileName);
                const summary = generateSummary(predictions, fileName);

                // Output panel
                outputChannel.clear();
                outputChannel.appendLine('WattWise — Energy Linter for Code');
                outputChannel.appendLine('='.repeat(60));
                outputChannel.appendLine(summary);
                outputChannel.show(true);

                // Save .txt report
                const txtPath = editor.document.fileName.replace(/\.py$/, '_wattwise_report.txt');
                try {
                    fs.writeFileSync(
                        txtPath,
                        `WattWise — Energy Linter for Code\n${'='.repeat(60)}\n${summary}`,
                        'utf8'
                    );
                } catch (writeErr: any) {
                    outputChannel.appendLine(`\nWattWise: Could not save report file: ${writeErr.message}`);
                }

                // Open web report
                EnergyWebviewPanel.createOrShow(extensionContext, predictions, fileName);

                // Toast
                const toastParts = [`Analyzed ${predictions.length} block(s)`];
                if (highEnergyBlocks.length > 0) {
                    toastParts.push(`${highEnergyBlocks.length} high-energy`);
                }
                if (suggestionCount > 0) {
                    toastParts.push(`${suggestionCount} AI suggestion(s) ready`);
                } else if (highEnergyBlocks.length > 0 && !apiKey) {
                    toastParts.push(`Set wattwise.geminiApiKey for AI suggestions`);
                }
                vscode.window.showInformationMessage(`⚡ WattWise | ${toastParts.join(' · ')}`);

            } catch (error: any) {
                const errorMessage = error.message || 'Unknown error';
                outputChannel.appendLine(`WattWise Error: ${errorMessage}`);
                outputChannel.show();

                if (errorMessage.includes('Models not found')) {
                    vscode.window.showErrorMessage(
                        'WattWise: ML models not trained yet.',
                        'Train Now'
                    ).then(selection => {
                        if (selection === 'Train Now') {
                            vscode.commands.executeCommand('wattwise.trainModels');
                        }
                    });
                } else {
                    vscode.window.showErrorMessage(`WattWise Error: ${errorMessage}`);
                }
            }
        }
    );
}

/**
 * Attach Gemini suggestions back to the matching predictions
 */
function attachSuggestionsToPredictions(
    predictions: EnergyPrediction[],
    suggestions: EnergySuggestion[]
): void {
    for (const suggestion of suggestions) {
        const target = predictions.find(
            p => p.start_line === suggestion.start_line && p.end_line === suggestion.end_line
        );
        if (target) {
            target.suggestion = suggestion;
        }
    }
}

/**
 * Generate plain-text summary for output panel and .txt report
 */
function generateSummary(predictions: EnergyPrediction[], fileName?: string): string {
    const lines: string[] = [];

    if (fileName) {
        lines.push(`File    : ${fileName}`);
        lines.push(`Generated: ${new Date().toLocaleString()}`);
        lines.push('');
    }

    const totalEnergy = predictions.reduce((sum, p) => sum + (p.energy_joules || 0), 0);
    const avgEnergy = totalEnergy / predictions.length;

    const tierCounts = { Low: 0, Medium: 0, High: 0 };
    predictions.forEach(p => {
        if (p.energy_tier in tierCounts) {
            tierCounts[p.energy_tier as keyof typeof tierCounts]++;
        }
    });

    lines.push(`Total blocks analyzed : ${predictions.length}`);
    lines.push(`Total estimated energy: ${totalEnergy.toExponential(3)} J`);
    lines.push(`Average energy / block: ${avgEnergy.toExponential(3)} J`);
    lines.push('');
    lines.push('Energy Tier Distribution:');
    lines.push(`  🟢 Low    : ${tierCounts.Low} block(s)`);
    lines.push(`  🟡 Medium : ${tierCounts.Medium} block(s)`);
    lines.push(`  🔴 High   : ${tierCounts.High} block(s)`);
    lines.push('');
    lines.push('Block Details  (sorted highest → lowest energy):');
    lines.push('-'.repeat(60));

    const sorted = [...predictions].sort((a, b) => (b.energy_joules || 0) - (a.energy_joules || 0));
    sorted.forEach((p, i) => {
        const emoji = { Low: '🟢', Medium: '🟡', High: '🔴' }[p.energy_tier] || '⚪';
        lines.push(`${i + 1}. ${emoji} ${p.block_type} (lines ${p.start_line}–${p.end_line})`);
        lines.push(`   Energy: ${p.energy_joules.toExponential(3)} J  |  Tier: ${p.energy_tier}  |  Confidence: ${((p.tier_confidence || 0) * 100).toFixed(0)}%`);
        lines.push('');
    });

    const highBlocks = predictions.filter(p => p.energy_tier === 'High');
    if (highBlocks.length > 0) {
        lines.push('⚠️  RECOMMENDATIONS:');
        lines.push('-'.repeat(60));
        lines.push(`Found ${highBlocks.length} high-energy block(s). Consider optimizing:`);
        highBlocks.forEach(p => {
            lines.push(`  • ${p.block_type} at lines ${p.start_line}–${p.end_line}`);
        });

        const withSuggestions = highBlocks.filter(p => p.suggestion && !p.suggestion.error);
        if (withSuggestions.length > 0) {
            lines.push('');
            lines.push('🤖 WATTWISE AI SUGGESTIONS  (powered by Gemini 2.5 Flash):');
            lines.push('='.repeat(60));
            withSuggestions.forEach(p => {
                const s = p.suggestion!;
                lines.push('');
                lines.push(`▶ ${p.block_type}  (lines ${p.start_line}–${p.end_line})`);
                if (s.explanation) {
                    lines.push(`  Why it's expensive: ${s.explanation}`);
                }
                if (s.suggestions?.length) {
                    lines.push('  Suggested changes:');
                    s.suggestions.forEach(tip => lines.push(`    - ${tip}`));
                }
                if (s.improved_code) {
                    lines.push('  Improved code:');
                    lines.push('  ' + '-'.repeat(56));
                    s.improved_code.split('\n').forEach(l => lines.push(`  ${l}`));
                    lines.push('  ' + '-'.repeat(56));
                }
            });
        }

        highBlocks.filter(p => p.suggestion?.error).forEach(p => {
            lines.push(`  ⚠ Could not get suggestion for ${p.block_type} (lines ${p.start_line}–${p.end_line}): ${p.suggestion!.error}`);
        });
    } else {
        lines.push('✅ All blocks have low to moderate energy consumption. Great work!');
    }

    return lines.join('\n');
}

/**
 * Clear WattWise decorations from the active editor
 */
function clearAnalysis() {
    const editor = vscode.window.activeTextEditor;
    if (editor) {
        decorationManager.clearDecorations(editor);
        vscode.window.showInformationMessage('WattWise: Energy annotations cleared.');
    }
}

/**
 * Train the WattWise ML models
 */
async function trainModels() {
    const result = await vscode.window.showWarningMessage(
        'WattWise will train its energy prediction models. Make sure CSV training data is in the "data" directory. This may take several minutes.',
        'Yes, Train', 'Cancel'
    );

    if (result !== 'Yes, Train') {
        return;
    }

    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: '⚡ WattWise — Training Models',
            cancellable: false
        },
        async (progress) => {
            try {
                progress.report({ message: 'This may take several minutes…' });
                await pythonBridge.trainModels(outputChannel);
                vscode.window.showInformationMessage(
                    '⚡ WattWise: Model training complete! You can now analyze Python files.'
                );
            } catch (error: any) {
                vscode.window.showErrorMessage(
                    `WattWise: Model training failed — ${error.message}. Check the Output panel for details.`
                );
            }
        }
    );
}

/**
 * Extension deactivation
 */
export function deactivate() {
    decorationManager?.clearAll();
    outputChannel?.dispose();
    statusBarItem?.dispose();
}
