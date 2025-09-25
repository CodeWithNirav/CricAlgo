-- Test contest workflow directly in database

-- 1. Check contest data
SELECT id, title, entry_fee, commission_pct, prize_structure 
FROM contests 
WHERE title = 'H2H(2)' 
LIMIT 1;

-- 2. Check entries
SELECT e.id, e.user_id, e.amount_debited, e.winner_rank, u.username
FROM entries e
JOIN users u ON e.user_id = u.id
WHERE e.contest_id = 'e5ca0ffe-2188-46fc-8fe5-e4f2253b938c'
ORDER BY e.created_at;

-- 3. Check wallet balances
SELECT user_id, deposit_balance, winning_balance, bonus_balance
FROM wallets
WHERE user_id IN (
    SELECT user_id FROM entries 
    WHERE contest_id = 'e5ca0ffe-2188-46fc-8fe5-e4f2253b938c'
);

-- 4. Select a winner (set winner_rank = 1 for first entry)
UPDATE entries 
SET winner_rank = 1 
WHERE contest_id = 'e5ca0ffe-2188-46fc-8fe5-e4f2253b938c'
AND id = (
    SELECT id FROM entries 
    WHERE contest_id = 'e5ca0ffe-2188-46fc-8fe5-e4f2253b938c'
    ORDER BY created_at 
    LIMIT 1
);

-- 5. Calculate and credit winner amount
-- Winner gets: (49 * 2) - (98 * 0.15) = 98 - 14.7 = 83.3 USDT
UPDATE wallets 
SET winning_balance = winning_balance + 83.3
WHERE user_id = (
    SELECT user_id FROM entries 
    WHERE contest_id = 'e5ca0ffe-2188-46fc-8fe5-e4f2253b938c'
    AND winner_rank = 1
);

-- 6. Update contest status
UPDATE contests 
SET status = 'settled', settled_at = NOW()
WHERE id = 'e5ca0ffe-2188-46fc-8fe5-e4f2253b938c';

-- 7. Check final state
SELECT 'Final wallet balances:' as status;
SELECT user_id, deposit_balance, winning_balance, bonus_balance
FROM wallets
WHERE user_id IN (
    SELECT user_id FROM entries 
    WHERE contest_id = 'e5ca0ffe-2188-46fc-8fe5-e4f2253b938c'
);

SELECT 'Contest status:' as status;
SELECT id, title, status, settled_at
FROM contests 
WHERE id = 'e5ca0ffe-2188-46fc-8fe5-e4f2253b938c';
