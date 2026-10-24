import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def init_db(retries: int = 20, delay: float = 3.0) -> None:
    """Create tables, retrying so the service survives starting before PostgreSQL is ready."""
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            print("Connected to database")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"Database connection attempt {attempt} failed: {exc}")
            time.sleep(delay)
    raise RuntimeError("Could not connect to database")


def db_is_up() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
