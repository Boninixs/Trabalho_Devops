"""
Esse arquivo é responsável por definir as funções de acesso ao banco de dados para o modelo MatchSuggestion.
"""
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.models.match_suggestion import MatchStatus, MatchSuggestion


def add_match_suggestion(session: Session, suggestion: MatchSuggestion) -> MatchSuggestion:
    """
    Função para adicionar uma nova sugestão de match ao banco de dados.
    args:
        session: Sessão do SQLAlchemy para acessar o banco de dados
        suggestion: A sugestão de match a ser adicionada
    returns:
        MatchSuggestion: A sugestão de match que foi adicionada ao banco de dados.
    """
    session.add(suggestion)
    return suggestion


def get_match_suggestion_by_id(session: Session, match_id: UUID) -> MatchSuggestion | None:
    """
    Função para obter uma sugestão de match pelo seu ID.
    args:
        session: Sessão do SQLAlchemy para acessar o banco de dados
        match_id: ID da sugestão de match a ser buscada
    returns:
        MatchSuggestion | None: A sugestão de match correspondente ao ID fornecido, ou None se não tiver  
    """
    return session.get(MatchSuggestion, match_id)


def get_match_suggestion_by_pair(
    session: Session,
    *,
    lost_item_id: UUID,
    found_item_id: UUID,
) -> MatchSuggestion | None:
    """
    Função para obter uma sugestão de match com base na combinação de IDs de item perdido e encontrado.
    args:       
        session: Sessão do SQLAlchemy para acessar o banco de dados
        lost_item_id: ID do item perdido
        found_item_id: ID do item encontrado
    returns:
        MatchSuggestion | None: A sugestão de match correspondente à combinação de IDs fornecida, ou None se não tiver.
    """
    statement = (
        select(MatchSuggestion)
        .where(MatchSuggestion.lost_item_id == lost_item_id)
        .where(MatchSuggestion.found_item_id == found_item_id)
    )
    return session.scalar(statement)


def list_match_suggestions(
    session: Session,
    *,
    status: MatchStatus | None = None,
) -> list[MatchSuggestion]:
    """
    Função para listar as sugestões de match, com opção de filtrar por status.
    args:
        session: Sessão do SQLAlchemy para acessar o banco de dados
        status: Status das sugestões de match a serem listadas (opcional)
    returns:
        list[MatchSuggestion]: Uma lista de sugestões de match correspondentes aos critérios fornecidos.
    """
    statement: Select[tuple[MatchSuggestion]] = select(MatchSuggestion)
    if status is not None:
        statement = statement.where(MatchSuggestion.status == status)

    statement = statement.order_by(MatchSuggestion.created_at.desc())
    return list(session.scalars(statement))


def list_suggested_matches_for_item(
    session: Session,
    item_id: UUID,
) -> list[MatchSuggestion]:
    """
    Função para listar as sugestões de match sugeridas para um item específico, seja ele perdido ou encontrado.
    args:
        session: Sessão do SQLAlchemy para acessar o banco de dados
        item_id: ID do item para o qual as sugestões de match devem ser listadas
    returns:
        list[MatchSuggestion]: Uma lista de sugestões de match sugeridas para o item especificado
    """
    statement = (
        select(MatchSuggestion)
        .where(MatchSuggestion.status == MatchStatus.SUGGESTED)
        .where(
            or_(
                MatchSuggestion.lost_item_id == item_id,
                MatchSuggestion.found_item_id == item_id,
            ),
        )
        .order_by(MatchSuggestion.created_at.asc())
    )
    return list(session.scalars(statement))
