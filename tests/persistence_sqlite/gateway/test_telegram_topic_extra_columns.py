"""Regression: topic-binding reads tolerate columns ``TopicBinding`` does not declare.

A ``telegram_dm_topic_bindings`` table left by an older build can carry extra columns
(e.g. ``last_user_inbound_at``) that the migration keeps. ``SELECT *`` fed into the
strict dataclass raised ``TypeError``, which the auto-rename path swallowed at debug.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from persistence import ProfileScope
from persistence.sqlite import SQLiteBackend
from tests.fixtures.storage_seed import seed_session

CHAT = "208214988"
KEY = f"agent:main:telegram:dm:{CHAT}"


def _seed_binding_with_extra_column(db_path: Path) -> None:
    scope = ProfileScope(profile_dir=db_path.parent, name="default")
    backend = SQLiteBackend({scope.hermes_home_key: db_path})
    try:
        store = backend.open(scope)
        seed_session(store, "sess-1", "telegram", session_key=KEY, chat_id=CHAT, chat_type="dm")
        store.routing.enable_topic_mode(chat_id=CHAT, user_id=CHAT)
        assert store.routing.bind_topic(chat_id=CHAT, thread_id="99", user_id=CHAT,
                                        session_key=KEY, session_id="sess-1")
    finally:
        backend.close()
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("ALTER TABLE telegram_dm_topic_bindings ADD COLUMN last_user_inbound_at REAL")
        conn.execute("UPDATE telegram_dm_topic_bindings SET last_user_inbound_at = 5.0")
        conn.commit()


def test_topic_binding_reads_ignore_undeclared_columns(tmp_path: Path):
    db_path = tmp_path / "state.db"
    _seed_binding_with_extra_column(db_path)
    scope = ProfileScope(profile_dir=db_path.parent, name="default")
    backend = SQLiteBackend({scope.hermes_home_key: db_path})
    try:
        routing = backend.open(scope).routing

        binding = routing.get_topic_binding(chat_id=CHAT, thread_id="99")
        assert binding is not None
        assert binding.session_id == "sess-1"
        assert [b.thread_id for b in routing.list_topic_bindings_for_chat(chat_id=CHAT)] == ["99"]
        by_session = routing.get_topic_binding_for_session(session_id="sess-1")
        assert by_session is not None
        assert by_session.thread_id == "99"
    finally:
        backend.close()
