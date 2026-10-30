import sqlite3, json
from datetime import datetime, timezone
from .config import settings

def init_db():
    with sqlite3.connect(settings.database_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo TEXT NOT NULL, pr_number INTEGER NOT NULL, title TEXT,
            status TEXT NOT NULL, findings_json TEXT NOT NULL,
            summary TEXT, created_at TEXT NOT NULL
        )""")

def save_review(repo, number, title, status, findings, summary):
    with sqlite3.connect(settings.database_path) as con:
        con.execute(
            "INSERT INTO reviews(repo,pr_number,title,status,findings_json,summary,created_at) VALUES(?,?,?,?,?,?,?)",
            (repo, number, title, status, json.dumps(findings), summary,
             datetime.now(timezone.utc).isoformat())
        )

def recent_reviews(limit=30):
    with sqlite3.connect(settings.database_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
