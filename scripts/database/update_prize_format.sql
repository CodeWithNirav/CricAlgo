-- Update prize structure to the format the frontend expects
UPDATE contests SET prize_structure = '{"1": 1.0}'::json;