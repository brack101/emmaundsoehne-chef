-- Schachspielbaum-Datenbank
-- Speichert alle möglichen Stellungen und Züge bis Tiefe N als gerichteten Graph.
-- Gleiche Stellungen (via verschiedene Zugfolgen) werden dedupliziert → DAG.

-- Jede einzigartige Stellung (Position auf dem Brett)
CREATE TABLE IF NOT EXISTS positions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fen         TEXT    NOT NULL UNIQUE,   -- FEN ohne Zugnummer (Deduplizierung)
    fen_full    TEXT    NOT NULL,          -- Vollständiges FEN (erste Erreichung)
    depth_first INTEGER NOT NULL,         -- Tiefe, bei der diese Stellung erstmals gesehen wurde
    is_checkmate INTEGER NOT NULL DEFAULT 0,
    is_stalemate INTEGER NOT NULL DEFAULT 0,
    is_terminal  INTEGER NOT NULL DEFAULT 0  -- Checkmate, Stalemate oder 50-Züge-Regel etc.
);

-- Jeder Zug zwischen zwei Stellungen (Kanten des Graphen)
CREATE TABLE IF NOT EXISTS moves (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_pos    INTEGER NOT NULL REFERENCES positions(id),
    to_pos      INTEGER NOT NULL REFERENCES positions(id),
    move_uci    TEXT    NOT NULL,   -- Zug in UCI-Notation (z.B. "e2e4", "e7e8q")
    move_san    TEXT    NOT NULL,   -- Zug in SAN-Notation (z.B. "e4", "Qxf7#")
    UNIQUE(from_pos, move_uci)      -- Kein doppelter Zug von derselben Stellung
);

-- Statistik-Tabelle für den Generierungslauf
CREATE TABLE IF NOT EXISTS generation_stats (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    max_depth     INTEGER NOT NULL,
    started_at    TEXT    NOT NULL,
    finished_at   TEXT,
    positions_total INTEGER DEFAULT 0,
    moves_total     INTEGER DEFAULT 0,
    terminal_nodes  INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_positions_fen   ON positions(fen);
CREATE INDEX IF NOT EXISTS idx_moves_from      ON moves(from_pos);
CREATE INDEX IF NOT EXISTS idx_moves_to        ON moves(to_pos);
CREATE INDEX IF NOT EXISTS idx_positions_depth ON positions(depth_first);
