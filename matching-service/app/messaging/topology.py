""""
Esse arquivo é responsável por definir a topologia de mensagens do sistema, incluindo as exchanges, filas e bindings.
"""
EVENTS_EXCHANGE = "domain.events"
DEAD_LETTER_EXCHANGE = "domain.events.dlx"

ROUTING_KEYS = {
    "item_created": "item.created",
    "item_updated": "item.updated",
    "match_suggested": "match.suggested",
    "match_accepted": "match.accepted",
    "match_rejected": "match.rejected",
    "recovery_case_opened": "recovery_case.opened",
    "recovery_case_cancelled": "recovery_case.cancelled",
    "recovery_case_completed": "recovery_case.completed",
}

QUEUE_BINDINGS = {
    "matching-service.item-events": [
        ROUTING_KEYS["item_created"],
        ROUTING_KEYS["item_updated"],
    ],
    "recovery-case-service.match-events": [
        ROUTING_KEYS["match_accepted"],
    ],
}

DEAD_LETTER_QUEUE_BINDINGS = {
    "matching-service.item-events.dlq": [
        ROUTING_KEYS["item_created"],
        ROUTING_KEYS["item_updated"],
    ],
    "recovery-case-service.match-events.dlq": [
        ROUTING_KEYS["match_accepted"],
    ],
}

AUDIT_QUEUE_BINDINGS = {
    "domain.events.audit": list(ROUTING_KEYS.values()),
}


def build_topology_snapshot() -> dict[str, object]:
    """"
    Constrói um snapshot da topologia de mensagens.  
    args:        
        None
    returns:    
        dict: Um dicionário contendo a configuração da topologia de mensagens.
    """
    return {
        "events_exchange": EVENTS_EXCHANGE,
        "dead_letter_exchange": DEAD_LETTER_EXCHANGE,
        "routing_keys": ROUTING_KEYS,
        "queue_bindings": QUEUE_BINDINGS,
        "dead_letter_queue_bindings": DEAD_LETTER_QUEUE_BINDINGS,
        "audit_queue_bindings": AUDIT_QUEUE_BINDINGS,
    }
