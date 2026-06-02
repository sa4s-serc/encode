import * as vscode from 'vscode';
import { PythonBridge, EnergyPrediction } from './pythonBridge';
import { EnergyDecorationManager } from './decorations';

let pythonBridge: PythonBridge;
let decorationManager: EnergyDecorationManager;
let outputChannel: vscode.OutputChannel;
let statusBarItem: vscode.StatusBarItem;

/**
 * Extension activation
 */
export function activate(context: vscode.ExtensionContext) {
    console.log('Energy Estimator extension is now active');

    // Initialize components
    pythonBridge = new PythonBridge(context.extensionPath);
    decorationManager = new EnergyDecorationManager();
    outputChannel = vscode.window.createOutputChannel('Energy Estimator');

    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'energyEstimator.analyzeFile';
    statusBarItem.text = '$(zap) Analyze Energy';
    statusBarItem.tooltip = 'Analyze energy consumption of Python code';
    context.subscriptions.push(statusBarItem);

    // Show status bar only for Python files
    updateStatusBarVisibility();

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('energyEstimator.analyzeFile', analyzeCurrentFile)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('energyEstimator.clearAnalysis', clearAnalysis)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('energyEstimator.trainModels', trainModels)
    );

    // Register event handlers
    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(updateStatusBarVisibility)
    );

    // Show welcome message
    vscode.window.showInformationMessage(
        'Energy Estimator extension activated! Use "Analyze Energy Consumption" command on Python files.',
        'Train Models'
    ).then(selection => {
        if (selection === 'Train Models') {
            vscode.commands.executeCommand('energyEstimator.trainModels');
        }
    });
}

/**
 * Update status bar visibility based on current file
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
 * Analyze current file
 */
async function analyzeCurrentFile() {
    const editor = vscode.window.activeTextEditor;

    if (!editor) {
        vscode.window.showErrorMessage('No active editor');
        return;
    }

    if (editor.document.languageId !== 'python') {
        vscode.window.showErrorMessage('This command only works with Python files');
        return;
    }

    const code = editor.document.getText();

    if (!code.trim()) {
        vscode.window.showErrorMessage('File is empty');
        return;
    }

    // Show progress
    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'Analyzing energy consumption...',
            cancellable: false
        },
        async (progress) => {
            try {
                progress.report({ increment: 0, message: 'Extracting code blocks...' });

                const predictions = await pythonBridge.analyzeFile(code);

                progress.report({ increment: 50, message: 'Predicting energy consumption...' });

                if (!predictions || predictions.length === 0) {
                    vscode.window.showInformationMessage('No code blocks found to analyze');
                    return;
                }

                progress.report({ increment: 90, message: 'Applying decorations...' });

                // Apply decorations
                decorationManager.applyDecorations(editor, predictions);

                // Show summary
                const summary = generateSummary(predictions);
                outputChannel.clear();
                outputChannel.appendLine('Energy Analysis Results');
                outputChannel.appendLine('='.repeat(60));
                outputChannel.appendLine(summary);
                outputChannel.show(true);

                vscode.window.showInformationMessage(
                    `Analyzed ${predictions.length} code block(s). See hover for details.`
                );

            } catch (error: any) {
                const errorMessage = error.message || 'Unknown error';
                outputChannel.appendLine(`Error: ${errorMessage}`);
                outputChannel.show();

                if (errorMessage.includes('Models not found')) {
                    vscode.window.showErrorMessage(
                        'Models not trained yet. Train models first.',
                        'Train Now'
                    ).then(selection => {
                        if (selection === 'Train Now') {
                            vscode.commands.executeCommand('energyEstimator.trainModels');
                        }
                    });
                } else {
                    vscode.window.showErrorMessage(`Energy analysis failed: ${errorMessage}`);
                }
            }
        }
    );
}

/**
 * Generate summary of predictions
 */
function generateSummary(predictions: EnergyPrediction[]): string {
    const lines: string[] = [];

    // Overall statistics
    const totalEnergy = predictions.reduce((sum, p) => sum + (p.energy_joules || 0), 0);
    const avgEnergy = totalEnergy / predictions.length;

    const tierCounts = {
        Low: 0,
        Medium: 0,
        High: 0
    };

    predictions.forEach(p => {
        if (p.energy_tier in tierCounts) {
            tierCounts[p.energy_tier as keyof typeof tierCounts]++;
        }
    });

    lines.push(`Total blocks analyzed: ${predictions.length}`);
    lines.push(`Total estimated energy: ${totalEnergy.toExponential(3)} J`);
    lines.push(`Average energy per block: ${avgEnergy.toExponential(3)} J`);
    lines.push('');
    lines.push('Energy Tier Distribution:');
    lines.push(`  🟢 Low:    ${tierCounts.Low} blocks`);
    lines.push(`  🟡 Medium: ${tierCounts.Medium} blocks`);
    lines.push(`  🔴 High:   ${tierCounts.High} blocks`);
    lines.push('');
    lines.push('Block Details:');
    lines.push('-'.repeat(60));

    // Sort by energy consumption (highest first)
    const sorted = [...predictions].sort((a, b) => (b.energy_joules || 0) - (a.energy_joules || 0));

    sorted.forEach((p, index) => {
        const tierEmoji = {
            'Low': '🟢',
            'Medium': '🟡',
            'High': '🔴'
        }[p.energy_tier] || '⚪';

        lines.push(`${index + 1}. ${tierEmoji} ${p.block_type} (lines ${p.start_line}-${p.end_line})`);
        lines.push(`   Energy: ${p.energy_joules.toExponential(3)} J | Tier: ${p.energy_tier}`);
        lines.push('');
    });

    // Recommendations
    const highEnergyBlocks = predictions.filter(p => p.energy_tier === 'High');
    if (highEnergyBlocks.length > 0) {
        lines.push('⚠️  RECOMMENDATIONS:');
        lines.push('-'.repeat(60));
        lines.push(`Found ${highEnergyBlocks.length} high-energy block(s). Consider optimizing:`);
        highEnergyBlocks.forEach(p => {
            lines.push(`  • ${p.block_type} at lines ${p.start_line}-${p.end_line}`);
        });
    } else {
        lines.push('✅ All blocks have low to moderate energy consumption. Great job!');
    }

    return lines.join('\n');
}

/**
 * Clear analysis decorations
 */
function clearAnalysis() {
    const editor = vscode.window.activeTextEditor;

    if (editor) {
        decorationManager.clearDecorations(editor);
        vscode.window.showInformationMessage('Energy analysis cleared');
    }
}

/**
 * Train models
 */
async function trainModels() {
    const result = await vscode.window.showWarningMessage(
        'This will train energy prediction models. Make sure training data (CSV files) are in the "data" directory. This may take several minutes. Continue?',
        'Yes', 'No'
    );

    if (result !== 'Yes') {
        return;
    }

    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'Training energy prediction models...',
            cancellable: false
        },
        async (progress) => {
            try {
                progress.report({ message: 'This may take several minutes...' });

                await pythonBridge.trainModels(outputChannel);

                vscode.window.showInformationMessage(
                    'Model training completed successfully! You can now analyze Python files.'
                );

            } catch (error: any) {
                vscode.window.showErrorMessage(
                    `Model training failed: ${error.message}. Check Output panel for details.`
                );
            }
        }
    );
}

/**
 * Extension deactivation
 */
export function deactivate() {
    if (decorationManager) {
        decorationManager.clearAll();
    }

    if (outputChannel) {
        outputChannel.dispose();
    }

    if (statusBarItem) {
        statusBarItem.dispose();
    }
}
