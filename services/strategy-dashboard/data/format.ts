/** SPX contract multiplier: one contract is 100 x the index points. */
export const MULTIPLIER = 100;

const usdFmt = (digits: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: digits, maximumFractionDigits: digits });

/** $12,345 (or with `digits` decimals). */
export const usd = (value: number | null | undefined, digits = 0) => usdFmt(digits).format(value ?? 0);

/** $137K */
export const usdK = (value: number | null | undefined) => `$${Math.round((value ?? 0) / 1000).toLocaleString('en-US')}K`;

export const num = (value: number | null | undefined, digits = 0) =>
  (value ?? 0).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const shortDate = (value: string | number | Date) =>
  new Date(value).toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' });

export const optionCode = (optionType: 'CALL' | 'PUT') => (optionType === 'CALL' ? 'C' : 'P');
