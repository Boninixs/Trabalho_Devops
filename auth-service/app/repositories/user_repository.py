""""
Esse arquivo é responsável por fornecer funções para interagir com a tabela de User no banco de dados.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_email(session: Session, email: str) -> User | None:
    """"
    Obtém um usuário pelo email, consultando a tabela de User. 
    args:
        session: Sessão do banco de dados.
        email: O email do usuário a ser buscado.
    returns:
        User | None: O usuário correspondente ao email fornecido, ou None se não for encontrado.
    """
    statement = select(User).where(User.email == email)
    return session.scalar(statement)


def get_user_by_id(session: Session, user_id: UUID) -> User | None:
    """"
    Obtém um usuário pelo ID, consultando a tabela de User. 
    args:
        session: Sessão do banco de dados.
        user_id: O ID do usuário a ser buscado.
    returns:
        User | None: O usuário correspondente ao ID fornecido, ou None se não for encontrado.
    """
    return session.get(User, user_id)


def add_user(session: Session, user: User) -> User:
    """"
    Adiciona um novo usuário à tabela de User.  
    args:
        session: Sessão do banco de dados.
        user: Instância do User a ser adicionada.
    returns:
        User: A instância do User persistida no banco de dados.
    """
    session.add(user)
    return user
