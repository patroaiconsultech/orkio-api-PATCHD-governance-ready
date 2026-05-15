from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text


def _clean_env_value(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().strip('"').strip("'")


def _database_url() -> str:
    url = (
        _clean_env_value(os.getenv("DATABASE_PUBLIC_URL"))
        or _clean_env_value(os.getenv("DATABASE_URL_PUBLIC"))
        or _clean_env_value(os.getenv("DATABASE_URL"))
    )

    if not url:
        raise RuntimeError(
            "DATABASE URL not found. Set DATABASE_PUBLIC_URL, "
            "DATABASE_URL_PUBLIC, or DATABASE_URL."
        )

    url = url.replace("Postgres.railway.internal", "postgres.railway.internal")

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    return url


def main() -> int:
    url = _database_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(128) NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE alembic_version
                ALTER COLUMN version_num TYPE VARCHAR(128)
                """
            )
        )

    print("ALEMBIC_VERSION_PREFLIGHT_OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ALEMBIC_VERSION_PREFLIGHT_FAILED: {exc}", file=sys.stderr)
        raise
