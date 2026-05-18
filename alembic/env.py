"""Alembic migration environment for Orkio API.

PATCH AO-01:
- Restores a valid Alembic env.py after the file was overwritten by migration content.
- Uses DATABASE_PUBLIC_URL / DATABASE_URL_PUBLIC / DATABASE_URL from runtime env.
- Registers app.models so Base.metadata contains all ORM tables.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db import Base
from app import models  # noqa: F401 - import registers ORM models on Base.metadata


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def _runtime_database_url() -> str:
    url = (
        os.getenv("DATABASE_PUBLIC_URL", "").strip().strip('"').strip("'")
        or os.getenv("DATABASE_URL_PUBLIC", "").strip().strip('"').strip("'")
        or os.getenv("DATABASE_URL", "").strip().strip('"').strip("'")
    )
    url = url.replace("Postgres.railway.internal", "postgres.railway.internal")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    url = _runtime_database_url() or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    runtime_url = _runtime_database_url()
    section = config.get_section(config.config_ini_section, {})
    if runtime_url:
        section = dict(section)
        section["sqlalchemy.url"] = runtime_url

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        pool_pre_ping=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
