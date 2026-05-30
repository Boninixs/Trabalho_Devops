""""
Esse arquivo é responsável por definir os endpoints relacionados a matches, como listar sugestões de matches.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidMatchDecisionError, MatchNotFoundError
from app.db.session import get_db
from app.mappers.match_mapper import to_match_response
from app.models.match_suggestion import MatchStatus
from app.schemas.match import MatchDecisionRequest, MatchFilters, MatchResponse
from app.services.matching_service import (
    accept_match,
    list_match_suggestions,
    reject_match,
    retrieve_match_suggestion,
)

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", response_model=list[MatchResponse])
def list_matches_endpoint(
    status_filter: MatchStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[MatchResponse]:
    """"
    Endpoint para listar sugestões de matches, com opção de filtrar por status.
    args:        
        status_filter: Filtro opcional para o status da sugestão de match.
        db: Sessão do banco de dados, injetada via Depends.
    returns:     
        Lista de sugestões de matches que correspondem ao filtro aplicado.
    """
    filters = MatchFilters(status=status_filter)
    return [to_match_response(match) for match in list_match_suggestions(db, filters)]


@router.get("/{match_id}", response_model=MatchResponse)
def get_match_endpoint(match_id: UUID, db: Session = Depends(get_db)) -> MatchResponse:
    """"
    Endpoint para obter detalhes de uma sugestão de match específica. 
    args:        
        match_id: ID da sugestão de match a ser recuperada.
        db: Sessão do banco de dados, injetada via Depends.
    returns:     
        Detalhes da sugestão de match correspondente ao ID fornecido.
    raise:  
        HTTPException com status 404 se a sugestão de match não for encontrada.
    """
    try:
        match = retrieve_match_suggestion(db, match_id)
    except MatchNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return to_match_response(match)


@router.post("/{match_id}/accept", response_model=MatchResponse)
def accept_match_endpoint(
    match_id: UUID,
    payload: MatchDecisionRequest,
    db: Session = Depends(get_db),
) -> MatchResponse:
    """"
    Endpoint para aceitar uma sugestão de match.
    args:        
        match_id: ID da sugestão de match a ser aceita.
        payload: Dados adicionais necessários para aceitar a sugestão de match.
        db: Sessão do banco de dados, injetada via Depends.
    returns:     
        Detalhes da sugestão de match após ser aceita.
    raise:  
        HTTPException com status 404 se a sugestão de match não for encontrada e 400 se a decisão for inválida.
    """
    try:
        match = accept_match(db, match_id, payload)
    except MatchNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidMatchDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_match_response(match)


@router.post("/{match_id}/reject", response_model=MatchResponse)
def reject_match_endpoint(
    match_id: UUID,
    payload: MatchDecisionRequest,
    db: Session = Depends(get_db),
) -> MatchResponse:
    """"
    Endpoint para rejeitar uma sugestão de match.
    args:        
        match_id: ID da sugestão de match a ser rejeitada.
        payload: Dados adicionais necessários para rejeitar a sugestão de match.
        db: Sessão do banco de dados, injetada via Depends.
    returns:     
        Detalhes da sugestão de match após ser rejeitada.
    raise:  
        HTTPException com status 404 se a sugestão de match não for encontrada e 400
    """
    try:
        match = reject_match(db, match_id, payload)
    except MatchNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidMatchDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_match_response(match)
