-- Yahoo reports open interest as 0 for every SPX contract outside the session.
-- That means "unknown", not "nobody holds this", so a Yahoo capture in which every
-- row has OI 0 gets NULL instead (e.g. the 01:45 ET capture of 2026-10-01).
-- A capture = one (snapshot_date, quoted_at). Safe to re-run: afterwards no capture is all zeros.
UPDATE option_chain_snapshots s
SET open_interest = NULL
FROM (
    SELECT snapshot_date, quoted_at
    FROM option_chain_snapshots
    WHERE source = 'yahoo'
    GROUP BY snapshot_date, quoted_at
    HAVING max(open_interest) = 0
) zero
WHERE s.source = 'yahoo'
  AND s.snapshot_date = zero.snapshot_date
  AND s.quoted_at = zero.quoted_at;
