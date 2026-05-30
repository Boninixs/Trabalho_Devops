""""
Esse arquivo é responsável por definir o modelo de dados para as sugestões de match.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, UUIDPrimaryKeyMixin, TimestampMixin


class MatchStatus(str, enum.Enum):
    """"
    Enum para representar o status das sugestões de match.
    """
    SUGGESTED = "SUGGESTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class MatchSuggestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """"
    Modelo de dados para as sugestões de match, que representam as possíveis correspondências entre itens perdidos
    e encontrados no serviço de matching.   
    """
    __tablename__ = "match_suggestions"
    __table_args__ = (
        UniqueConstraint(
            "lost_item_id",
            "found_item_id",
            name="uq_match_suggestions_lost_found_pair",
        ),
    )

    lost_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    found_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    criteria_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status", native_enum=False),
        nullable=False,
        default=MatchStatus.SUGGESTED,
        index=True,
    )
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
