import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EdgeType(str, enum.Enum):
    VOUCH = "vouch"
    COOL = "cool"
    BLOCK = "block"
    REPORT = "report"
    MEMBER = "member"
    PARTICIPANT = "participant"
    HOST = "host"
    RESPONDER = "responder"


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False
    )
    type: Mapped[EdgeType] = mapped_column(Enum(EdgeType, name="edge_type"), nullable=False)
    context_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    source_node: Mapped["Node"] = relationship(foreign_keys=[source_node_id], back_populates="edges_out")
    target_node: Mapped["Node"] = relationship(foreign_keys=[target_node_id], back_populates="edges_in")
    context_node: Mapped["Node | None"] = relationship(foreign_keys=[context_node_id])

    __table_args__ = (
        UniqueConstraint("source_node_id", "target_node_id", "type", "context_node_id", name="uq_edge"),
        Index("idx_edges_source", "source_node_id"),
        Index("idx_edges_target", "target_node_id"),
        Index("idx_edges_type", "type"),
        Index("idx_edges_context", "context_node_id", postgresql_where="context_node_id IS NOT NULL"),
    )
