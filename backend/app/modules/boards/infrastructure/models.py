from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Board(Base):
    __tablename__ = "boards"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    view_mode: Mapped[str] = mapped_column(String(32), default="map")


class BoardNode(Base):
    __tablename__ = "board_nodes"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    board_id: Mapped[UUID] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    object_type: Mapped[str] = mapped_column(String(48))
    object_id: Mapped[UUID] = mapped_column(index=True)
    x: Mapped[int] = mapped_column(default=0)
    y: Mapped[int] = mapped_column(default=0)
    width: Mapped[int] = mapped_column(default=200)
    height: Mapped[int] = mapped_column(default=100)


class BoardEdge(Base):
    __tablename__ = "board_edges"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    board_id: Mapped[UUID] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    source_node_id: Mapped[UUID] = mapped_column(
        ForeignKey("board_nodes.id", ondelete="CASCADE"), index=True
    )
    target_node_id: Mapped[UUID] = mapped_column(
        ForeignKey("board_nodes.id", ondelete="CASCADE"), index=True
    )
    edge_type: Mapped[str] = mapped_column(String(48), default="depends_on")
