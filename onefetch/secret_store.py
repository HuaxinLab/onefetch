from __future__ import annotations

import os
import secrets
import sqlite3
import subprocess
import time
from pathlib import Path

_DB_RELATIVE_PATH = ".onefetch/secrets.db"


class SecretStoreError(RuntimeError):
    pass


def get_secret(key: str) -> str | None:
    if not key.strip():
        return None
    conn = _connect()
    try:
        row = conn.execute("SELECT ciphertext FROM secrets WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        return _decrypt_text(row[0])
    finally:
        conn.close()


def set_secret(key: str, value: str, *, secret_type: str = "cookie") -> None:
    key = key.strip()
    value = value.strip()
    if not key:
        raise SecretStoreError("key is required")
    if not value:
        raise SecretStoreError("value is required")

    ciphertext = _encrypt_text(value)
    now = int(time.time())

    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO secrets(key, type, ciphertext, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              type = excluded.type,
              ciphertext = excluded.ciphertext,
              updated_at = excluded.updated_at
            """,
            (key, secret_type, ciphertext, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def delete_secret(key: str) -> int:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM secrets WHERE key = ?", (key,))
        conn.commit()
        return int(cur.rowcount or 0)
    finally:
        conn.close()


def list_secret_keys(*, secret_type: str | None = None) -> list[str]:
    conn = _connect()
    try:
        if secret_type:
            rows = conn.execute(
                "SELECT key FROM secrets WHERE type = ? ORDER BY key",
                (secret_type,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT key FROM secrets ORDER BY key").fetchall()
        return [str(row[0]) for row in rows]
    finally:
        conn.close()


def secret_exists(key: str) -> bool:
    conn = _connect()
    try:
        row = conn.execute("SELECT 1 FROM secrets WHERE key = ? LIMIT 1", (key,)).fetchone()
        return bool(row)
    finally:
        conn.close()


def move_secret_key(old_key: str, new_key: str) -> str:
    """Move old key to new key.

    Returns:
      - "moved": old existed and was moved to new
      - "dropped": old existed but new already existed, so old was removed
      - "missing": old did not exist
      - "noop": old == new
    """
    old_key = old_key.strip()
    new_key = new_key.strip()
    if not old_key or not new_key:
        raise SecretStoreError("both old_key and new_key are required")
    if old_key == new_key:
        return "noop"

    conn = _connect()
    try:
        old_row = conn.execute(
            "SELECT key, type, ciphertext, created_at, updated_at FROM secrets WHERE key = ?",
            (old_key,),
        ).fetchone()
        if not old_row:
            return "missing"

        new_row = conn.execute("SELECT 1 FROM secrets WHERE key = ? LIMIT 1", (new_key,)).fetchone()
        if new_row:
            conn.execute("DELETE FROM secrets WHERE key = ?", (old_key,))
            conn.commit()
            return "dropped"

        conn.execute(
            """
            INSERT INTO secrets(key, type, ciphertext, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (new_key, old_row[1], old_row[2], old_row[3], old_row[4]),
        )
        conn.execute("DELETE FROM secrets WHERE key = ?", (old_key,))
        conn.commit()
        return "moved"
    finally:
        conn.close()


def cookie_key(domain: str) -> str:
    normalized = (domain or "").strip().lower()
    if not normalized:
        raise SecretStoreError("domain is required")
    return f"cookie.{normalized}"


def _project_root() -> Path:
    return Path(os.getenv("ONEFETCH_PROJECT_ROOT", ".")).resolve()


def _db_path() -> Path:
    return _project_root() / _DB_RELATIVE_PATH


def _connect() -> sqlite3.Connection:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(db_path.parent, 0o700)
    except OSError:
        pass

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS secrets (
            key TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            ciphertext TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    try:
        os.chmod(db_path, 0o600)
    except OSError:
        pass
    return conn


def _master_key() -> str:
    return _load_or_create_master_key_file()


def _master_key_file_path() -> Path:
    override = os.getenv("ONEFETCH_MASTER_KEY_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (_project_root() / ".onefetch" / "master.key").resolve()


def _load_or_create_master_key_file() -> str:
    path = _master_key_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass

    if path.is_file():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value

    value = secrets.token_urlsafe(48)
    path.write_text(value + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return value


def _encrypt_text(plain: str) -> str:
    key = _master_key()
    proc = subprocess.run(
        [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-pbkdf2",
            "-salt",
            "-pass",
            f"pass:{key}",
            "-a",
            "-A",
        ],
        input=plain.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise SecretStoreError(f"encrypt failed: {proc.stderr.decode('utf-8', errors='ignore').strip()}")
    return proc.stdout.decode("utf-8").strip()


def _decrypt_text(ciphertext: str) -> str:
    key = _master_key()
    proc = subprocess.run(
        [
            "openssl",
            "enc",
            "-d",
            "-aes-256-cbc",
            "-pbkdf2",
            "-pass",
            f"pass:{key}",
            "-a",
            "-A",
        ],
        input=ciphertext.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise SecretStoreError(f"decrypt failed: {proc.stderr.decode('utf-8', errors='ignore').strip()}")
    return proc.stdout.decode("utf-8").strip()
