# Schachspielbaum-Generator

Speichert alle möglichen Schachstellungen bis Tiefe N als **gerichteten Graphen** in SQLite.

## Warum ein Graph, keine Liste von Partien?

Schach hat Transpositionen — dieselbe Stellung ist über verschiedene Zugfolgen erreichbar.
Ein Graph mit **Deduplizierung via FEN** ist ~10× kompakter als eine rohe Partien-Liste.

## Installation

```bash
pip install chess
```

## Verwendung

```bash
# Alle Stellungen bis Tiefe 4 (Halbzüge) generieren
python generate_games.py --depth 4

# Tiefe 5 in eigene DB
python generate_games.py --depth 5 --db meine.db

# Hilfe
python generate_games.py --help
```

## Datenbankstruktur

```
positions
├── id            INTEGER  PK
├── fen           TEXT     UNIQUE  ← FEN ohne Zähler (Deduplizierungs-Key)
├── fen_full      TEXT             ← Vollständiges FEN
├── depth_first   INTEGER          ← Tiefe der ersten Erreichung
├── is_checkmate  INTEGER
├── is_stalemate  INTEGER
└── is_terminal   INTEGER

moves
├── id          INTEGER  PK
├── from_pos    INTEGER  → positions.id
├── to_pos      INTEGER  → positions.id
├── move_uci    TEXT     ← z.B. "e2e4", "e7e8q"
└── move_san    TEXT     ← z.B. "e4", "Qxf7#"
```

## Geschätzte Grössen

| Tiefe (Halbzüge) | Stellungen | Züge      | DB-Grösse | Dauer  |
|:----------------:|:----------:|:---------:|:---------:|:------:|
| 3                |      8.902 |    80.000 | < 5 MB    | < 1s   |
| 4                |    197.281 | 2.000.000 | ~ 80 MB   | ~5s    |
| 5                |  4.865.609 | ~50 Mio.  | ~ 800 MB  | ~2 Min |
| 6                | ~120 Mio.  | ~1 Mrd.   | ~ 20 GB   | Stunden|

## Beispielabfragen

```bash
sqlite3 chess_games.db < queries.sql
```

```sql
-- Alle Züge aus der Startstellung
SELECT move_san FROM moves m
JOIN positions p ON m.from_pos = p.id
WHERE p.depth_first = 0;

-- Mattstellungen
SELECT fen_full FROM positions WHERE is_checkmate = 1;
```
