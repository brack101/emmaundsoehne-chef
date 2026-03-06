-- Nützliche Abfragen für die Schachspielbaum-Datenbank
-- Verwendung: sqlite3 chess_games.db < queries.sql

-- 1. Überblick
SELECT
    'Stellungen'  AS typ, COUNT(*) AS anzahl FROM positions
UNION ALL SELECT
    'Züge',               COUNT(*)            FROM moves
UNION ALL SELECT
    'Mattstellungen',     COUNT(*)            FROM positions WHERE is_checkmate = 1
UNION ALL SELECT
    'Pattstellungen',     COUNT(*)            FROM positions WHERE is_stalemate = 1;

-- 2. Stellungen pro Tiefe
SELECT
    depth_first AS tiefe,
    COUNT(*)    AS stellungen
FROM positions
GROUP BY depth_first
ORDER BY depth_first;

-- 3. Alle legalen Züge aus der Startstellung
SELECT m.move_san, p.fen_full
FROM moves m
JOIN positions src ON m.from_pos = src.id
JOIN positions p   ON m.to_pos   = p.id
WHERE src.depth_first = 0
ORDER BY m.move_san;

-- 4. Mattstellungen mit dem letzten Zug der dorthin führt
SELECT p.fen_full AS stellung, m.move_san AS letzter_zug
FROM positions p
JOIN moves m ON m.to_pos = p.id
WHERE p.is_checkmate = 1
LIMIT 20;

-- 5. Tiefste erreichbare Stellungen (Blätter des Graphen)
SELECT p.fen_full, p.depth_first, p.is_terminal
FROM positions p
WHERE p.id NOT IN (SELECT DISTINCT from_pos FROM moves)
ORDER BY p.depth_first DESC
LIMIT 10;

-- 6. Generierungsstatistik
SELECT
    max_depth,
    started_at,
    finished_at,
    positions_total,
    moves_total,
    terminal_nodes
FROM generation_stats
ORDER BY id DESC
LIMIT 1;
