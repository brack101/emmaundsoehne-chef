#!/usr/bin/env python3
"""
Schachspielbaum-Generator
=========================
Generiert alle möglichen Schachstellungen bis Tiefe N (Halbzüge)
und speichert sie als gerichteten Graphen in einer SQLite-Datenbank.

Wachstum (ca.):
  Tiefe 1  →         20 Stellungen
  Tiefe 2  →        400 Stellungen
  Tiefe 3  →      8.902 Stellungen
  Tiefe 4  →    197.281 Stellungen (De-Bruijn-Sequenz)
  Tiefe 5  →  4.865.609 Stellungen  (~500 MB DB)

Verwendung:
  pip install chess
  python generate_games.py --depth 4 --db chess_games.db
  python generate_games.py --depth 5 --db chess_games.db --batch 5000
"""

import argparse
import sqlite3
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

try:
    import chess
    import chess.pgn
except ImportError:
    print("Fehler: 'chess'-Paket fehlt. Installieren mit: pip install chess")
    sys.exit(1)


def fen_without_counters(board: chess.Board) -> str:
    """FEN ohne Halbzug- und Vollzugzähler für Deduplizierung.
    Zwei Stellungen mit gleichem Brett + Seite + Rochaderechte + En-passant
    gelten als identisch, egal wie viele Züge gespielt wurden.
    """
    parts = board.fen().split()
    return " ".join(parts[:4])  # Stellung, Seite, Rochade, En-passant


