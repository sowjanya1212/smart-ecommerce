import warnings

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

# SQLite has no native Decimal type; the warning is harmless for dev.
warnings.filterwarnings("ignore", message="Dialect sqlite\\+pysqlite does \\*not\\* support Decimal")

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False, "timeout": 15} if _is_sqlite else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
