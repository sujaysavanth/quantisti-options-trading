'use client';

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { STREAM_API, type LiveQuote } from '@/data/live';

type Status = 'loading' | 'live' | 'waiting';

type LiveQuoteState = {
  quote: LiveQuote | null;
  status: Status;
  refresh: () => Promise<void>;
};

const LiveQuoteContext = createContext<LiveQuoteState>({ quote: null, status: 'loading', refresh: async () => {} });

const REFRESH_MS = 15_000;

/** Polls market-stream for the SPX quote once, for every page (nav badge, chain, strategies, paper). */
export function LiveQuoteProvider({ children }: { children: React.ReactNode }) {
  const [quote, setQuote] = useState<LiveQuote | null>(null);
  const [status, setStatus] = useState<Status>('loading');

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${STREAM_API}/v1/quotes/SPX`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`market-stream responded ${response.status}`);
      const data = (await response.json()) as LiveQuote;
      setQuote(data);
      setStatus(data.legs?.length ? 'live' : 'waiting');
    } catch {
      setQuote(null);
      setStatus('waiting');
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(id);
  }, [refresh]);

  return <LiveQuoteContext.Provider value={{ quote, status, refresh }}>{children}</LiveQuoteContext.Provider>;
}

export const useLiveQuote = () => useContext(LiveQuoteContext);
