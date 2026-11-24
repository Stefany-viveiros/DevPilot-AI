from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="registered")
    analysis_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
