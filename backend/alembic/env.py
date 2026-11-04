from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import Settings
from app.database import Base
from app import models  # noqa: F401: register metadata

config = context.config
url = config.attributes.get("database_url") or Settings().database_url


def run():
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            if engine.dialect.name == "sqlite":
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
            context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True, render_as_batch=engine.dialect.name == "sqlite")
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()


run()
