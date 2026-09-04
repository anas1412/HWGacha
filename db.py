"""SQLite storage: cards, ownership, cooldowns. Ownership is per Discord server."""
import sqlite3
import time
from datetime import datetime, timedelta

from config import DB_PATH, RARITIES

_conn = sqlite3.connect(DB_PATH)
_conn.row_factory = sqlite3.Row


def init():
    _conn.executescript("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY,
            file TEXT UNIQUE NOT NULL,
            name TEXT UNIQUE NOT NULL,
            rarity TEXT NOT NULL,
            description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS claims (
            guild_id INTEGER NOT NULL,
            card_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            claimed_at REAL NOT NULL,
            PRIMARY KEY (guild_id, card_id)
        );
        CREATE TABLE IF NOT EXISTS rolls (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rolled_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS last_claim (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            claimed_at REAL NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        );
    """)
    _conn.commit()


# ---------- cards ----------

def add_card(file, name, rarity, description):
    cur = _conn.execute(
        "INSERT INTO cards (file, name, rarity, description) VALUES (?, ?, ?, ?)",
        (file, name, rarity, description),
    )
    _conn.commit()
    return cur.lastrowid


def known_files():
    return {r["file"] for r in _conn.execute("SELECT file FROM cards")}


def all_names():
    return [r["name"] for r in _conn.execute("SELECT name FROM cards")]


def cards_in_rarity(rarity, unclaimed_in=None):
    """All cards of a rarity; with unclaimed_in=guild_id, only those nobody in that server owns."""
    if unclaimed_in is None:
        return _conn.execute("SELECT * FROM cards WHERE rarity = ?", (rarity,)).fetchall()
    return _conn.execute(
        """SELECT c.* FROM cards c LEFT JOIN claims k ON k.card_id = c.id AND k.guild_id = ?
           WHERE c.rarity = ? AND k.card_id IS NULL""",
        (unclaimed_in, rarity),
    ).fetchall()


def get_card(card_id):
    return _conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()


def find_card(query):
    """Exact name first, then substring match."""
    row = _conn.execute("SELECT * FROM cards WHERE name = ?", (query,)).fetchone()
    if row:
        return row
    return _conn.execute(
        "SELECT * FROM cards WHERE name LIKE ? ORDER BY name LIMIT 1", (f"%{query}%",)
    ).fetchone()


def pool_counts(unclaimed_in=None):
    """Cards per rarity; with unclaimed_in=guild_id, only those nobody in that server owns."""
    if unclaimed_in is None:
        rows = _conn.execute("SELECT rarity, COUNT(*) AS n FROM cards GROUP BY rarity")
    else:
        rows = _conn.execute(
            """SELECT c.rarity, COUNT(*) AS n FROM cards c
               LEFT JOIN claims k ON k.card_id = c.id AND k.guild_id = ?
               WHERE k.card_id IS NULL GROUP BY c.rarity""",
            (unclaimed_in,),
        )
    return {r["rarity"]: r["n"] for r in rows}


# ---------- ownership ----------

def owner_of(guild_id, card_id):
    row = _conn.execute(
        "SELECT user_id FROM claims WHERE guild_id = ? AND card_id = ?", (guild_id, card_id)
    ).fetchone()
    return row["user_id"] if row else None


def claim(guild_id, card_id, user_id):
    """Returns True if the claim succeeded, False if someone got there first."""
    try:
        _conn.execute(
            "INSERT INTO claims (guild_id, card_id, user_id, claimed_at) VALUES (?, ?, ?, ?)",
            (guild_id, card_id, user_id, time.time()),
        )
    except sqlite3.IntegrityError:
        return False
    _conn.execute(
        "INSERT OR REPLACE INTO last_claim (guild_id, user_id, claimed_at) VALUES (?, ?, ?)",
        (guild_id, user_id, time.time()),
    )
    _conn.commit()
    return True


def release(guild_id, card_id, user_id):
    cur = _conn.execute(
        "DELETE FROM claims WHERE guild_id = ? AND card_id = ? AND user_id = ?",
        (guild_id, card_id, user_id),
    )
    _conn.commit()
    return cur.rowcount == 1


def transfer(guild_id, card_id, from_user, to_user):
    cur = _conn.execute(
        "UPDATE claims SET user_id = ? WHERE guild_id = ? AND card_id = ? AND user_id = ?",
        (to_user, guild_id, card_id, from_user),
    )
    _conn.commit()
    return cur.rowcount == 1


def swap(guild_id, card_a, user_a, card_b, user_b):
    """Atomically trade card_a (owned by user_a) for card_b (owned by user_b)."""
    with _conn:
        a = _conn.execute(
            "UPDATE claims SET user_id = ? WHERE guild_id = ? AND card_id = ? AND user_id = ?",
            (user_b, guild_id, card_a, user_a),
        ).rowcount
        b = _conn.execute(
            "UPDATE claims SET user_id = ? WHERE guild_id = ? AND card_id = ? AND user_id = ?",
            (user_a, guild_id, card_b, user_b),
        ).rowcount
        if a != 1 or b != 1:
            raise sqlite3.IntegrityError("ownership changed")
    return True


def collection(guild_id, user_id):
    return _conn.execute(
        """SELECT c.* FROM cards c JOIN claims k ON k.card_id = c.id
           WHERE k.guild_id = ? AND k.user_id = ? ORDER BY c.name""",
        (guild_id, user_id),
    ).fetchall()


def leaderboard(guild_id, limit=10):
    rows = _conn.execute(
        """SELECT k.user_id, c.rarity, COUNT(*) AS n FROM claims k JOIN cards c ON c.id = k.card_id
           WHERE k.guild_id = ? GROUP BY k.user_id, c.rarity""",
        (guild_id,),
    )
    totals = {}
    for r in rows:
        pts, cnt = totals.get(r["user_id"], (0, 0))
        totals[r["user_id"]] = (pts + RARITIES[r["rarity"]]["points"] * r["n"], cnt + r["n"])
    ranked = sorted(totals.items(), key=lambda kv: kv[1][0], reverse=True)
    return ranked[:limit]


# ---------- daily limits (reset at local midnight) ----------

def day_start():
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def seconds_until_midnight():
    return day_start() + 86400 - time.time()


def rolls_today(guild_id, user_id):
    row = _conn.execute(
        "SELECT COUNT(*) AS n FROM rolls WHERE guild_id = ? AND user_id = ? AND rolled_at >= ?",
        (guild_id, user_id, day_start()),
    ).fetchone()
    return row["n"]


def record_roll(guild_id, user_id):
    _conn.execute(
        "INSERT INTO rolls (guild_id, user_id, rolled_at) VALUES (?, ?, ?)",
        (guild_id, user_id, time.time()),
    )
    _conn.execute("DELETE FROM rolls WHERE rolled_at < ?", (day_start(),))
    _conn.commit()


def claimed_today(guild_id, user_id):
    row = _conn.execute(
        "SELECT claimed_at FROM last_claim WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
    ).fetchone()
    return bool(row) and row["claimed_at"] >= day_start()
