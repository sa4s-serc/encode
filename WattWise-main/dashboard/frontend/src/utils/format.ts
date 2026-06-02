export function formatNumber(value: number | string | null | undefined): string {
  return new Intl.NumberFormat('en-US').format(Number(value ?? 0));
}

export function formatCurrency(value: number | string | null | undefined): string {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: numericValue >= 100 ? 0 : 2,
  }).format(numericValue);
}

export function formatCurrencyCompact(value: number | string | null | undefined): string {
  return formatCurrency(value).replace('.00', '');
}

export function formatKwh(value: number | null | undefined): string {
  const numericValue = Number(value ?? 0);
  return numericValue.toFixed(numericValue >= 100 ? 0 : 1);
}

export function formatKg(value: number | null | undefined): string {
  const numericValue = Number(value ?? 0);
  return numericValue.toFixed(numericValue >= 100 ? 0 : 1);
}

export function formatRelativeTime(isoString?: string | null): string {
  if (!isoString) return 'just now';
  const scannedAt = new Date(isoString).getTime();
  const deltaMs = Date.now() - scannedAt;
  const minutes = Math.round(deltaMs / 60000);
  if (minutes <= 1) return 'just now';
  if (minutes < 60) return minutes + 'm ago';
  const hours = Math.round(minutes / 60);
  if (hours < 24) return hours + 'h ago';
  return Math.round(hours / 24) + 'd ago';
}
