from __future__ import annotations

from db.connection import get_connection, transaction


def get_preference(owner_id: str, key: str) -> str | None:
    """
    Get a persistent preference for a shop/owner.

    Preferences are keyed by owner_id, NOT Telegram chat_id.
    """

    if not owner_id or not owner_id.strip():
        raise ValueError("owner_id is required")

    if not key or not key.strip():
        raise ValueError("preference key is required")

    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT value
            FROM preferences
            WHERE owner_id = ?
              AND key = ?
            """,
            (
                owner_id.strip(),
                key.strip(),
            ),
        ).fetchone()

        if row is None:
            return None

        return row["value"]

    finally:
        conn.close()
def list_preferences(owner_id: str) -> list[dict]:
    """
    Return all persistent preferences for a shop/owner.

    Preferences are keyed by owner_id, NOT Telegram chat_id.
    """

    if not owner_id or not owner_id.strip():
        raise ValueError("owner_id is required")

    owner_id = owner_id.strip()

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                key,
                value,
                updated_at
            FROM preferences
            WHERE owner_id = ?
            ORDER BY key
            """,
            (owner_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def set_preference(
    owner_id: str,
    key: str,
    value: str,
) -> dict:
    """
    Create or update a persistent shop/owner preference.

    Uses (owner_id, key) as the unique identity.
    """

    if not owner_id or not owner_id.strip():
        raise ValueError("owner_id is required")

    if not key or not key.strip():
        raise ValueError("preference key is required")

    if value is None:
        raise ValueError("preference value is required")

    owner_id = owner_id.strip()
    key = key.strip()
    value = str(value)

    conn = get_connection()

    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO preferences
                    (owner_id, key, value, updated_at)
                VALUES
                    (?, ?, ?, datetime('now'))
                ON CONFLICT(owner_id, key)
                DO UPDATE SET
                    value = excluded.value,
                    updated_at = datetime('now')
                """,
                (
                    owner_id,
                    key,
                    value,
                ),
            )

            row = conn.execute(
                """
                SELECT
                    owner_id,
                    key,
                    value,
                    updated_at
                FROM preferences
                WHERE owner_id = ?
                  AND key = ?
                """,
                (
                    owner_id,
                    key,
                ),
            ).fetchone()

            return dict(row)

    finally:
        conn.close()