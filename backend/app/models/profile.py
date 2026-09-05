import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AttributeDirection(str, enum.Enum):
    INPUT = "input"
    OUTPUT = "output"


class MembraneEntry(Base):
    __tablename__ = "membrane_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("nodes.id"))
    direction: Mapped[AttributeDirection] = mapped_column(
        Enum(AttributeDirection, values_callable=lambda members: [member.value for member in members], name="attribute_direction"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    node: Mapped["Node"] = relationship(back_populates="membrane_entries")

    __table_args__ = (
        Index("idx_membrane_node", "node_id"),
    )
