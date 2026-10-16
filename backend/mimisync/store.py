import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone


class Store:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS media (id TEXT PRIMARY KEY, payload TEXT NOT NULL);"
        )
        for job in self.list("jobs"):
            if job["status"] in ("queued", "running"):
                self.update(
                    job["id"],
                    status="interrupted",
                    stage="Interrompido pela reinicialização; crie um novo trabalho",
                )

    def list(self, table):
        assert table in ("jobs", "media")
        with self.lock:
            return [
                json.loads(row[0])
                for row in self.db.execute(
                    f"SELECT payload FROM {table} ORDER BY rowid DESC"
                )
            ]

    def get(self, table, id):
        assert table in ("jobs", "media")
        with self.lock:
            row = self.db.execute(
                f"SELECT payload FROM {table} WHERE id=?", (id,)
            ).fetchone()
            if not row:
                raise KeyError(id)
            return json.loads(row[0])

    def put(self, table, data):
        assert table in ("jobs", "media")
        with self.lock, self.db:
            self.db.execute(
                f"INSERT OR REPLACE INTO {table} VALUES (?,?)",
                (data["id"], json.dumps(data)),
            )
        return data

    def create(self, kind, **kwargs):
        return self.put(
            "jobs",
            {
                "id": uuid.uuid4().hex,
                "kind": kind,
                "status": "queued",
                "stage": "Na fila",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "progress": None,
                **kwargs,
            },
        )

    def update(self, id, **kwargs):
        with self.lock:
            return self.put("jobs", {**self.get("jobs", id), **kwargs})
