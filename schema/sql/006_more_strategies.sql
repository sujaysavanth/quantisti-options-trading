-- Add more strategies to the simulator
-- Includes Ratio Spreads, Butterflies, Jade Lizards, and Institutional Strategies

INSERT INTO strategies (name, strategy_type, description)
SELECT v.name, v.strategy_type, v.description FROM (VALUES
-- Weekly Income / Directional
('Call Ratio Spread', 'CALL_RATIO_SPREAD', 'Buy 1 ATM call, sell 2 OTM calls. Profit from small upward move, risk on large upward move.'),
('Put Ratio Spread', 'PUT_RATIO_SPREAD', 'Buy 1 ATM put, sell 2 OTM puts. Profit from small downward move, risk on large downward move.'),
('Long Call Butterfly', 'LONG_CALL_BUTTERFLY', 'Buy 1 ITM call, sell 2 ATM calls, buy 1 OTM call. Profit from low volatility around ATM.'),
('Long Put Butterfly', 'LONG_PUT_BUTTERFLY', 'Buy 1 ITM put, sell 2 ATM puts, buy 1 OTM put. Profit from low volatility around ATM.'),
('Jade Lizard', 'JADE_LIZARD', 'Sell OTM put and OTM call spread. Bullish/Neutral strategy with no upside risk.'),
('Reverse Jade Lizard', 'REVERSE_JADE_LIZARD', 'Sell OTM call and OTM put spread. Bearish/Neutral strategy with no downside risk.'),

-- Advanced / Institutional
('Call Ratio Backspread', 'CALL_RATIO_BACKSPREAD', 'Sell 1 ATM call, buy 2 OTM calls. Unlimited profit on explosion, small loss if flat, profit if crashes.'),
('Put Ratio Backspread', 'PUT_RATIO_BACKSPREAD', 'Sell 1 ATM put, buy 2 OTM puts. Unlimited profit on crash, small loss if flat, profit if rallies.'),
('Broken Wing Butterfly (Call)', 'BWB_CALL', 'Buy ATM, Sell 2 OTM, Buy Far OTM. Skewed butterfly for directional bias and credit entry.')
) AS v(name, strategy_type, description)
-- strategies has no unique key, so ON CONFLICT never fired and re-runs duplicated rows
WHERE NOT EXISTS (SELECT 1 FROM strategies s WHERE s.strategy_type = v.strategy_type);

-- Get strategy IDs and insert legs
DO $$
DECLARE
    call_ratio_id UUID;
    put_ratio_id UUID;
    call_fly_id UUID;
    put_fly_id UUID;
    jade_lizard_id UUID;
    rev_jade_lizard_id UUID;
    call_backspread_id UUID;
    put_backspread_id UUID;
    bwb_call_id UUID;
BEGIN
    -- Get strategy IDs
    SELECT id INTO call_ratio_id FROM strategies WHERE strategy_type = 'CALL_RATIO_SPREAD' LIMIT 1;
    SELECT id INTO put_ratio_id FROM strategies WHERE strategy_type = 'PUT_RATIO_SPREAD' LIMIT 1;
    SELECT id INTO call_fly_id FROM strategies WHERE strategy_type = 'LONG_CALL_BUTTERFLY' LIMIT 1;
    SELECT id INTO put_fly_id FROM strategies WHERE strategy_type = 'LONG_PUT_BUTTERFLY' LIMIT 1;
    SELECT id INTO jade_lizard_id FROM strategies WHERE strategy_type = 'JADE_LIZARD' LIMIT 1;
    SELECT id INTO rev_jade_lizard_id FROM strategies WHERE strategy_type = 'REVERSE_JADE_LIZARD' LIMIT 1;
    SELECT id INTO call_backspread_id FROM strategies WHERE strategy_type = 'CALL_RATIO_BACKSPREAD' LIMIT 1;
    SELECT id INTO put_backspread_id FROM strategies WHERE strategy_type = 'PUT_RATIO_BACKSPREAD' LIMIT 1;
    SELECT id INTO bwb_call_id FROM strategies WHERE strategy_type = 'BWB_CALL' LIMIT 1;

    -- Call Ratio Spread (Buy ATM, Sell 2x OTM +25)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = call_ratio_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
        (call_ratio_id, 'BUY', 'C', 0, 1, 1),
        (call_ratio_id, 'SELL', 'C', 25, 2, 2);
    END IF;

    -- Put Ratio Spread (Buy ATM, Sell 2x OTM -25)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = put_ratio_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
        (put_ratio_id, 'BUY', 'P', 0, 1, 1),
        (put_ratio_id, 'SELL', 'P', -25, 2, 2);
    END IF;

    -- Long Call Butterfly (Buy ITM -25, Sell 2x ATM, Buy OTM +25)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = call_fly_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
        (call_fly_id, 'BUY', 'C', -25, 1, 1),
        (call_fly_id, 'SELL', 'C', 0, 2, 2),
        (call_fly_id, 'BUY', 'C', 25, 1, 3);
    END IF;

    -- Long Put Butterfly (Buy ITM +25, Sell 2x ATM, Buy OTM -25)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = put_fly_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
        (put_fly_id, 'BUY', 'P', 25, 1, 1),
        (put_fly_id, 'SELL', 'P', 0, 2, 2),
        (put_fly_id, 'BUY', 'P', -25, 1, 3);
    END IF;

    -- Jade Lizard (Sell OTM Put -25, Sell OTM Call +25, Buy OTM Call +50)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = jade_lizard_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
        (jade_lizard_id, 'SELL', 'P', -25, 1, 1),
        (jade_lizard_id, 'SELL', 'C', 25, 1, 2),
        (jade_lizard_id, 'BUY', 'C', 50, 1, 3);
    END IF;

    -- Reverse Jade Lizard (Sell OTM Call +25, Sell OTM Put -25, Buy OTM Put -50)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = rev_jade_lizard_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
        (rev_jade_lizard_id, 'SELL', 'C', 25, 1, 1),
        (rev_jade_lizard_id, 'SELL', 'P', -25, 1, 2),
        (rev_jade_lizard_id, 'BUY', 'P', -50, 1, 3);
    END IF;

    -- Call Ratio Backspread (Sell ATM, Buy 2x OTM +25)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = call_backspread_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
        (call_backspread_id, 'SELL', 'C', 0, 1, 1),
        (call_backspread_id, 'BUY', 'C', 25, 2, 2);
    END IF;

    -- Put Ratio Backspread (Sell ATM, Buy 2x OTM -25)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = put_backspread_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
        (put_backspread_id, 'SELL', 'P', 0, 1, 1),
        (put_backspread_id, 'BUY', 'P', -25, 2, 2);
    END IF;

    -- Broken Wing Butterfly Call (Buy ATM, Sell 2x +25, Buy +65)
    -- Note the "Broken" wing is 40 wide (25 to 65) vs 25 wide (0 to 25)
    IF NOT EXISTS (SELECT 1 FROM strategy_legs WHERE strategy_id = bwb_call_id) THEN
    INSERT INTO strategy_legs (strategy_id, action, option_type, strike_offset, quantity, leg_order) VALUES
        (bwb_call_id, 'BUY', 'C', 0, 1, 1),
        (bwb_call_id, 'SELL', 'C', 25, 2, 2),
        (bwb_call_id, 'BUY', 'C', 65, 1, 3);
    END IF;

END $$;
