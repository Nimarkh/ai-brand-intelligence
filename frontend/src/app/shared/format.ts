/** Shared display formatting. Does not change stored values. */

export const UNAVAILABLE = '—';

export function formatDisplayDate(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date);
}

export function formatDisplayDateTime(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'UTC',
  }).format(date);
}

/** Date for UI lists/cards; missing values show as em dash. */
export function formatDateOrDash(value: string | null | undefined): string {
  return formatDisplayDate(value) ?? UNAVAILABLE;
}

/** Date-time for UI; missing values show as em dash. */
export function formatDateTimeOrDash(value: string | null | undefined): string {
  return formatDisplayDateTime(value) ?? UNAVAILABLE;
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return UNAVAILABLE;
  }
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value);
}

export function formatMilliseconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return UNAVAILABLE;
  }
  return `${formatCount(Math.round(value))} ms`;
}

/**
 * Compact metric score for rings and cards (e.g. "72" or "72.5").
 * Does not append "/ 100".
 */
export function formatMetricScore(value: number | null | undefined, maxFractionDigits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return UNAVAILABLE;
  }
  const rounded = Math.round(value * 100) / 100;
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: maxFractionDigits,
    minimumFractionDigits: 0,
  }).format(rounded);
}

/** Score with scale, e.g. "78.4 / 100". */
export function formatScoreOutOf100(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return UNAVAILABLE;
  }
  const rounded = Math.round(value * 100) / 100;
  const display = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(rounded);
  return `${display} / 100`;
}

export function formatPercent(value: number | null | undefined, maxFractionDigits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return UNAVAILABLE;
  }
  const pct = Math.round(value * 1000) / 10;
  return `${new Intl.NumberFormat('en-US', {
    maximumFractionDigits: maxFractionDigits,
    minimumFractionDigits: 0,
  }).format(pct)}%`;
}
