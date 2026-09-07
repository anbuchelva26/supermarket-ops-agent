import os
import sqlite3

import pytest


@pytest.fixture(autouse=True)
def test_database(tmp_path, monkeypatch):
    """
    Create an isolated SQLite database for every test and
    initialize it using the application's schema.sql.
    """

    db_path = tmp_path / "test_kirana.db"

    # Make application code use this temporary database.
    monkeypatch.setenv("KIRANA_DB_PATH", str(db_path))

    # Locate the project's schema.sql.
    project_root = os.path.dirname(os.path.dirname(__file__))
    schema_path = os.path.join(
        project_root,
        "db",
        "schema.sql",
    )

    # Create and initialize the test database.
    with sqlite3.connect(db_path) as conn:
        with open(schema_path, "r", encoding="utf-8") as schema_file:
            conn.executescript(schema_file.read())

    yield