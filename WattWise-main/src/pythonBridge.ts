import * as cp from 'child_process';
import * as path from 'path';
import * as vscode from 'vscode';

export interface CodeBlock {
    block_type: string;
    start_line: number;
    end_line: number;
    features?: any;
}

export interface EnergySuggestion {
    block_type: string;
    start_line: number;
    end_line: number;
    explanation: string;
    suggestions: string[];
    improved_code: string;
    error?: string;
}

export interface EnergyPrediction {
    block_type: string;
    start_line: number;
    end_line: number;
    energy_joules: number;
    energy_tier: string;
    tier_confidence: number;
    energy_formatted: string;
    error?: string;
    suggestion?: EnergySuggestion;
}

export class PythonBridge {
    private pythonPath: string;
    private extensionPath: string;

    constructor(extensionPath: string) {
        this.extensionPath = extensionPath;
        this.pythonPath = this.getPythonPath();
    }

    private getPythonPath(): string {
        const config = vscode.workspace.getConfiguration('wattwise');
        return config.get<string>('pythonPath', 'python3');
    }

    /**
     * Extract code blocks and features from Python code
     */
    async extractFeatures(code: string): Promise<CodeBlock[]> {
        const scriptPath = path.join(this.extensionPath, 'python', 'extract_features.py');

        return new Promise((resolve, reject) => {
            const process = cp.spawn(this.pythonPath, [scriptPath, '--stdin']);

            let stdout = '';
            let stderr = '';

            process.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            process.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            process.on('close', (code) => {
                if (code !== 0) {
                    reject(new Error(`Feature extraction failed: ${stderr}`));
                    return;
                }

                try {
                    const blocks = JSON.parse(stdout);

                    if (blocks.error) {
                        reject(new Error(blocks.error));
                        return;
                    }

                    resolve(blocks);
                } catch (e) {
                    reject(new Error(`Failed to parse feature extraction output: ${e}`));
                }
            });

            process.on('error', (err) => {
                reject(new Error(`Failed to spawn Python process: ${err.message}`));
            });

            // Send code via stdin
            process.stdin.write(code);
            process.stdin.end();
        });
    }

    /**
     * Predict energy consumption for extracted blocks
     */
    async predictEnergy(blocks: CodeBlock[]): Promise<EnergyPrediction[]> {
        const scriptPath = path.join(this.extensionPath, 'python', 'predict_energy.py');
        const modelsPath = path.join(this.extensionPath, 'python', 'models');

        // Check if models exist
        if (!require('fs').existsSync(modelsPath)) {
            throw new Error('Models not found. Please train models first using "Energy: Train Energy Prediction Models" command.');
        }

        return new Promise((resolve, reject) => {
            const process = cp.spawn(this.pythonPath, [scriptPath], {
                cwd: path.join(this.extensionPath, 'python')
            });

            let stdout = '';
            let stderr = '';

            process.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            process.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            process.on('close', (code) => {
                if (code !== 0) {
                    reject(new Error(`Energy prediction failed: ${stderr}`));
                    return;
                }

                try {
                    const predictions = JSON.parse(stdout);

                    if (predictions.error) {
                        reject(new Error(predictions.error));
                        return;
                    }

                    resolve(predictions);
                } catch (e) {
                    reject(new Error(`Failed to parse prediction output: ${e}`));
                }
            });

            process.on('error', (err) => {
                reject(new Error(`Failed to spawn Python process: ${err.message}`));
            });

            // Send blocks via stdin as JSON
            process.stdin.write(JSON.stringify(blocks));
            process.stdin.end();
        });
    }

    /**
     * Train models using the training script
     */
    async trainModels(outputChannel: vscode.OutputChannel): Promise<void> {
        const scriptPath = path.join(this.extensionPath, 'python', 'train_and_save_models.py');
        const dataPath = path.join(this.extensionPath, 'data');

        // Check if training data exists
        const fs = require('fs');
        const requiredFiles = [
            'X_train_base_features.csv',
            'X_test_base_features.csv',
            'target_variables.csv'
        ];

        for (const file of requiredFiles) {
            const filePath = path.join(dataPath, file);
            if (!fs.existsSync(filePath)) {
                throw new Error(`Training data not found: ${file}. Please place CSV files in the 'data' directory.`);
            }
        }

        return new Promise((resolve, reject) => {
            outputChannel.show();
            outputChannel.appendLine('Starting model training...');
            outputChannel.appendLine('This may take several minutes...\n');

            const process = cp.spawn(this.pythonPath, [scriptPath], {
                cwd: path.join(this.extensionPath, 'python')
            });

            process.stdout.on('data', (data) => {
                outputChannel.append(data.toString());
            });

            process.stderr.on('data', (data) => {
                outputChannel.append(data.toString());
            });

            process.on('close', (code) => {
                if (code !== 0) {
                    outputChannel.appendLine('\n❌ Model training failed!');
                    reject(new Error('Model training failed. Check output for details.'));
                    return;
                }

                outputChannel.appendLine('\n✅ Model training completed successfully!');
                resolve();
            });

            process.on('error', (err) => {
                outputChannel.appendLine(`\n❌ Error: ${err.message}`);
                reject(err);
            });
        });
    }

    /**
     * Get Gemini AI suggestions for high-energy code blocks
     */
    async getSuggestions(
        sourceCode: string,
        highEnergyBlocks: EnergyPrediction[],
        apiKey: string
    ): Promise<EnergySuggestion[]> {
        const scriptPath = path.join(this.extensionPath, 'python', 'suggest_improvements.py');

        const inputPayload = {
            source_code: sourceCode,
            blocks: highEnergyBlocks.map(b => ({
                block_type: b.block_type,
                start_line: b.start_line,
                end_line: b.end_line,
                energy_joules: b.energy_joules
            })),
            api_key: apiKey
        };

        return new Promise((resolve, reject) => {
            const proc = cp.spawn(this.pythonPath, [scriptPath]);

            let stdout = '';
            let stderr = '';

            proc.stdout.on('data', (data) => { stdout += data.toString(); });
            proc.stderr.on('data', (data) => { stderr += data.toString(); });

            proc.on('close', (code) => {
                if (code !== 0) {
                    reject(new Error(`Suggestion script failed: ${stderr}`));
                    return;
                }

                try {
                    const result = JSON.parse(stdout);

                    if (result && result.error) {
                        reject(new Error(result.error));
                        return;
                    }

                    resolve(result as EnergySuggestion[]);
                } catch (e) {
                    reject(new Error(`Failed to parse suggestion output: ${e}`));
                }
            });

            proc.on('error', (err) => {
                reject(new Error(`Failed to spawn suggestion process: ${err.message}`));
            });

            proc.stdin.write(JSON.stringify(inputPayload));
            proc.stdin.end();
        });
    }

    /**
     * Analyze a Python file and get energy predictions
     */
    async analyzeFile(code: string): Promise<EnergyPrediction[]> {
        // Step 1: Extract features
        const blocks = await this.extractFeatures(code);

        if (!blocks || blocks.length === 0) {
            return [];
        }

        // Step 2: Predict energy
        const predictions = await this.predictEnergy(blocks);

        return predictions;
    }
}
