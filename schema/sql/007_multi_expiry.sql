-- Support for Multi-Expiry Strategies (Calendar/Diagonal)

-- Add expiry_offset to strategy_legs
-- 0 = Current/Next Expiry (Near week)
-- 1 = Next Expiry + 1 week (Far week)
-- etc.
ALTER TABLE strategy_legs ADD COLUMN IF NOT EXISTS expiry_offset INT NOT NULL DEFAULT 0;

-- Add new strategies
INSERT INTO strategies (name, strategy_type, description)
SELECT v.name, v.strategy_type, v.description FROM (VALUES
('Long Calendar Spread', 'LONG_CALENDAR_SPREAD', 'Sell near-term ATM call, buy longer-term ATM call. Profit from time decay of the short option.'),
('Long Diagonal Spread', 'LONG_DIAGONAL_SPREAD', 'Sell near-term OTM call, buy longer-term ITM call. Directional trade with time-decay benefit.')
) AS v(name, strategy_type, description)
-- strategies has no unique key, so ON CONFLICT never fired and re-runs duplicated rows
WHERE NOT EXISTS (SELECT 1 FROM strategies s WHERE s.strategy_type = v.strategy_type);

-- Insert legs for new strategies
DO $$
DECLARE
    calendar_id UUID;
    diagonal_id UUID;
BEGIN
    SELECT id INTO calendar_id FROM strategies WHERE strategy_type = 'LONG_CALENDAR_SPREAD' LIMIT 1;
    SELECT id INTO diagonal_id FROM strategies WHERE strategy_type = 'LONG_DIAGONAL_SPREAD' LIMIT 1;

    -- Long Calendar Spread (Call)
    -- Leg 1: Sell ATM, Near Week (Offset 0)
    -- Leg 2: Buy ATM, Next Week (Offset 1)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = calendar_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order, expiry_offset) VALUES
        (calendar_id, 'SELL', 'C', 0, 1, 1, 0),
        (calendar_id, 'BUY', 'C', 0, 1, 2, 1);
    END IF;

    -- Long Diagonal Spread (Call)
    -- Leg 1: Sell OTM (+25), Near Week (Offset 0)
    -- Leg 2: Buy ITM (-25), Next Week (Offset 1)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = diagonal_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order, expiry_offset) VALUES
        (diagonal_id, 'SELL', 'C', 25, 1, 1, 0),
        (diagonal_id, 'BUY', 'C', -25, 1, 2, 1);
    END IF;

END $$;
