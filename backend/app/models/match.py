import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MatchHistory(Base):
    __tablename__ = "match_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("nodes.id"))
    node_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("nodes.id"))
    attribute_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attribute_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attribute_a_type: Mapped[str] = mapped_column(String(20), nullable=False)
    attribute_b_type: Mapped[str] = mapped_column(String(20), nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    digest_sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    node_a: Mapped["Node"] = relationship(foreign_keys=[node_a_id])
    node_b: Mapped["Node"] = relationship(foreign_keys=[node_b_id])

    __table_args__ = (
        Index("idx_match_history_nodes", "node_a_id", "node_b_id"),
    )
