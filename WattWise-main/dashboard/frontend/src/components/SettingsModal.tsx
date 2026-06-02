import type { FormEvent } from 'react';

import type { CostConfig } from '../types';
import { SETTINGS_BLOCK_TYPES } from '../utils/dashboard';

interface SettingsModalProps {
  config: CostConfig;
  onClose: () => void;
  onSave: (config: CostConfig) => void | Promise<void>;
}

export function SettingsModal({ config, onClose, onSave }: SettingsModalProps) {
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const nextConfig: CostConfig = {
      awsRateKwh: Number(formData.get('awsRateKwh')),
      co2KgPerKwh: config.co2KgPerKwh,
      defaultCallsPerDay: {},
    };

    SETTINGS_BLOCK_TYPES.forEach(blockType => {
      nextConfig.defaultCallsPerDay[blockType] = Number(formData.get(blockType));
    });

    await onSave(nextConfig);
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <div className="panel-eyebrow">Call-rate assumptions</div>
        <h2 className="modal-title">Repository cost model</h2>
        <p className="modal-copy">
          Adjust default daily execution counts per block type. WattWise writes these values back to <code>.wattwise.yml</code>.
        </p>

        <form id="settings-form" onSubmit={handleSubmit}>
          <label className="settings-row">
            <span>AWS rate / kWh (₹)</span>
            <input type="number" min="0.001" step="0.001" name="awsRateKwh" defaultValue={config.awsRateKwh} />
          </label>

          {SETTINGS_BLOCK_TYPES.map(blockType => (
            <label key={blockType} className="settings-row">
              <span>{blockType}</span>
              <input
                type="number"
                min="1"
                step="1"
                name={blockType}
                defaultValue={config.defaultCallsPerDay[blockType]}
              />
            </label>
          ))}

          <div className="modal-actions">
            <button className="ghost-button" type="button" onClick={onClose}>
              Cancel
            </button>
            <button className="primary-button" type="submit">
              Save assumptions
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
