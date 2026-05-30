"""
Esse arquivo é responsável pelas exceções relacionadas ao serviço de autenticação.
"""
class AuthServiceError(Exception):
    """
    Exceção base para erros do serviço de autenticação.
    """


class DuplicateEmailError(AuthServiceError):
    """
    Erro lançado quando o e-mail informado já está em uso.
    """


class AuthenticationError(AuthServiceError):
    """
    Erro lançado quando as credenciais são inválidas.
    """

class InactiveUserError(AuthServiceError):
    """
    Erro lançado quando um usuário inativo tenta se autenticar.
    """
