from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def make_database(url: str):
    engine = create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread": False, "timeout": 15} if url.startswith("sqlite") else {})
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def sqlite_constraints(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=15000")
    return engine, sessionmaker(engine, expire_on_commit=False)
