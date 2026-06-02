import * as vscode from 'vscode';
import { EnergyPrediction } from './pythonBridge';

export class EnergyDecorationManager {
    private decorationType: vscode.TextEditorDecorationType;
    private activeDecorations: Map<string, vscode.DecorationOptions[]> = new Map();

    constructor() {
        this.decorationType = vscode.window.createTextEditorDecorationType({
            after: {
                margin: '0 0 0 3em',
                fontStyle: 'italic',
                fontWeight: 'normal'
            },
            rangeBehavior: vscode.DecorationRangeBehavior.ClosedClosed
        });
    }

    /**
     * Get color for energy tier
     */
    private getTierColor(tier: string): string {
        switch (tier.toLowerCase()) {
            case 'low':
                return 'rgba(0, 255, 0, 0.6)';  // Green
            case 'medium':
                return 'rgba(255, 165, 0, 0.6)'; // Orange
            case 'high':
                return 'rgba(255, 0, 0, 0.6)';   // Red
            default:
                return 'rgba(128, 128, 128, 0.6)'; // Gray
        }
    }

    /**
     * Format decoration text
     */
    private formatDecoration(prediction: EnergyPrediction): string {
        const config = vscode.workspace.getConfiguration('energyEstimator');
        const format = config.get<string>('decorationFormat', '[Est: {energy}J | Tier: {tier}]');

        return format
            .replace('{energy}', prediction.energy_joules.toExponential(2))
            .replace('{tier}', prediction.energy_tier);
    }

    /**
     * Create hover content
     */
    private createHoverContent(prediction: EnergyPrediction): vscode.MarkdownString {
        const markdown = new vscode.MarkdownString();
        markdown.isTrusted = true;

        const tierEmoji = {
            'Low': '🟢',
            'Medium': '🟡',
            'High': '🔴'
        }[prediction.energy_tier] || '⚪';

        markdown.appendMarkdown(`### ${tierEmoji} Energy Estimate\n\n`);
        markdown.appendMarkdown(`**Block Type:** \`${prediction.block_type}\`\n\n`);
        markdown.appendMarkdown(`**Energy Consumption:** ${prediction.energy_joules.toFixed(6)} J\n\n`);
        markdown.appendMarkdown(`**Energy Tier:** ${prediction.energy_tier}\n\n`);

        if (prediction.tier_confidence) {
            const confidencePercent = (prediction.tier_confidence * 100).toFixed(1);
            markdown.appendMarkdown(`**Confidence:** ${confidencePercent}%\n\n`);
        }

        markdown.appendMarkdown(`---\n\n`);

        // Add tier explanation
        if (prediction.energy_tier === 'Low') {
            markdown.appendMarkdown(`✅ This code block has **low energy consumption**. Good job!\n\n`);
        } else if (prediction.energy_tier === 'Medium') {
            markdown.appendMarkdown(`⚠️ This code block has **moderate energy consumption**. Consider optimization if it's in a hot path.\n\n`);
        } else if (prediction.energy_tier === 'High') {
            markdown.appendMarkdown(`⚠️ This code block has **high energy consumption**. Consider refactoring for efficiency.\n\n`);
        }

        markdown.appendMarkdown(`*Lines ${prediction.start_line}-${prediction.end_line}*`);

        return markdown;
    }

    /**
     * Apply decorations to editor
     */
    applyDecorations(editor: vscode.TextEditor, predictions: EnergyPrediction[]): void {
        const config = vscode.workspace.getConfiguration('energyEstimator');
        const showInline = config.get<boolean>('showInlineDecorations', true);

        if (!showInline) {
            return;
        }

        const decorations: vscode.DecorationOptions[] = [];

        for (const prediction of predictions) {
            if (prediction.error) {
                continue; // Skip blocks with errors
            }

            // Create decoration at the end of the start line
            const line = editor.document.lineAt(prediction.start_line - 1); // Convert to 0-based
            const range = new vscode.Range(
                line.range.end,
                line.range.end
            );

            const decorationText = this.formatDecoration(prediction);
            const tierColor = this.getTierColor(prediction.energy_tier);

            const decoration: vscode.DecorationOptions = {
                range: range,
                renderOptions: {
                    after: {
                        contentText: ` ${decorationText}`,
                        color: tierColor
                    }
                },
                hoverMessage: this.createHoverContent(prediction)
            };

            decorations.push(decoration);
        }

        // Apply decorations
        editor.setDecorations(this.decorationType, decorations);

        // Store decorations for this document
        this.activeDecorations.set(editor.document.uri.toString(), decorations);
    }

    /**
     * Clear decorations from editor
     */
    clearDecorations(editor: vscode.TextEditor): void {
        editor.setDecorations(this.decorationType, []);
        this.activeDecorations.delete(editor.document.uri.toString());
    }

    /**
     * Clear all decorations
     */
    clearAll(): void {
        this.activeDecorations.clear();
        this.decorationType.dispose();
    }

    /**
     * Get active decorations for a document
     */
    getDecorations(uri: string): vscode.DecorationOptions[] | undefined {
        return this.activeDecorations.get(uri);
    }
}
