"""
Esse arquivo é responsável por definir as funções de acesso ao banco de dados para o modelo ItemProjection.
"""
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.item_projection import ExternalItemStatus, ItemClassification, ItemProjection


def get_item_projection_by_id(session: Session, item_id: UUID) -> ItemProjection | None:
    """"
    Função para obter uma projeção de item pelo seu ID.
    args:   
        session: Sessão do SQLAlchemy para acessar o banco de dados
        item_id: ID do item a ser buscado
    returns:
        ItemProjection | None: A projeção do item correspondente ao ID fornecido, ou None se não for encontrada.    
    """
    return session.get(ItemProjection, item_id)


def add_item_projection(session: Session, item_projection: ItemProjection) -> ItemProjection:
    """"
    Função para adicionar uma nova projeção de item ao banco de dados.
    args:
        session: Sessão do SQLAlchemy para acessar o banco de dados
        item_projection: A projeção do item a ser adicionada
    returns:
        ItemProjection: A projeção do item que foi adicionada ao banco de dados.
    """
    session.add(item_projection)
    return item_projection


def list_candidate_item_projections(
    session: Session,
    *,
    classification: ItemClassification,
    exclude_item_id: UUID,
) -> list[ItemProjection]:
    """"
    Função para listar as projeções de itens candidatas a serem sugeridas como correspondências, com base na 
    classificação e excluindo um item específico.
    args:
        session: Sessão do SQLAlchemy para acessar o banco de dados
        classification: Classificação dos itens a serem listados (LOST ou FOUND)
        exclude_item_id: ID do item a ser excluído da lista de candidatos
    returns:        
        list[ItemProjection]: Uma lista de projeções de itens candidatas a serem sugeridas como correspondências.
    """
    statement: Select[tuple[ItemProjection]] = (
        select(ItemProjection)
        .where(ItemProjection.classification == classification)
        .where(ItemProjection.id != exclude_item_id)
        .order_by(ItemProjection.created_at.asc())
    )
    return list(session.scalars(statement))


def get_item_projections_by_ids(session: Session, item_ids: list[UUID]) -> list[ItemProjection]:
    """"
    Função para obter uma lista de projeções de itens com base em uma lista de IDs.
    args:
        session: Sessão do SQLAlchemy para acessar o banco de dados
        item_ids: Lista de IDs dos itens a serem buscados
    returns:
        list[ItemProjection]: Uma lista de projeções de itens correspondentes aos IDs fornecidos.
    """
    statement = select(ItemProjection).where(ItemProjection.id.in_(item_ids))
    return list(session.scalars(statement))