class ChessTreeGenerator:
    def __init__(self, db_path: str, max_depth: int, batch_size: int = 2000):
        self.db_path = db_path
        self.max_depth = max_depth
        self.batch_size = batch_size

        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=-64000")  # 64 MB Cache
        self._init_schema()

        # In-Memory-Cache: fen_key → position_id
        self.pos_cache: dict[str, int] = {}

        self.stats = {
            "positions": 0,
            "moves": 0,
            "terminal": 0,
            "skipped": 0,   # Bereits bekannte Stellungen (Transpositionstreffer)
        }

    def _init_schema(self):
        schema_path = Path(__file__).parent / "schema.sql"
        if schema_path.exists():
            self.conn.executescript(schema_path.read_text())
        else:
            # Fallback: Schema inline
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fen TEXT NOT NULL UNIQUE,
                    fen_full TEXT NOT NULL,
                    depth_first INTEGER NOT NULL,
                    is_checkmate INTEGER NOT NULL DEFAULT 0,
                    is_stalemate INTEGER NOT NULL DEFAULT 0,
                    is_terminal INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS moves (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_pos INTEGER NOT NULL REFERENCES positions(id),
                    to_pos INTEGER NOT NULL REFERENCES positions(id),
                    move_uci TEXT NOT NULL,
                    move_san TEXT NOT NULL,
                    UNIQUE(from_pos, move_uci)
                );
                CREATE TABLE IF NOT EXISTS generation_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    max_depth INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    positions_total INTEGER DEFAULT 0,
                    moves_total INTEGER DEFAULT 0,
                    terminal_nodes INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_positions_fen ON positions(fen);
                CREATE INDEX IF NOT EXISTS idx_moves_from ON moves(from_pos);
            """)
        self.conn.commit()

    def _get_or_create_position(
        self,
        board: chess.Board,
        depth: int,
        pos_batch: list,
    ) -> tuple[int, bool]:
        """Gibt (id, is_new) zurück. is_new=False → Transpositionstreffer."""
        fen_key = fen_without_counters(board)

        if fen_key in self.pos_cache:
            return self.pos_cache[fen_key], False

        # DB prüfen
        row = self.conn.execute(
            "SELECT id FROM positions WHERE fen = ?", (fen_key,)
        ).fetchone()
        if row:
            self.pos_cache[fen_key] = row[0]
            return row[0], False

        # Neue Stellung einfügen
        is_checkmate = int(board.is_checkmate())
        is_stalemate = int(board.is_stalemate())
        is_terminal = int(
            board.is_checkmate()
            or board.is_stalemate()
            or board.is_insufficient_material()
            or board.is_seventyfive_moves()
            or board.is_fivefold_repetition()
        )

        cur = self.conn.execute(
            """INSERT OR IGNORE INTO positions
               (fen, fen_full, depth_first, is_checkmate, is_stalemate, is_terminal)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (fen_key, board.fen(), depth, is_checkmate, is_stalemate, is_terminal),
        )
        if cur.lastrowid:
            pos_id = cur.lastrowid
        else:
            # Race condition (sollte bei single-thread nicht passieren)
            pos_id = self.conn.execute(
                "SELECT id FROM positions WHERE fen = ?", (fen_key,)
            ).fetchone()[0]

        self.pos_cache[fen_key] = pos_id
        self.stats["positions"] += 1
        return pos_id, True

    def generate(self):
        started_at = datetime.now(timezone.utc).isoformat()
        stat_id = self.conn.execute(
            "INSERT INTO generation_stats (max_depth, started_at) VALUES (?, ?)",
            (self.max_depth, started_at),
        ).lastrowid
        self.conn.commit()

        root_board = chess.Board()
        pos_batch: list = []
        move_batch: list[tuple] = []

        # BFS-Queue: (Board, depth, parent_pos_id, move_uci, move_san)
        # Startstellung hat keinen Elternteil
        root_id, _ = self._get_or_create_position(root_board, 0, pos_batch)
        self.conn.commit()

        queue: deque = deque()
        queue.append((root_board.copy(), 0, root_id))

        last_report = time.time()
        report_interval = 5  # Sekunden

        print(f"Starte Generierung bis Tiefe {self.max_depth}...")
        print(f"Datenbank: {self.db_path}")
        print()

        while queue:
            board, depth, parent_id = queue.popleft()

            if depth >= self.max_depth:
                continue
            if board.is_game_over():
                continue

            for move in board.legal_moves:
                san = board.san(move)
                board.push(move)

                child_id, is_new = self._get_or_create_position(
                    board, depth + 1, pos_batch
                )

                # Zug als Kante speichern
                move_batch.append((parent_id, child_id, move.uci(), san))
                self.stats["moves"] += 1

                if is_new:
                    if not board.is_game_over():
                        queue.append((board.copy(), depth + 1, child_id))
                else:
                    self.stats["skipped"] += 1

                board.pop()

            # Batch-Insert
            if len(move_batch) >= self.batch_size:
                self._flush(move_batch)
                move_batch.clear()

            # Fortschritt ausgeben
            now = time.time()
            if now - last_report >= report_interval:
                qsize = len(queue)
                print(
                    f"  Tiefe ≤{depth+1:2d} | "
                    f"Stellungen: {self.stats['positions']:>8,} | "
                    f"Züge: {self.stats['moves']:>9,} | "
                    f"Transpos.: {self.stats['skipped']:>7,} | "
                    f"Queue: {qsize:>7,}"
                )
                last_report = now

        # Rest flushen
        if move_batch:
            self._flush(move_batch)

        # Stats abschliessen
        finished_at = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """UPDATE generation_stats
               SET finished_at=?, positions_total=?, moves_total=?, terminal_nodes=?
               WHERE id=?""",
            (
                finished_at,
                self.stats["positions"],
                self.stats["moves"],
                self.stats["terminal"],
                stat_id,
            ),
        )
        self.conn.commit()
        self.conn.close()

        print()
        print("=" * 55)
        print(f"  Fertig!")
        print(f"  Stellungen gespeichert : {self.stats['positions']:>10,}")
        print(f"  Züge gespeichert       : {self.stats['moves']:>10,}")
        print(f"  Transpositionstreffer  : {self.stats['skipped']:>10,}")
        print(f"  Datenbank              : {self.db_path}")
        print("=" * 55)

    def _flush(self, move_batch: list[tuple]):
        self.conn.executemany(
            """INSERT OR IGNORE INTO moves (from_pos, to_pos, move_uci, move_san)
               VALUES (?, ?, ?, ?)""",
            move_batch,
        )
        self.conn.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Generiert alle Schachstellungen bis Tiefe N in einer SQLite-DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python generate_games.py --depth 4
  python generate_games.py --depth 5 --db meine_partie.db --batch 5000

Geschätzte Grössen (Halbzüge):
  --depth 3  →      8.902 Stellungen  (schnell, <1s)
  --depth 4  →    197.281 Stellungen  (~5s)
  --depth 5  →  4.865.609 Stellungen  (~2 Min, ~800 MB)
        """,
    )
    parser.add_argument(
        "--depth", type=int, default=4,
        help="Maximale Suchtiefe in Halbzügen (default: 4)",
    )
    parser.add_argument(
        "--db", type=str, default="chess_games.db",
        help="Pfad zur SQLite-Datenbank (default: chess_games.db)",
    )
    parser.add_argument(
        "--batch", type=int, default=2000,
        help="Batch-Grösse für DB-Inserts (default: 2000)",
    )
    args = parser.parse_args()

    if args.depth > 6:
        print(f"Warnung: Tiefe {args.depth} erzeugt >100 Mio. Stellungen.")
        print("Das kann Stunden dauern und >50 GB Speicher benötigen.")
        answer = input("Trotzdem fortfahren? [j/N] ").strip().lower()
        if answer != "j":
            print("Abgebrochen.")
            sys.exit(0)

    gen = ChessTreeGenerator(
        db_path=args.db,
        max_depth=args.depth,
        batch_size=args.batch,
    )
    gen.generate()


if __name__ == "__main__":
    main()
