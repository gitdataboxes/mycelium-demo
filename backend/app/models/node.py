import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NodeType(str, enum.Enum):
    USER = "user"
    ORGANIZATION = "organization"
    EVENT = "event"


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    community_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communities.id"), nullable=False
    )
    type: Mapped[NodeType] = mapped_column(Enum(NodeType, values_callable=lambda members: [member.value for member in members], name="node_type"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    community: Mapped["Community"] = relationship(back_populates="nodes")
    membrane_entries: Mapped[list["MembraneEntry"]] = relationship(back_populates="node")
    signals: Mapped[list["Signal"]] = relationship(back_populates="node")
    edges_out: Mapped[list["Edge"]] = relationship(
        foreign_keys="Edge.source_node_id", back_populates="source_node"
    )
    edges_in: Mapped[list["Edge"]] = relationship(
        foreign_keys="Edge.target_node_id", back_populates="target_node"
    )

    __table_args__ = (
        Index("idx_nodes_community", "community_id"),
        Index("idx_nodes_type", "community_id", "type"),
    )
