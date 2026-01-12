from typing import List, Optional
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker, relationship
import os
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL env variable not set")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Models
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    api_keys: Mapped[List["APIKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    usage_logs: Mapped[List["UsageLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email}, name={self.name})"


class APIKey(Base):
    __tablename__ = "api_keys"

    key: Mapped[str] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="api_keys")
    usage_logs: Mapped[List["UsageLog"]] = relationship(
        back_populates="api_key_obj", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"APIKey(key={self.key[:8]}..., user_id={self.user_id}, name={self.name})"
        )


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    api_key_str: Mapped[str] = mapped_column(ForeignKey("api_keys.key"), index=True)
    endpoint: Mapped[str]
    method: Mapped[str]
    status_code: Mapped[int]
    timestamp: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="usage_logs")
    api_key_obj: Mapped["APIKey"] = relationship(back_populates="usage_logs")

    def __repr__(self) -> str:
        return f"UsageLog(user_id={self.user_id}, endpoint={self.endpoint}, status={self.status_code})"


# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
Base.metadata.create_all(bind=engine)
