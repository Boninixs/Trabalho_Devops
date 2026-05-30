"""
Esse arquivo é responsável pelas exceções relacionadas ao serviço de matching.
"""
class MatchingServiceError(Exception):
    """
    Exceção base para o serviço de matching.
    """


class MatchNotFoundError(MatchingServiceError):
    """
    Erro lançado quando um match não é encontrado.
    """


class InvalidMatchError(MatchingServiceError):
    """"
    Erro lançado quando um match não pode ser criado ou atualizado.
    """


class InvalidMatchDecisionError(MatchingServiceError):
    """"
    Erro lançado quando uma decisão de match é inválida.
    """