# MiniSQL

Miniature relational database engine. Hand-written SQL parser + storage + index.

## Architecture
CLI (minisql.py) -> Engine (engine.py) -> Storage (storage.py) -> data/<table>.json

- storage.py - Table, PK dict index O(1), JSON persistence, type checks
- engine.py - Parser (regex), WHERE, transactions, EXPLAIN
- minisql.py - REPL
- tests/test_engine.py - 6 tests

## SQL Supported
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, active BOOLEAN)
INSERT INTO users VALUES (1, 'Ada', true)
SELECT * FROM users WHERE active = true
SELECT name FROM users WHERE id = 1
UPDATE users SET name = 'Ada L' WHERE id = 1
DELETE FROM users WHERE id = 1
BEGIN / COMMIT / ROLLBACK

## Query Plans
- WHERE id = 1 -> INDEX SCAN (PK) O(1)
- WHERE name = 'x' -> FULL SCAN O(n)

## Run
python minisql.py

## Test
python -m pytest tests/test_engine.py -v -s

## Results
- 6/6 tests passed: CRUD + WHERE, duplicate PK, invalid SQL, persistence, rollback, 10k rows
- 10k rows inserted, indexed PK lookup vs full scan measured
- Persistence: restart reloads from JSON
- Transactions: ROLLBACK discards, COMMIT persists