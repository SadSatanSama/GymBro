import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base

# Get database URL from environment
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gym_tracker.db")

# Fix for Heroku/Render PostgreSQL URLs (replace postgres:// with postgresql://)
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs 'check_same_thread', PostgreSQL does not
if "sqlite" in SQLALCHEMY_DATABASE_URL:
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    # Create all new tables (users, etc.)
    Base.metadata.create_all(bind=engine)

    # Safe migration: add user_id column to workouts if it doesn't exist.
    # This handles existing databases that pre-date the multi-user upgrade.
    with engine.connect() as conn:
        try:
            if "sqlite" in SQLALCHEMY_DATABASE_URL:
                # SQLite doesn't support ADD COLUMN IF NOT EXISTS
                result = conn.execute(text("PRAGMA table_info(workouts)"))
                cols = [row[1] for row in result]
                if "user_id" not in cols:
                    conn.execute(text(
                        "ALTER TABLE workouts ADD COLUMN user_id INTEGER REFERENCES users(id)"
                    ))
                    conn.commit()
            else:
                # PostgreSQL supports ADD COLUMN IF NOT EXISTS
                conn.execute(text(
                    "ALTER TABLE workouts ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"
                ))
                conn.commit()
        except Exception as e:
            print(f"Migration note (safe to ignore if column exists): {e}")
