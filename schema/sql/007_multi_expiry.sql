-- Support for Multi-Expiry Strategies (Calendar/Diagonal)

-- Add expiry_offset to strategy_legs
-- 0 = Current/Next Expiry (Near week)
-- 1 = Next Expiry + 1 week (Far week)
-- etc.
ALTER TABLE strategy_legs ADD COLUMN IF NOT EXISTS expiry_offset INT NOT NULL DEFAULT 0;

-- Add new strategies
INSERT INTO strategies (name, strategy_type, description) VALUES
('Long Calendar Spread', 'LONG_CALENDAR_SPREAD', 'Sell near-term ATM call, buy longer-term ATM call. Profit from time decay of the short option.'),
('Long Diagonal Spread', 'LONG_DIAGONAL_SPREAD', 'Sell near-term OTM call, buy longer-term ITM call. Directional trade with time-decay benefit.')
ON CONFLICT DO NOTHING;

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
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order, expiry_offset) VALUES
    (calendar_id, 'SELL', 'CE', 0, 1, 1, 0),
    (calendar_id, 'BUY', 'CE', 0, 1, 2, 1);

    -- Long Diagonal Spread (Call)
    -- Leg 1: Sell OTM (+100), Near Week (Offset 0)
    -- Leg 2: Buy ITM (-100), Next Week (Offset 1)
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order, expiry_offset) VALUES
    (diagonal_id, 'SELL', 'CE', 100, 1, 1, 0),
    (diagonal_id, 'BUY', 'CE', -100, 1, 2, 1);

END $$;
