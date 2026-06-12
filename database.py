import datetime
import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# Postgres in production (DATABASE_URL), SQLite locally.
# Railway-era fallback: volume mounted at /data via DATA_DIR.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    # SQLAlchemy needs postgresql://, some providers hand out postgres://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    DATA_DIR = os.getenv("DATA_DIR", ".")
    DATABASE_URL = f"sqlite:///{DATA_DIR}/greeksrt.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id           = Column(Integer, primary_key=True, index=True)
    email        = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at   = Column(DateTime, default=datetime.datetime.utcnow)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
