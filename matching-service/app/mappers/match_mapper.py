""""
Esse arquivo é responsável por mapear os objetos de domínio. 
"""
from app.models.match_suggestion import MatchSuggestion
from app.schemas.match import MatchResponse
from app.schemas.match_event import MatchEventPayload


def to_match_response(match: MatchSuggestion) -> MatchResponse:
    """
    Mapeia um objeto MatchSuggestion para um objeto MatchResponse.
    Args:        
        match: O objeto MatchSuggestion a ser mapeado.
    Returns:        
        MatchResponse: 
        O objeto MatchResponse resultante do mapeamento.
    """
    return MatchResponse.model_validate(match)


def to_match_event_payload(match: MatchSuggestion) -> MatchEventPayload:
    """"
    Mapeia um objeto MatchSuggestion para um objeto MatchEventPayload.
    Args:        
        match: O objeto MatchSuggestion a ser mapeado.
    Returns:        
        MatchEventPayload: 
        O objeto MatchEventPayload resultante do mapeamento.
    """
    return MatchEventPayload.model_validate(match)

