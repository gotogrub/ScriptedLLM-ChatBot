from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import sqlite3


class ChatStorage:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        with self.connect() as connection:
            connection.execute(
                """
                create table if not exists sessions (
                    user_id text primary key,
                    state text not null,
                    request_type text,
                    draft_json text not null,
                    metadata_json text not null default '{}',
                    updated_at text not null
                )
                """
            )
            self.ensure_session_columns(connection)
            connection.execute(
                """
                create table if not exists messages (
                    id integer primary key autoincrement,
                    user_id text not null,
                    role text not null,
                    content text not null,
                    created_at text not null
                )
                """
            )
            connection.execute(
                """
                create table if not exists tickets (
                    id text primary key,
                    user_id text not null,
                    type text not null,
                    status text not null,
                    payload_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )

    def load_session(self, user_id):
        with self.connect() as connection:
            row = connection.execute("select * from sessions where user_id = ?", (user_id,)).fetchone()
        if not row:
            return {"user_id": user_id, "state": "idle", "request_type": None, "draft": {}}
        return {
            "user_id": user_id,
            "state": row["state"],
            "request_type": row["request_type"],
            "draft": json.loads(row["draft_json"]),
            **json.loads(row["metadata_json"] or "{}"),
        }

    def save_session(self, session):
        now = utc_now()
        metadata = {
            "field_attempts": session.get("field_attempts", {}),
            "last_missing_field": session.get("last_missing_field"),
        }
        with self.connect() as connection:
            connection.execute(
                """
                insert into sessions (user_id, state, request_type, draft_json, metadata_json, updated_at)
                values (?, ?, ?, ?, ?, ?)
                on conflict(user_id) do update set
                    state = excluded.state,
                    request_type = excluded.request_type,
                    draft_json = excluded.draft_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    session["user_id"],
                    session["state"],
                    session.get("request_type"),
                    json.dumps(session.get("draft", {}), ensure_ascii=False),
                    json.dumps(metadata, ensure_ascii=False),
                    now,
                ),
            )

    def ensure_session_columns(self, connection):
        rows = connection.execute("pragma table_info(sessions)").fetchall()
        columns = {row[1] for row in rows}
        if "metadata_json" not in columns:
            connection.execute("alter table sessions add column metadata_json text not null default '{}'")

    def reset_session(self, user_id):
        with self.connect() as connection:
            connection.execute("delete from sessions where user_id = ?", (user_id,))

    def add_message(self, user_id, role, content):
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "insert into messages (user_id, role, content, created_at) values (?, ?, ?, ?)",
                (user_id, role, content, now),
            )

    def recent_messages(self, user_id, limit=20):
        with self.connect() as connection:
            rows = connection.execute(
                "select role, content, created_at from messages where user_id = ? order by id desc limit ?",
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def create_ticket(self, ticket):
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                insert into tickets (id, user_id, type, status, payload_json, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket["id"],
                    ticket["user_id"],
                    ticket["type"],
                    ticket["status"],
                    json.dumps(ticket, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return ticket

    def list_tickets(self, user_id):
        with self.connect() as connection:
            rows = connection.execute(
                "select payload_json from tickets where user_id = ? order by created_at desc",
                (user_id,),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def update_ticket_status(self, ticket_id, status, resolution=None):
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                "select payload_json from tickets where id = ?",
                (ticket_id,),
            ).fetchone()
            if not row:
                return None
            ticket: dict[str, Any] = json.loads(row["payload_json"])
            ticket["status"] = status
            ticket["updated_at"] = now
            if resolution:
                ticket["resolution"] = resolution
            connection.execute(
                "update tickets set status = ?, payload_json = ?, updated_at = ? where id = ?",
                (status, json.dumps(ticket, ensure_ascii=False), now, ticket_id),
            )
        return ticket


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
