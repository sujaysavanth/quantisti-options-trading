/** The simulator's paper account and trades (services/simulator/app/routers/paper.py). */

export const SIM_API = process.env.NEXT_PUBLIC_SIMULATOR_API ?? 'http://localhost:8082';

export type PaperLeg = {
  identifier?: string;
  strike: number;
  option_type: string;
  expiry: string;
  quantity: number;
  side: string;
  entry_price?: number | null;
  current_price?: number | null;
  exit_price?: number | null;
  pnl: number;
};

export type PaperTrade = {
  id: string;
  symbol: string;
  nickname?: string;
  created_at: string;
  pnl: number;
  legs: PaperLeg[];
  status: 'open' | 'closed';
  expiry?: string | null;
  settles_at?: string | null;
  closed_at?: string | null;
  close_reason?: string | null;
  capital_held?: number | null;
  capital_basis?: string | null;
};

export type PaperAccount = {
  starting_balance: number;
  realised_pnl: number;
  unrealised_pnl: number;
  total_pnl: number;
  account_value: number;
  capital_held: number;
  available: number;
  open_trades: number;
  closed_trades: number;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${SIM_API}${path}`, { cache: 'no-store', ...init });
  if (!response.ok) throw new Error(await errorText(response));
  return (response.status === 204 ? null : await response.json()) as T;
}

/** FastAPI's {"detail": "..."} as plain text. */
export async function errorText(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const detail = JSON.parse(text).detail;
    return typeof detail === 'string' ? detail : text;
  } catch {
    return text || `Request failed (${response.status})`;
  }
}

export const fetchTrades = () => call<PaperTrade[]>('/v1/paper/orders');
export const fetchAccount = () => call<PaperAccount>('/v1/paper/account');
export const closeTrade = (id: string) => call<PaperTrade>(`/v1/paper/orders/${id}/close`, { method: 'POST' });
export const deleteTrade = (id: string) => call<null>(`/v1/paper/orders/${id}`, { method: 'DELETE' });

/** "2h 05m" until `iso`, or null once it has passed. */
export function countdown(iso: string, now: Date = new Date()): string | null {
  const ms = new Date(iso).getTime() - now.getTime();
  if (ms <= 0) return null;
  const minutes = Math.floor(ms / 60_000);
  const days = Math.floor(minutes / 1440);
  const h = Math.floor((minutes % 1440) / 60);
  const m = minutes % 60;
  return days > 0 ? `${days}d ${h}h` : `${h}h ${String(m).padStart(2, '0')}m`;
}

/** e.g. "Fri 9 Oct, 3:30 PM ET". */
export const etDateTime = (iso: string) =>
  new Date(iso).toLocaleString('en-US', {
    timeZone: 'America/New_York', weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  }) + ' ET';
