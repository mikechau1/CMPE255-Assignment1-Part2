from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH, METRIC_DIR


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.lock = threading.Lock()
        self.init()

    def conn(self):
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self):
        with self.conn() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, name TEXT, status TEXT, phase TEXT, config TEXT, summary TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS trials (id TEXT PRIMARY KEY, experiment_id TEXT, parent_id TEXT, status TEXT, config TEXT, metrics TEXT, created_at TEXT, finished_at TEXT);
            """)

    def create_experiment(self, name, config, phase="Modeling"):
        ident = str(uuid.uuid4())
        stamp = now()
        with self.conn() as db:
            db.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (ident, name, "queued", phase, json.dumps(config), "{}", stamp, stamp))
        return ident

    def update_experiment(self, ident, **values):
        values["updated_at"] = now()
        sets = ", ".join(f"{key} = ?" for key in values)
        with self.conn() as db:
            db.execute(f"UPDATE experiments SET {sets} WHERE id = ?", (*values.values(), ident))

    def get_experiment(self, ident):
        with self.conn() as db:
            row = db.execute("SELECT * FROM experiments WHERE id = ?", (ident,)).fetchone()
        return dict(row) if row else None

    def list_experiments(self):
        with self.conn() as db:
            return [dict(row) for row in db.execute("SELECT * FROM experiments ORDER BY created_at DESC")]

    def create_trial(self, experiment_id, config, parent_id=None):
        ident = str(uuid.uuid4())
        with self.conn() as db:
            db.execute("INSERT INTO trials VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (ident, experiment_id, parent_id, "running", json.dumps(config), "{}", now(), None))
        return ident

    def finish_trial(self, ident, status, metrics):
        with self.conn() as db:
            db.execute("UPDATE trials SET status = ?, metrics = ?, finished_at = ? WHERE id = ?", (status, json.dumps(metrics), now(), ident))

    def list_trials(self, experiment_id=None):
        query = "SELECT * FROM trials"
        params = ()
        if experiment_id:
            query += " WHERE experiment_id = ?"
            params = (experiment_id,)
        query += " ORDER BY created_at DESC"
        with self.conn() as db:
            return [dict(row) for row in db.execute(query, params)]

    def append_metric(self, experiment_id, metric):
        METRIC_DIR.mkdir(parents=True, exist_ok=True)
        with self.lock:
            with (METRIC_DIR / f"{experiment_id}.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(metric) + "\n")

    def metrics(self, experiment_id):
        path = METRIC_DIR / f"{experiment_id}.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
