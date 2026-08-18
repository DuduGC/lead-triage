from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection, create_engine

from alembic import context
from app.config import Settings
from app.persistence.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    settings = Settings()
    context.configure(
        url=settings.database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings = Settings()
    connectable = create_engine(
        settings.database_url.get_secret_value(),
        poolclass=pool.NullPool,
        pool_pre_ping=True,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
